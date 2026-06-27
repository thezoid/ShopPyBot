"""web/sse_hub.py: SSE pub-sub hub and background poll loop.

This module is imported ONLY by web/ code. It must NOT be imported from
core/, orchestrator.py, or any file the bot daemon thread runs. The bot
thread must never touch asyncio.Queue objects (not thread-safe).

_poll_loop (running on uvicorn's event loop) is the SOLE SSE producer.
"""

import asyncio
import json

from web.log_reader import tail_log_lines

# Module-level constants: tests override these directly on the module
# (e.g. web.sse_hub._POLL_INTERVAL_SECS = 0.05) before constructing the app.
_POLL_INTERVAL_SECS = 1.0   # seconds between status polls
_KEEPALIVE_SECS = 15.0      # seconds before emitting ": keep-alive" comment


class SseHub:
    """Pub-sub hub for Server-Sent Events clients.

    All methods are synchronous and must only be called from uvicorn's event
    loop (never from the bot daemon thread).

    Each subscriber holds a bounded asyncio.Queue(maxsize=100). When a queue
    is full, broadcast drops the oldest item before inserting the new frame
    so the producer never blocks and memory stays bounded (slow-client safety).
    """

    def __init__(self) -> None:
        self._queues: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        """Create a new per-client queue, register it, and return it."""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._queues.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Remove a client queue. Safe to call if q is already removed."""
        self._queues.discard(q)

    def broadcast(self, event: str, payload: dict) -> None:
        """Send an SSE frame to every subscribed client.

        Frame format: "event: {event}\\ndata: {json}\\n\\n"

        Drop-oldest strategy: if a client queue is full, discard its oldest
        item via get_nowait() before inserting the new frame. The producer
        never blocks regardless of slow or dead clients.
        """
        frame = f"event: {event}\ndata: {json.dumps(payload)}\n\n"
        for q in list(self._queues):  # snapshot: avoids mutation-during-iteration
            if q.full():
                try:
                    q.get_nowait()  # drop oldest to make room
                except asyncio.QueueEmpty:
                    pass  # another coroutine drained it between full() and get_nowait()
            try:
                q.put_nowait(frame)
            except asyncio.QueueFull:
                pass  # race: filled again between full() check and put_nowait()


async def _poll_loop(
    hub: SseHub,
    svc,
    poll_interval: float | None = None,
) -> None:
    """Background coroutine: sole SSE producer, running on uvicorn's event loop.

    Args:
        hub:           The SseHub to broadcast to.
        svc:           BotService (or compatible mock) whose get_status() is called.
        poll_interval: Seconds between polls. If None, reads _POLL_INTERVAL_SECS from
                       this module at each iteration so test overrides take effect.
                       Pass an explicit value to pin the interval (e.g., in unit tests
                       that call _poll_loop directly without module-level patching).

    Each tick:
    - Reads svc.get_status() via asyncio.to_thread (sync call, bot-thread safe)
    - Broadcasts a "status" frame to all subscribers
    - Reads new log lines via tail_log_lines(cursor) via asyncio.to_thread
    - Broadcasts a "log" frame per new line

    Error handling: asyncio.CancelledError propagates (lifespan shutdown).
    Any other exception is logged (class name only, never str(exc) per SSE-03)
    and the loop continues -- a single read error must never kill the stream.
    """
    cursor = 0
    while True:
        try:
            interval = poll_interval if poll_interval is not None else _POLL_INTERVAL_SECS
            await asyncio.sleep(interval)
            status = await asyncio.to_thread(svc.get_status)
            hub.broadcast("status", status)
            new_lines, cursor = await asyncio.to_thread(tail_log_lines, cursor)
            for line in new_lines:
                hub.broadcast("log", {"line": line})
        except asyncio.CancelledError:
            raise  # propagate: lifespan shutdown must be able to stop the loop
        except Exception as exc:
            from logger import writeLog  # lazy import: avoids import-time coupling
            writeLog(f"SSE poll error: {exc.__class__.__name__}", "WARNING")
