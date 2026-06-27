"""web/routes/sse.py: Server-Sent Events endpoint for the ShopPyBot dashboard.

Exposes GET /api/events (via prefix=/api at include time).

The generator reads the current keepalive timeout from the web.sse_hub module at
call time so that test overrides of sse_hub._KEEPALIVE_SECS take effect without
restarting the app.

No Depends(check_origin): this is a read-only GET endpoint, matching the security
posture of /api/status and /api/logs (POST/DELETE endpoints carry the CSRF guard).
"""

import asyncio

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

from web import sse_hub

router = APIRouter()


@router.get("/events")
async def sse_events(request: Request):
    """Stream Server-Sent Events to the client (text/event-stream).

    Opens with 'retry: 3000' so the browser reconnects after 3s on drop.
    Emits 'event: status' and 'event: log' frames from the SseHub broadcast queue.
    Emits ': keep-alive' comments on idle to prevent proxy idle-timeout disconnects.
    Calls hub.unsubscribe in a finally block to guarantee no queue leak on disconnect.
    """
    hub = request.app.state.sse_hub
    return StreamingResponse(
        _event_generator(request, hub),
        media_type="text/event-stream",
    )


async def _event_generator(
    request: Request,
    hub,
    keepalive_secs: float | None = None,
    max_frames: int | None = None,
):
    """Async generator that yields SSE frames for a single connected client.

    Subscribes to the hub on entry and unsubscribes in the finally block, so the
    queue is always cleaned up regardless of how the generator exits (normal break,
    CancelledError, or generator close by the ASGI server).

    Args:
        request:        The active FastAPI/Starlette request (used for is_disconnected).
        hub:            The SseHub instance from app.state.sse_hub.
        keepalive_secs: Override idle timeout. If None, reads sse_hub._KEEPALIVE_SECS
                        at each call so test monkeypatches are respected.
        max_frames:     Optional cap on frames yielded before the generator exits.
                        None (the production default, used by the route) means the
                        stream runs until the client disconnects. A finite value lets
                        unit tests drive the generator directly to a bounded length
                        without relying on transport-level disconnect — there is NO
                        test-harness detection in this function.
    """
    # Resolve keepalive at call time so test overrides of sse_hub._KEEPALIVE_SECS apply.
    ka = keepalive_secs if keepalive_secs is not None else sse_hub._KEEPALIVE_SECS

    queue = hub.subscribe()
    frame_count = 0
    try:
        # Emit retry directive first — guaranteed even if keepalive fires before a frame.
        yield "retry: 3000\n\n"
        frame_count += 1
        while max_frames is None or frame_count < max_frames:
            if await request.is_disconnected():
                break
            try:
                frame = await asyncio.wait_for(queue.get(), timeout=ka)
                yield frame
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
            frame_count += 1
    finally:
        hub.unsubscribe(queue)
