"""Tests for signal bridge + write-queue flush in core/orchestrator.py.

Covers:
- SRV-02 POSIX path: loop.add_signal_handler used when available
- SRV-02 Windows path: signal.signal fallback when add_signal_handler raises NotImplementedError
- SRV-02 handler calls loop.call_soon_threadsafe(root_task.cancel)
- SRV-02 write-queue manual flush: all items dispatched, queue.join() does not hang
"""

import asyncio
import signal
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from core.orchestrator import _flush_write_queue, _register_signals


# ---------------------------------------------------------------------------
# _register_signals: POSIX path
# ---------------------------------------------------------------------------


def test_signal_bridge_posix_path():
    """POSIX: add_signal_handler used for SIGTERM+SIGINT; signal.signal NOT called."""
    loop = MagicMock()
    loop.add_signal_handler = MagicMock()  # does not raise
    root_task = MagicMock()

    with patch("core.orchestrator.signal.signal") as mock_signal_signal:
        _register_signals(loop, root_task)

    # add_signal_handler called for both signals
    calls = loop.add_signal_handler.call_args_list
    sigs_registered = [c.args[0] for c in calls]
    assert signal.SIGTERM in sigs_registered, "SIGTERM not registered via add_signal_handler"
    assert signal.SIGINT in sigs_registered, "SIGINT not registered via add_signal_handler"

    # signal.signal must NOT be called on the POSIX path
    mock_signal_signal.assert_not_called()


# ---------------------------------------------------------------------------
# _register_signals: Windows fallback path
# ---------------------------------------------------------------------------


def test_signal_bridge_windows_fallback():
    """Windows: signal.signal used for SIGTERM+SIGINT when add_signal_handler raises NotImplementedError."""
    loop = MagicMock()
    loop.add_signal_handler = MagicMock(side_effect=NotImplementedError)
    root_task = MagicMock()

    with patch("core.orchestrator.signal.signal") as mock_signal_signal:
        _register_signals(loop, root_task)

    calls = mock_signal_signal.call_args_list
    sigs_registered = [c.args[0] for c in calls]
    assert signal.SIGTERM in sigs_registered, "SIGTERM not registered via signal.signal on Windows path"
    assert signal.SIGINT in sigs_registered, "SIGINT not registered via signal.signal on Windows path"


# ---------------------------------------------------------------------------
# _register_signals: handler calls call_soon_threadsafe(root_task.cancel)
# ---------------------------------------------------------------------------


def test_shutdown_handler_cancels_root_task():
    """The handler registered by _register_signals cancels root_task via call_soon_threadsafe."""
    loop = MagicMock()
    captured_handler = None

    def capture_add_signal_handler(sig, handler):
        nonlocal captured_handler
        captured_handler = handler

    loop.add_signal_handler = MagicMock(side_effect=capture_add_signal_handler)
    root_task = MagicMock()

    _register_signals(loop, root_task)

    assert captured_handler is not None, "_register_signals did not register any handler"

    # Invoke the handler (simulates OS signal delivery)
    captured_handler()

    loop.call_soon_threadsafe.assert_called_once_with(root_task.cancel)


# ---------------------------------------------------------------------------
# _flush_write_queue: drains all items, no hang, error path calls task_done
# ---------------------------------------------------------------------------


async def test_write_queue_flush_before_teardown():
    """Manual flush dispatches all remaining items; queue.join() returns immediately."""
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    dispatched: list = []

    async def fake_dispatch(lp, item):
        dispatched.append(item)

    # Two normal items
    item_a = ("clear_available", "https://example.com/a")
    item_b = ("clear_available", "https://example.com/b")
    await queue.put(item_a)
    await queue.put(item_b)

    with patch("core.orchestrator._dispatch_write", side_effect=fake_dispatch):
        await _flush_write_queue(queue, loop)

    assert dispatched == [item_a, item_b], f"Unexpected dispatch order: {dispatched}"
    assert queue.empty(), "Queue not empty after flush"

    # join() must return immediately (all task_done() calls made)
    done = False

    async def check_join():
        nonlocal done
        await queue.join()
        done = True

    await asyncio.wait_for(check_join(), timeout=1.0)
    assert done, "queue.join() did not return (task_done not called)"


async def test_write_queue_flush_error_still_calls_task_done():
    """Error in _dispatch_write is logged as ERROR; task_done still called (no hang)."""
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    bad_item = ("clear_available", "https://bad.example.com")
    await queue.put(bad_item)

    async def raising_dispatch(lp, item):
        raise RuntimeError("simulated write error")

    with (
        patch("core.orchestrator._dispatch_write", side_effect=raising_dispatch),
        patch("core.orchestrator.writeLog") as mock_log,
    ):
        await _flush_write_queue(queue, loop)

    assert queue.empty(), "Queue not empty after flush with error"

    # join() must not hang
    await asyncio.wait_for(queue.join(), timeout=1.0)

    # ERROR log emitted
    error_calls = [c for c in mock_log.call_args_list if c.args[1] == "ERROR"]
    assert error_calls, "No ERROR log emitted for dispatch failure"
