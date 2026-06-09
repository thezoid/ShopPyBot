"""Tests for CaptchaSolver wiring: registry.assign_solver, orchestrator construction,
balance-check invocation, and BotService startup log (ANTI-06, ANTI-07).

TDD RED suite written first; implementation lives in core/registry.py,
core/orchestrator.py, and core/service.py.
"""
from __future__ import annotations

import asyncio
import types
from unittest.mock import MagicMock, patch, AsyncMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plugin():
    """Return a minimal plugin-like object with no pre-existing captcha attr."""
    return types.SimpleNamespace()


def _make_registry(captcha_solver=None, proxy_pool=None):
    """Build a PluginRegistry with no plugins_dir scanning."""
    from core.registry import PluginRegistry
    from pathlib import Path
    with patch("core.registry._discover_plugins", return_value=[]):
        reg = PluginRegistry.__new__(PluginRegistry)
        reg._all_plugins = []
        reg._active_plugins = []
        reg._proxy_pool = proxy_pool
        reg._captcha_solver = captcha_solver
        return reg


# ---------------------------------------------------------------------------
# Task 1: assign_solver wiring in PluginRegistry
# ---------------------------------------------------------------------------

class TestAssignSolver:
    def test_assign_solver_sets_attribute_to_solver(self):
        """When a solver is configured, assign_solver injects it onto the plugin."""
        from core.registry import PluginRegistry
        solver = MagicMock()
        reg = _make_registry(captcha_solver=solver)
        plugin = _make_plugin()

        reg.assign_solver(plugin)

        assert plugin._captcha_solver is solver

    def test_assign_solver_sets_none_when_no_solver(self):
        """When no solver is configured (disabled), plugin._captcha_solver is None."""
        reg = _make_registry(captcha_solver=None)
        plugin = _make_plugin()

        reg.assign_solver(plugin)

        assert plugin._captcha_solver is None

    def test_assign_solver_method_exists(self):
        """assign_solver is a method on PluginRegistry."""
        from core.registry import PluginRegistry
        assert hasattr(PluginRegistry, "assign_solver")
        assert callable(PluginRegistry.assign_solver)

    def test_registry_accepts_captcha_solver_kwarg(self):
        """PluginRegistry.__init__ accepts captcha_solver= and stores it."""
        from core.registry import PluginRegistry
        solver = MagicMock()
        with patch("core.registry._discover_plugins", return_value=[]):
            from pathlib import Path
            reg = PluginRegistry(MagicMock(), Path("/tmp/fake"), captcha_solver=solver)
        assert reg._captcha_solver is solver

    def test_registry_default_captcha_solver_is_none(self):
        """PluginRegistry._captcha_solver defaults to None when kwarg omitted."""
        from core.registry import PluginRegistry
        with patch("core.registry._discover_plugins", return_value=[]):
            from pathlib import Path
            reg = PluginRegistry(MagicMock(), Path("/tmp/fake"))
        assert reg._captcha_solver is None


# ---------------------------------------------------------------------------
# Task 1: async_main builds solver only when captcha.enabled=True
# ---------------------------------------------------------------------------

class TestOrchestratorSolverConstruction:
    """Verify CaptchaSolver.from_config is called correctly in async_main."""

    def _make_cfg(self, captcha_enabled=False):
        """Minimal AppConfig-like namespace for orchestrator tests."""
        captcha_cfg = types.SimpleNamespace(
            enabled=captcha_enabled,
            max_solves_per_run=5,
            low_balance_threshold=1.0,
        )
        proxy_cfg = types.SimpleNamespace(enabled=False)
        app_cfg = types.SimpleNamespace(poll_interval=30)
        return types.SimpleNamespace(
            captcha=captcha_cfg,
            proxy=proxy_cfg,
            app=app_cfg,
        )

    def test_from_config_not_called_when_disabled(self):
        """CaptchaSolver.from_config must NOT be called when captcha.enabled=False."""
        cfg = self._make_cfg(captcha_enabled=False)

        with patch("core.orchestrator.CaptchaSolver") as mock_cls, \
             patch("core.orchestrator.get_store"), \
             patch("core.orchestrator.PluginRegistry") as mock_reg_cls, \
             patch("core.orchestrator.get_items_sync", return_value=[]), \
             patch("core.orchestrator._staggered_setup", new=AsyncMock()), \
             patch("core.orchestrator.build_dispatcher", return_value=MagicMock()), \
             patch("core.orchestrator._start_stdin_listener"):

            mock_reg_cls.return_value._active_plugins = []

            asyncio.run(_run_async_main(cfg))

        mock_cls.from_config.assert_not_called()

    def test_from_config_called_when_enabled(self):
        """CaptchaSolver.from_config IS called when captcha.enabled=True."""
        cfg = self._make_cfg(captcha_enabled=True)
        mock_solver = MagicMock()

        with patch("core.orchestrator.CaptchaSolver") as mock_cls, \
             patch("core.orchestrator.get_store") as mock_store, \
             patch("core.orchestrator.PluginRegistry") as mock_reg_cls, \
             patch("core.orchestrator.get_items_sync", return_value=[]), \
             patch("core.orchestrator._staggered_setup", new=AsyncMock()), \
             patch("core.orchestrator.build_dispatcher", return_value=MagicMock()), \
             patch("core.orchestrator._start_stdin_listener"):

            mock_cls.from_config.return_value = mock_solver
            mock_reg_cls.return_value._active_plugins = []

            asyncio.run(_run_async_main(cfg))

        mock_cls.from_config.assert_called_once()
        call_args = mock_cls.from_config.call_args
        # First positional arg is cfg.captcha
        assert call_args[0][0] is cfg.captcha

    def test_balance_check_called_via_executor_when_solver_exists(self):
        """check_balance_at_startup runs via run_in_executor, not inline."""
        cfg = self._make_cfg(captcha_enabled=True)
        mock_solver = MagicMock()

        calls = []

        async def _capture_run(coro_or_fn, *args):
            """Capture executor calls to detect balance check."""
            calls.append(coro_or_fn)
            if callable(coro_or_fn):
                coro_or_fn(*args)

        with patch("core.orchestrator.CaptchaSolver") as mock_cls, \
             patch("core.orchestrator.get_store"), \
             patch("core.orchestrator.PluginRegistry") as mock_reg_cls, \
             patch("core.orchestrator.get_items_sync", return_value=[]), \
             patch("core.orchestrator._staggered_setup", new=AsyncMock()), \
             patch("core.orchestrator.build_dispatcher", return_value=MagicMock()), \
             patch("core.orchestrator._start_stdin_listener"):

            mock_cls.from_config.return_value = mock_solver
            mock_reg_cls.return_value._active_plugins = []

            asyncio.run(_run_async_main_with_executor_capture(cfg, calls))

        # The balance check function should have been passed to run_in_executor
        assert mock_solver.check_balance_at_startup in calls, (
            "check_balance_at_startup was not dispatched via run_in_executor"
        )

    def test_captcha_solver_passed_to_registry(self):
        """async_main passes captcha_solver= to PluginRegistry constructor."""
        cfg = self._make_cfg(captcha_enabled=True)
        mock_solver = MagicMock()

        with patch("core.orchestrator.CaptchaSolver") as mock_cls, \
             patch("core.orchestrator.get_store"), \
             patch("core.orchestrator.PluginRegistry") as mock_reg_cls, \
             patch("core.orchestrator.get_items_sync", return_value=[]), \
             patch("core.orchestrator._staggered_setup", new=AsyncMock()), \
             patch("core.orchestrator.build_dispatcher", return_value=MagicMock()), \
             patch("core.orchestrator._start_stdin_listener"):

            mock_cls.from_config.return_value = mock_solver
            mock_reg_cls.return_value._active_plugins = []

            asyncio.run(_run_async_main(cfg))

        _, kwargs = mock_reg_cls.call_args
        assert kwargs.get("captcha_solver") is mock_solver


# ---------------------------------------------------------------------------
# Task 1: _staggered_setup calls assign_solver
# ---------------------------------------------------------------------------

class TestStaggeredSetupAssignSolver:
    """Verify assign_solver is invoked in _staggered_setup."""

    @pytest.mark.asyncio
    async def test_assign_solver_called_in_staggered_setup(self):
        """_staggered_setup calls registry.assign_solver(plugin) before setup()."""
        from core.orchestrator import _staggered_setup

        mock_plugin = MagicMock()
        mock_plugin.__class__.__name__ = "TestPlugin"
        mock_plugin.setup = AsyncMock()

        mock_registry = MagicMock()
        mock_registry.plugins_for_items.return_value = [mock_plugin]
        mock_registry._active_plugins = []

        await _staggered_setup(mock_registry, [], stagger_secs=0)

        mock_registry.assign_solver.assert_called_once_with(mock_plugin)


# ---------------------------------------------------------------------------
# Task 2: BotService startup log
# ---------------------------------------------------------------------------

class TestBotServiceStartupLog:
    """Verify BotService.__init__ logs CAPTCHA-enabled status without key leakage."""

    def _make_captcha_cfg(self, enabled: bool):
        from core.config_schema import AppConfig, CaptchaConfig
        cfg = AppConfig()
        # Override captcha config via model_copy
        captcha = CaptchaConfig(enabled=enabled, max_solves_per_run=5, low_balance_threshold=0.5)
        return cfg.model_copy(update={"captcha": captcha})

    def test_startup_log_present_when_enabled(self, caplog):
        """BotService logs 'CAPTCHA solving: enabled' when captcha.enabled=True."""
        import logging
        cfg = self._make_captcha_cfg(enabled=True)
        with patch("core.service.init_store"):
            with caplog.at_level(logging.DEBUG, logger="root"):
                from core.service import BotService
                BotService(cfg=cfg)

        messages = [r.message for r in caplog.records]
        assert any("CAPTCHA solving" in m and "enabled" in m for m in messages), (
            f"Expected CAPTCHA startup log; got: {messages}"
        )

    def test_startup_log_absent_when_disabled(self, caplog):
        """BotService does NOT log CAPTCHA solving when captcha.enabled=False."""
        import logging
        cfg = self._make_captcha_cfg(enabled=False)
        with patch("core.service.init_store"):
            with caplog.at_level(logging.DEBUG, logger="root"):
                from core.service import BotService
                BotService(cfg=cfg)

        messages = [r.message for r in caplog.records]
        assert not any("CAPTCHA solving" in m and "enabled" in m for m in messages), (
            f"Expected no CAPTCHA enabled log; got: {messages}"
        )

    def test_startup_log_contains_cap_and_threshold(self, caplog):
        """Startup log includes max_solves_per_run and low_balance_threshold."""
        import logging
        cfg = self._make_captcha_cfg(enabled=True)
        with patch("core.service.init_store"):
            with caplog.at_level(logging.DEBUG, logger="root"):
                from core.service import BotService
                BotService(cfg=cfg)

        messages = "\n".join(r.message for r in caplog.records)
        assert "max_solves_per_run" in messages
        assert "low_balance_threshold" in messages

    def test_startup_log_does_not_contain_api_key(self, caplog):
        """The startup log NEVER contains the TWOCAPTCHA_API_KEY value."""
        import logging
        import os
        os.environ["TWOCAPTCHA_API_KEY"] = "SECRET_KEY_VALUE_12345"
        try:
            cfg = self._make_captcha_cfg(enabled=True)
            with patch("core.service.init_store"):
                with caplog.at_level(logging.DEBUG, logger="root"):
                    from core.service import BotService
                    BotService(cfg=cfg)

            all_text = " ".join(r.message for r in caplog.records)
            assert "SECRET_KEY_VALUE_12345" not in all_text, (
                "API key was leaked into startup log"
            )
        finally:
            del os.environ["TWOCAPTCHA_API_KEY"]


# ---------------------------------------------------------------------------
# Async helpers for orchestrator tests
# ---------------------------------------------------------------------------

async def _run_async_main(cfg):
    """Run async_main with an early exit by raising KeyboardInterrupt."""
    import core.orchestrator as orch

    # Patch TaskGroup to raise immediately (avoid real async tasks)
    orig = asyncio.TaskGroup

    class _EarlyExit(Exception):
        pass

    class _FakeTaskGroup:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def create_task(self, coro, **kw):
            # Cancel immediately
            async def _noop():
                pass
            t = asyncio.ensure_future(_noop())
            return t

    with patch("core.orchestrator.asyncio") as mock_asyncio:
        mock_asyncio.TaskGroup = _FakeTaskGroup
        mock_asyncio.Queue = asyncio.Queue
        mock_asyncio.sleep = asyncio.sleep
        mock_asyncio.wait_for = asyncio.wait_for
        mock_asyncio.get_running_loop = asyncio.get_running_loop
        mock_asyncio.TimeoutError = asyncio.TimeoutError

        # We can't easily short-circuit TaskGroup; instead just call async_main
        # and trust that _staggered_setup is patched to return quickly.
        try:
            await asyncio.wait_for(orch.async_main(cfg, None), timeout=2.0)
        except (asyncio.TimeoutError, KeyboardInterrupt, Exception):
            pass


async def _run_async_main_with_executor_capture(cfg, calls_list):
    """Run async_main while capturing all run_in_executor calls."""
    import core.orchestrator as orch

    original_get_loop = asyncio.get_running_loop

    def _patched_get_loop():
        loop = original_get_loop()
        original_executor = loop.run_in_executor

        async def _capturing_executor(pool, fn, *args):
            calls_list.append(fn)
            # Actually run it to avoid side effects
            if callable(fn):
                return fn(*args)

        loop.run_in_executor = _capturing_executor
        return loop

    with patch("core.orchestrator.asyncio.get_running_loop", side_effect=_patched_get_loop):
        try:
            await asyncio.wait_for(orch.async_main(cfg, None), timeout=2.0)
        except (asyncio.TimeoutError, KeyboardInterrupt, Exception):
            pass
