"""SRV-02 regression: _register_signals must not kill the bot loop off the main thread.

BotService.start() runs async_main in a daemon thread (the dashboard's Start Bot path).
Signal disposition is main-thread-only in CPython:

  - Windows: loop.add_signal_handler raises NotImplementedError, and the
    signal.signal() fallback then raises
    "ValueError: signal only works in main thread of the main interpreter".
  - POSIX: loop.add_signal_handler itself raises ValueError from
    signal.set_wakeup_fd, which the NotImplementedError handler does not catch.

Either way the ValueError propagated out of async_main's fifth statement, so every
dashboard Start Bot died before plugin setup, while POST /api/bot/start still
returned 200. These tests fail without the main-thread guard.
"""

import asyncio
import signal
import threading

from core.orchestrator import _register_signals


def _call_in_loop():
    """Run _register_signals inside a real event loop; return None or the exception."""
    captured = {}

    async def inner():
        loop = asyncio.get_running_loop()
        task = asyncio.current_task()
        try:
            _register_signals(loop, task)
            captured["exc"] = None
        except BaseException as exc:      # noqa: BLE001 - the failure is the subject
            captured["exc"] = exc

    asyncio.run(inner())
    return captured["exc"]


def test_register_signals_is_noop_off_main_thread():
    """The regression itself: a background thread must not raise (was ValueError)."""
    result = {}

    def worker():
        result["exc"] = _call_in_loop()

    t = threading.Thread(target=worker, name="BotService-loop")
    t.start()
    t.join(timeout=10)

    assert not t.is_alive(), "worker thread hung"
    assert result["exc"] is None, (
        f"_register_signals raised off the main thread: {result['exc']!r}"
    )


def test_register_signals_installs_nothing_off_main_thread():
    """The no-op is real: process-wide SIGTERM disposition is left untouched."""
    before = signal.getsignal(signal.SIGTERM)

    t = threading.Thread(target=_call_in_loop, name="BotService-loop")
    t.start()
    t.join(timeout=10)

    assert signal.getsignal(signal.SIGTERM) is before


def test_register_signals_still_works_on_main_thread():
    """The guard must not disable SRV-02 for the CLI path, which IS the main thread."""
    original_term = signal.getsignal(signal.SIGTERM)
    original_int = signal.getsignal(signal.SIGINT)
    try:
        assert _call_in_loop() is None
    finally:
        # asyncio.run() closes the loop, which detaches any add_signal_handler
        # registrations; the signal.signal() fallback persists, so restore both.
        signal.signal(signal.SIGTERM, original_term)
        signal.signal(signal.SIGINT, original_int)


def test_async_main_reaches_past_signal_registration_in_a_thread(monkeypatch):
    """End-to-end shape: async_main gets past _register_signals off the main thread.

    PluginRegistry is the first statement AFTER _register_signals (orchestrator.py
    ordering: _build_proxy_pool, _build_captcha_solver, get_running_loop,
    current_task, _register_signals, then PluginRegistry). Patching it to raise a
    sentinel proves execution reached past the signal call without touching the DB,
    a browser, or the network.

    A bare object() for cfg is enough: _build_proxy_pool and _build_captcha_solver
    both getattr their way to None on an unconfigured object, so neither raises.
    """
    import core.orchestrator as orch

    class _Sentinel(Exception):
        pass

    reached = []

    def fake_registry(*args, **kwargs):
        reached.append("plugin_registry")
        raise _Sentinel

    monkeypatch.setattr(orch, "PluginRegistry", fake_registry)

    result = {}

    def worker():
        async def inner():
            try:
                await orch.async_main(object(), None)
            except BaseException as exc:   # noqa: BLE001
                result["exc"] = exc
        asyncio.run(inner())

    t = threading.Thread(target=worker, name="BotService-loop")
    t.start()
    t.join(timeout=10)

    assert not t.is_alive(), "worker thread hung"
    assert reached == ["plugin_registry"], (
        f"async_main died before PluginRegistry: {result.get('exc')!r}"
    )
    assert isinstance(result.get("exc"), _Sentinel), (
        f"expected the sentinel, got {result.get('exc')!r}"
    )
