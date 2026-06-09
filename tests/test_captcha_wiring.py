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
# Task 1: _build_captcha_solver helper + async_main registry wiring
# ---------------------------------------------------------------------------

class TestBuildCaptchaSolver:
    """Verify the _build_captcha_solver helper (extracted from async_main)."""

    def _make_captcha_cfg(self, enabled: bool):
        return types.SimpleNamespace(
            enabled=enabled,
            max_solves_per_run=5,
            low_balance_threshold=1.0,
        )

    def test_returns_none_when_disabled(self):
        """_build_captcha_solver returns None when captcha.enabled=False."""
        from core.orchestrator import _build_captcha_solver
        cfg = types.SimpleNamespace(captcha=self._make_captcha_cfg(enabled=False))

        with patch("core.orchestrator.CaptchaSolver") as mock_cls, \
             patch("core.orchestrator.get_store"):
            result = _build_captcha_solver(cfg)

        assert result is None
        mock_cls.from_config.assert_not_called()

    def test_returns_none_when_no_captcha_attr(self):
        """_build_captcha_solver returns None when cfg has no captcha attribute."""
        from core.orchestrator import _build_captcha_solver
        cfg = types.SimpleNamespace()  # no captcha attr

        with patch("core.orchestrator.CaptchaSolver") as mock_cls:
            result = _build_captcha_solver(cfg)

        assert result is None
        mock_cls.from_config.assert_not_called()

    def test_calls_from_config_when_enabled(self):
        """_build_captcha_solver calls CaptchaSolver.from_config with captcha cfg + store."""
        from core.orchestrator import _build_captcha_solver
        captcha_cfg = self._make_captcha_cfg(enabled=True)
        cfg = types.SimpleNamespace(captcha=captcha_cfg)
        mock_solver = MagicMock()

        with patch("core.orchestrator.CaptchaSolver") as mock_cls, \
             patch("core.orchestrator.get_store") as mock_store:
            mock_cls.from_config.return_value = mock_solver
            result = _build_captcha_solver(cfg)

        assert result is mock_solver
        mock_cls.from_config.assert_called_once_with(captcha_cfg, mock_store.return_value)

    def test_passes_store_from_get_store(self):
        """_build_captcha_solver passes get_store() as the second arg to from_config."""
        from core.orchestrator import _build_captcha_solver
        captcha_cfg = self._make_captcha_cfg(enabled=True)
        cfg = types.SimpleNamespace(captcha=captcha_cfg)
        fake_store = MagicMock()

        with patch("core.orchestrator.CaptchaSolver") as mock_cls, \
             patch("core.orchestrator.get_store", return_value=fake_store):
            mock_cls.from_config.return_value = MagicMock()
            _build_captcha_solver(cfg)

        _, args, _ = mock_cls.from_config.mock_calls[0]
        assert args[1] is fake_store


class TestOrchestratorBalanceCheck:
    """Verify balance check runs via run_in_executor in async_main."""

    @pytest.mark.asyncio
    async def test_balance_check_uses_run_in_executor(self):
        """When solver is not None, check_balance_at_startup is awaited via executor."""
        import core.orchestrator as orch

        mock_solver = MagicMock()
        executor_calls = []

        async def _fake_executor(pool, fn, *args):
            executor_calls.append(fn)
            if callable(fn):
                fn(*args)

        loop = asyncio.get_running_loop()
        original_executor = loop.run_in_executor
        loop.run_in_executor = _fake_executor

        try:
            with patch("core.orchestrator._build_proxy_pool", return_value=None), \
                 patch("core.orchestrator._build_captcha_solver", return_value=mock_solver), \
                 patch("core.orchestrator.PluginRegistry") as mock_reg_cls, \
                 patch("core.orchestrator.get_items_sync", return_value=[]), \
                 patch("core.orchestrator._staggered_setup", new=AsyncMock()), \
                 patch("core.orchestrator._start_stdin_listener"), \
                 patch("core.orchestrator.asyncio.TaskGroup") as mock_tg_cls:

                mock_reg_cls.return_value._active_plugins = []

                ctx = AsyncMock()
                ctx.__aenter__ = AsyncMock(return_value=ctx)
                ctx.__aexit__ = AsyncMock(return_value=False)
                ctx.create_task = MagicMock()
                mock_tg_cls.return_value = ctx

                cfg = types.SimpleNamespace(
                    captcha=types.SimpleNamespace(enabled=True),
                    proxy=types.SimpleNamespace(enabled=False),
                    app=types.SimpleNamespace(poll_interval=30),
                )

                try:
                    await asyncio.wait_for(orch.async_main(cfg, None), timeout=1.0)
                except (asyncio.TimeoutError, Exception):
                    pass
        finally:
            loop.run_in_executor = original_executor

        assert mock_solver.check_balance_at_startup in executor_calls, (
            "check_balance_at_startup was not dispatched via run_in_executor"
        )

    @pytest.mark.asyncio
    async def test_captcha_solver_passed_to_registry(self):
        """async_main passes captcha_solver= to PluginRegistry."""
        import core.orchestrator as orch

        mock_solver = MagicMock()

        with patch("core.orchestrator._build_proxy_pool", return_value=None), \
             patch("core.orchestrator._build_captcha_solver", return_value=mock_solver), \
             patch("core.orchestrator.PluginRegistry") as mock_reg_cls, \
             patch("core.orchestrator.get_items_sync", return_value=[]), \
             patch("core.orchestrator._staggered_setup", new=AsyncMock()), \
             patch("core.orchestrator._start_stdin_listener"), \
             patch("core.orchestrator.asyncio.TaskGroup") as mock_tg_cls:

            mock_reg_cls.return_value._active_plugins = []
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=ctx)
            ctx.__aexit__ = AsyncMock(return_value=False)
            ctx.create_task = MagicMock()
            mock_tg_cls.return_value = ctx

            cfg = types.SimpleNamespace(
                captcha=types.SimpleNamespace(enabled=True),
                proxy=types.SimpleNamespace(enabled=False),
                app=types.SimpleNamespace(poll_interval=30),
            )

            try:
                await asyncio.wait_for(orch.async_main(cfg, None), timeout=1.0)
            except (asyncio.TimeoutError, Exception):
                pass

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
    """Verify BotService.__init__ logs CAPTCHA-enabled status without key leakage.

    BotService uses Python's logging module (via logging.getLogger) for the CAPTCHA
    startup message so that caplog can capture it for security-assertion tests.
    This mirrors the approach used in core/captcha.py (Plan 01 decision).
    """

    def _make_captcha_cfg(self, enabled: bool):
        from core.config_schema import AppConfig, CaptchaConfig
        cfg = AppConfig()
        captcha = CaptchaConfig(enabled=enabled, max_solves_per_run=5, low_balance_threshold=0.5)
        return cfg.model_copy(update={"captcha": captcha})

    def test_startup_log_present_when_enabled(self, caplog):
        """BotService logs 'CAPTCHA solving: enabled' when captcha.enabled=True."""
        import logging
        cfg = self._make_captcha_cfg(enabled=True)
        with patch("core.service.init_store"):
            with caplog.at_level(logging.INFO, logger="core.service"):
                from core.service import BotService
                BotService(cfg=cfg)

        messages = [r.message for r in caplog.records]
        assert any("CAPTCHA solving" in m and "enabled" in m for m in messages), (
            f"Expected CAPTCHA startup log; got: {messages}"
        )

    def test_startup_log_absent_when_disabled(self, caplog):
        """BotService does NOT log 'CAPTCHA solving: enabled' when captcha.enabled=False."""
        import logging
        cfg = self._make_captcha_cfg(enabled=False)
        with patch("core.service.init_store"):
            with caplog.at_level(logging.INFO, logger="core.service"):
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
            with caplog.at_level(logging.INFO, logger="core.service"):
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
                with caplog.at_level(logging.INFO, logger="core.service"):
                    from core.service import BotService
                    BotService(cfg=cfg)

            all_text = " ".join(r.message for r in caplog.records)
            assert "SECRET_KEY_VALUE_12345" not in all_text, (
                "API key was leaked into startup log"
            )
        finally:
            del os.environ["TWOCAPTCHA_API_KEY"]


