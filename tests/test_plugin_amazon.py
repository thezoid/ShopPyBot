"""Tests for plugins/shopbot_plugin_amazon.py (PLG-01, PLG-03, ASYNC-03).

Loads the plugin via importlib.util.spec_from_file_location to mirror how the
registry discovers plugins -- no sys.path manipulation required.
"""

import asyncio
import importlib.util
import inspect
import sys
from pathlib import Path
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module loading (mirrors registry discovery pattern)
# ---------------------------------------------------------------------------

_PLUGIN_PATH = Path(__file__).parent.parent / "plugins" / "shopbot_plugin_amazon.py"


def _load_amazon_module():
    spec = importlib.util.spec_from_file_location("shopbot_plugin_amazon", _PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_amazon_module = _load_amazon_module()
AmazonPlugin = _amazon_module.AmazonPlugin

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

from core.plugin_base import RetailerPlugin  # noqa: E402


def _make_config(test_mode=True, items=None):
    """Return a minimal config-like object suitable for AmazonPlugin."""
    cfg = MagicMock()
    cfg.debug.test_mode = test_mode
    cfg.available.items = items or []
    cfg.checkout.step_timeout_secs = 30  # BUY-06: required for asyncio.timeout in auto_buy
    return cfg


# ---------------------------------------------------------------------------
# ABC + structural tests (sync -- no async needed)
# ---------------------------------------------------------------------------


def test_amazon_satisfies_abc():
    """AmazonPlugin must be a concrete subclass of RetailerPlugin (PLG-01)."""
    assert issubclass(AmazonPlugin, RetailerPlugin)
    # Instantiating must succeed (all abstract methods implemented).
    plugin = AmazonPlugin(config=None)
    assert plugin is not None


def test_domain_patterns_includes_amazon():
    assert "amazon.com" in AmazonPlugin.domain_patterns


def test_no_global_driver():
    """PLG-03: no module-level 'driver'; instance.driver is None before setup()."""
    assert not hasattr(_amazon_module, "driver"), (
        "Module must not define a top-level 'driver' variable"
    )
    plugin = AmazonPlugin(config=None)
    assert plugin.driver is None

    # Also verify the source contains the required self.driver assignment pattern.
    source = _PLUGIN_PATH.read_text()
    assert "self.driver = await nodriver.start" in source, (
        "Plugin must build self.driver via nodriver.start() in setup()"
    )


# ---------------------------------------------------------------------------
# Async tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_availability_returns_true_when_button_found(fake_browser):
    """check_availability returns True when add-to-cart button is present."""
    plugin = AmazonPlugin(config=_make_config())
    plugin.driver = fake_browser

    # fake_browser.get returns fake_tab; fake_tab.select returns a fake element.
    # Patch detect_captcha to skip blocking input().
    with patch.object(plugin, "detect_captcha", new=AsyncMock(return_value=False)):
        result = await plugin.check_availability("https://www.amazon.com/dp/B00TEST")

    assert result is True


@pytest.mark.asyncio
async def test_check_availability_returns_false_when_no_button(fake_browser):
    """check_availability returns False when both buttons are absent."""
    plugin = AmazonPlugin(config=_make_config())
    plugin.driver = fake_browser

    # Make tab.select always return None (button not found).
    fake_browser.main_tab.select = AsyncMock(return_value=None)
    fake_browser.get.return_value.select = AsyncMock(return_value=None)

    with patch.object(plugin, "detect_captcha", new=AsyncMock(return_value=False)):
        result = await plugin.check_availability("https://www.amazon.com/dp/B00TEST")

    assert result is False


@pytest.mark.asyncio
async def test_check_availability_returns_bool_type(fake_browser):
    """check_availability always returns a bool, never None or another type."""
    plugin = AmazonPlugin(config=_make_config())
    plugin.driver = fake_browser

    with patch.object(plugin, "detect_captcha", new=AsyncMock(return_value=False)):
        result = await plugin.check_availability("https://www.amazon.com/dp/B00TEST")

    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_check_availability_never_raises(fake_browser):
    """check_availability catches exceptions and returns False instead of raising."""
    plugin = AmazonPlugin(config=_make_config())
    plugin.driver = fake_browser

    # Make browser.get raise an unexpected error.
    fake_browser.get = AsyncMock(side_effect=RuntimeError("network error"))

    result = await plugin.check_availability("https://www.amazon.com/dp/B00TEST")

    assert result is False


@pytest.mark.asyncio
async def test_detect_captcha_returns_true_when_element_found(fake_browser):
    """detect_captcha returns True when the CAPTCHA text element is found."""
    plugin = AmazonPlugin(config=_make_config())
    plugin.driver = fake_browser

    # fake_browser.main_tab.find returns a fake element by default.
    result = await plugin.detect_captcha()

    assert result is True


@pytest.mark.asyncio
async def test_detect_captcha_returns_false_when_element_absent(fake_browser):
    """detect_captcha returns False when tab.find returns None."""
    plugin = AmazonPlugin(config=_make_config())
    plugin.driver = fake_browser
    fake_browser.main_tab.find = AsyncMock(return_value=None)

    result = await plugin.detect_captcha()

    assert result is False


# ---------------------------------------------------------------------------
# ASYNC-03: asyncio.Event intervention pattern tests (TDD RED)
# ---------------------------------------------------------------------------


def test_amazon_plugin_has_four_event_attrs():
    """AmazonPlugin.__init__ must create 4 asyncio.Event attributes (ASYNC-03)."""
    plugin = AmazonPlugin(config=None)
    for attr in ("captcha_event", "passkey_event", "otp_event", "test_pause_event"):
        assert hasattr(plugin, attr), f"AmazonPlugin missing attribute: {attr}"
        assert isinstance(getattr(plugin, attr), asyncio.Event), (
            f"{attr} must be asyncio.Event, got {type(getattr(plugin, attr))}"
        )


def test_amazon_plugin_has_wait_user_action_helper():
    """AmazonPlugin must define _wait_user_action coroutine method (ASYNC-03)."""
    plugin = AmazonPlugin(config=None)
    assert hasattr(plugin, "_wait_user_action"), (
        "AmazonPlugin missing _wait_user_action helper"
    )
    assert asyncio.iscoroutinefunction(plugin._wait_user_action), (
        "_wait_user_action must be an async def coroutine"
    )


def test_no_input_call_in_amazon_source():
    """No input() call (non-comment) must exist in the Amazon plugin source (ASYNC-03)."""
    source_lines = _PLUGIN_PATH.read_text().splitlines()
    violations = [
        (i + 1, line)
        for i, line in enumerate(source_lines)
        if "input(" in line and not line.lstrip().startswith("#")
    ]
    assert not violations, (
        "Found input() calls in non-comment lines:\n"
        + "\n".join(f"  line {ln}: {txt}" for ln, txt in violations)
    )


@pytest.mark.asyncio
async def test_captcha_event_resumes_check_availability(fake_browser, event_shim):
    """check_availability resumes after captcha_event is set (ASYNC-03 Event wakeup).

    Sequence:
      1. detect_captcha returns True -> _wait_user_action is called on captcha_event
      2. Before the await can block, the event_shim fires captcha_event via
         loop.call_soon_threadsafe (the real stdin-listener bridge)
      3. check_availability completes and returns a bool without hanging
    """
    plugin = AmazonPlugin(config=_make_config())
    plugin.driver = fake_browser

    loop = asyncio.get_running_loop()

    # Schedule the event signal to fire on the next iteration of the event loop.
    # This ensures _wait_user_action hits its await before the event is set,
    # proving the coroutine wakes from the Event -- not from a pre-set flag.
    loop.call_soon(event_shim, plugin.captcha_event, loop)

    with patch.object(plugin, "detect_captcha", new=AsyncMock(return_value=True)):
        result = await plugin.check_availability("https://www.amazon.com/dp/B00TEST")

    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_wait_user_action_clears_event_after_resume():
    """_wait_user_action must clear the event in finally so next cycle re-waits (Pitfall 7)."""
    plugin = AmazonPlugin(config=None)
    event = plugin.captcha_event
    event.set()  # pre-set so wait_for returns immediately

    # Use patch.object on the importlib-loaded module (not string import path).
    with patch.object(_amazon_module, "play_notification_sound"), \
         patch.object(_amazon_module, "writeLog"):
        await plugin._wait_user_action(event, "test message")

    assert not event.is_set(), "Event must be cleared after _wait_user_action returns"


@pytest.mark.asyncio
async def test_wait_user_action_timeout_does_not_raise():
    """_wait_user_action must log and continue (not raise) on 300s timeout.

    Patches asyncio.wait_for on the plugin module object to raise TimeoutError
    immediately, verifying the exception is caught and does not propagate.
    """
    plugin = AmazonPlugin(config=None)
    event = asyncio.Event()  # never set

    async def _fast_timeout(coro, timeout):
        # Close the coroutine we won't await to avoid ResourceWarning.
        coro.close()
        raise asyncio.TimeoutError()

    with patch.object(_amazon_module.asyncio, "wait_for", _fast_timeout), \
         patch.object(_amazon_module, "play_notification_sound"), \
         patch.object(_amazon_module, "writeLog"):
        try:
            await plugin._wait_user_action(event, "test")
        except asyncio.TimeoutError:
            pytest.fail("_wait_user_action must not propagate TimeoutError")


# ---------------------------------------------------------------------------
# SC3: setup() reads config.platforms.amazon.headless (Task 3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_setup_passes_headless_false_from_config(mock_nodriver_start):
    """setup() passes headless=False when config.platforms.amazon.headless is False (SC3)."""
    cfg = MagicMock()
    cfg.platforms.amazon.headless = False
    plugin = AmazonPlugin(config=cfg)
    await plugin.setup()
    assert mock_nodriver_start.last_kwargs.get("headless") is False


@pytest.mark.asyncio
async def test_setup_passes_headless_true_from_config(mock_nodriver_start):
    """setup() passes headless=True when config.platforms.amazon.headless is True (SC3)."""
    cfg = MagicMock()
    cfg.platforms.amazon.headless = True
    plugin = AmazonPlugin(config=cfg)
    await plugin.setup()
    assert mock_nodriver_start.last_kwargs.get("headless") is True


@pytest.mark.asyncio
async def test_setup_with_config_none_defaults_headless_true(mock_nodriver_start):
    """setup() defaults headless=True when self.config is None (guard test, SC3)."""
    plugin = AmazonPlugin(config=None)
    await plugin.setup()
    assert mock_nodriver_start.last_kwargs.get("headless") is True


def test_amazon_event_attrs_preserved_after_setup_change():
    """Amazon __init__ Event attributes must remain after setup() is updated (SC3 preservation)."""
    plugin = AmazonPlugin(config=None)
    for attr in ("captcha_event", "passkey_event", "otp_event", "test_pause_event"):
        assert hasattr(plugin, attr), f"AmazonPlugin still must have attribute: {attr}"
        assert isinstance(getattr(plugin, attr), asyncio.Event)


# ---------------------------------------------------------------------------
# BUY-06: per-step asyncio.timeout + _checkout_stage tracking (Plan 21-03)
# ---------------------------------------------------------------------------


def test_amazon_auto_buy_has_six_timeout_blocks():
    """Amazon auto_buy must contain exactly 6 asyncio.timeout(step_timeout_secs) blocks (BUY-06)."""
    import ast

    source = _PLUGIN_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_PLUGIN_PATH))

    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncWith):
            for item in node.items:
                ctx = item.context_expr
                if isinstance(ctx, ast.Call):
                    func = ctx.func
                    func_name = ""
                    if isinstance(func, ast.Name):
                        func_name = func.id
                    elif isinstance(func, ast.Attribute):
                        func_name = func.attr
                    if func_name == "timeout" and ctx.args:
                        arg_src = ast.unparse(ctx.args[0])
                        if "step_timeout_secs" in arg_src:
                            count += 1

    assert count == 6, (
        f"Amazon auto_buy must have exactly 6 asyncio.timeout(step_timeout_secs) blocks, found {count}"
    )


@pytest.mark.asyncio
async def test_amazon_auto_buy_returns_false_on_step_timeout(fake_browser):
    """BUY-06: when a DOM stage exceeds step_timeout_secs, auto_buy returns False.

    Simulates a hung navigate stage by making driver.get raise asyncio.TimeoutError,
    which is what asyncio.timeout() raises when the deadline expires.
    """
    cfg = MagicMock()
    cfg.debug.test_mode = False
    cfg.debug.monitor_only = False
    cfg.checkout.step_timeout_secs = 30
    cfg.available.items = []

    plugin = AmazonPlugin(config=cfg)
    plugin.driver = fake_browser

    fake_browser.get = AsyncMock(side_effect=asyncio.TimeoutError())

    with patch.object(plugin, "login", new=AsyncMock(return_value=True)):
        result = await plugin.auto_buy("https://www.amazon.com/dp/B00TEST")

    assert result is False, "auto_buy must return False when a step timeout fires"


@pytest.mark.asyncio
async def test_amazon_auto_buy_logs_stage_name_on_timeout(fake_browser):
    """BUY-06: the error log on step timeout must include the stage name and exc class name.

    Verifies _checkout_stage is readable on timeout and exc.__class__.__name__ is used
    (not str(exc), which could leak sensitive data -- T-21-07).
    """
    cfg = MagicMock()
    cfg.debug.test_mode = False
    cfg.debug.monitor_only = False
    cfg.checkout.step_timeout_secs = 30
    cfg.available.items = []

    plugin = AmazonPlugin(config=cfg)
    plugin.driver = fake_browser

    fake_browser.get = AsyncMock(side_effect=asyncio.TimeoutError())

    log_calls: list[tuple] = []

    def _capture_log(msg, level):
        log_calls.append((msg, level))

    with patch.object(plugin, "login", new=AsyncMock(return_value=True)), \
         patch.object(_amazon_module, "writeLog", _capture_log):
        await plugin.auto_buy("https://www.amazon.com/dp/B00TEST")

    error_logs = [msg for msg, lvl in log_calls if lvl == "ERROR"]
    assert any("navigate" in m for m in error_logs), (
        f"Error log must contain stage name 'navigate'; got: {error_logs}"
    )
    assert any("TimeoutError" in m for m in error_logs), (
        f"Error log must contain exc.__class__.__name__ 'TimeoutError'; got: {error_logs}"
    )


def test_amazon_checkout_stage_default_is_empty_string():
    """_checkout_stage must default to '' on AmazonPlugin (inherits from RetailerPlugin base)."""
    plugin = AmazonPlugin(config=None)
    assert plugin._checkout_stage == "", (
        f"_checkout_stage must default to '' on AmazonPlugin, got {plugin._checkout_stage!r}"
    )


# ---------------------------------------------------------------------------
# BF-02: durable place-order marker written before the click (Plan 30-04)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_amazon_marks_place_order_before_click(fake_browser):
    """BF-02/D-01: auto_buy must write the durable marker (via run_in_executor)
    BEFORE dispatching the place-order click (place_order_guarded call)."""
    cfg = MagicMock()
    cfg.debug.test_mode = False
    cfg.debug.monitor_only = False
    cfg.checkout.step_timeout_secs = 30
    cfg.available.items = []

    plugin = AmazonPlugin(config=cfg)
    plugin.driver = fake_browser

    call_order: list[str] = []

    def _fake_marker_write(link, attempted_at):
        call_order.append("marker")

    async def _fake_place_order_guarded(click_fn):
        call_order.append("click_dispatch")
        return True

    with patch.object(plugin, "login", new=AsyncMock(return_value=True)), \
         patch.object(
             plugin, "place_order_guarded",
             new=AsyncMock(side_effect=_fake_place_order_guarded),
         ), \
         patch("models.mark_place_order_attempted_sync", side_effect=_fake_marker_write) as mock_marker:
        result = await plugin.auto_buy("https://www.amazon.com/dp/B00TEST")

    assert call_order == ["marker", "click_dispatch"], (
        f"Marker write must precede the place-order click dispatch; got {call_order}"
    )
    mock_marker.assert_called_once()
    marker_args = mock_marker.call_args[0]
    assert marker_args[0] == "https://www.amazon.com/dp/B00TEST"
    assert result is True


def test_amazon_place_order_marker_not_via_write_queue():
    """BF-02: the marker write must not be routed through write_queue (D-01 durability).

    Checks non-comment lines only -- explanatory comments about *why* the marker
    avoids write_queue are fine; actual code referencing write_queue is not.
    """
    source_lines = _PLUGIN_PATH.read_text(encoding="utf-8").splitlines()
    assert any("mark_place_order_attempted_sync" in line for line in source_lines), (
        "Amazon plugin must call mark_place_order_attempted_sync"
    )
    violations = [
        (i + 1, line)
        for i, line in enumerate(source_lines)
        if "write_queue" in line and not line.lstrip().startswith("#")
    ]
    assert not violations, (
        "Amazon plugin must not reference write_queue in code for the place-order "
        f"marker (D-01): {violations}"
    )


# ---------------------------------------------------------------------------
# BF-03: login() -> bool via _verify_login_generic (D-11/D-12/D-13/D-14/D-15)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_returns_false_missing_credentials(monkeypatch, fake_browser):
    """login() returns False when AMZ_EMAIL/AMZ_PASSWORD are unset (D-14)."""
    plugin = AmazonPlugin(config=_make_config())
    plugin.driver = fake_browser
    fake_store = MagicMock()
    fake_store.get.return_value = None
    monkeypatch.setattr(_amazon_module, "get_store", lambda: fake_store)
    result = await plugin.login()
    assert result is False


@pytest.mark.asyncio
async def test_login_returns_false_missing_email_field(monkeypatch, fake_browser):
    """login() returns False when #ap_email is not found on the sign-in page."""
    plugin = AmazonPlugin(config=_make_config())
    plugin.driver = fake_browser
    fake_store = MagicMock()
    fake_store.get.side_effect = lambda key: "creds" if "EMAIL" in key or "PASSWORD" in key else None
    monkeypatch.setattr(_amazon_module, "get_store", lambda: fake_store)
    fake_browser.main_tab.select = AsyncMock(return_value=None)
    fake_browser.get.return_value.select = AsyncMock(return_value=None)
    result = await plugin.login()
    assert result is False


@pytest.mark.asyncio
async def test_login_returns_false_on_exception(monkeypatch, fake_browser):
    """login() returns False (never raises) on any exception during sign-in (D-13)."""
    plugin = AmazonPlugin(config=_make_config())
    plugin.driver = fake_browser
    fake_store = MagicMock()
    fake_store.get.side_effect = lambda key: "creds" if "EMAIL" in key or "PASSWORD" in key else None
    monkeypatch.setattr(_amazon_module, "get_store", lambda: fake_store)
    fake_browser.get = AsyncMock(side_effect=RuntimeError("network error"))
    result = await plugin.login()
    assert result is False


@pytest.mark.asyncio
async def test_login_returns_true_when_verified(monkeypatch, fake_browser):
    """login() returns True only after _verify_login_generic confirms (D-12)."""
    plugin = AmazonPlugin(config=_make_config())
    plugin.driver = fake_browser
    fake_store = MagicMock()
    fake_store.get.side_effect = lambda key: "creds" if "EMAIL" in key or "PASSWORD" in key else None
    monkeypatch.setattr(_amazon_module, "get_store", lambda: fake_store)
    # No MFA form present -- skip the OTP wait branch. Passkey wait is always
    # hit in the happy path -- stub it out so the test doesn't block on the
    # real 300s asyncio.wait_for guard (never fires in this fake-browser test).
    plugin._wait_user_action = AsyncMock()
    fake_browser.get.return_value.select = AsyncMock(
        side_effect=lambda selector, timeout=10: None
        if selector == "#auth-mfa-form"
        else MagicMock(send_keys=AsyncMock(), click=AsyncMock())
    )
    plugin._verify_login_generic = AsyncMock(return_value=True)
    result = await plugin.login()
    assert result is True
    plugin._verify_login_generic.assert_awaited_once_with(ANY, "/ap/signin", "#ap_email")


@pytest.mark.asyncio
async def test_login_returns_false_when_verification_fails(monkeypatch, fake_browser):
    """login() returns False when _verify_login_generic cannot confirm success (D-13)."""
    plugin = AmazonPlugin(config=_make_config())
    plugin.driver = fake_browser
    fake_store = MagicMock()
    fake_store.get.side_effect = lambda key: "creds" if "EMAIL" in key or "PASSWORD" in key else None
    monkeypatch.setattr(_amazon_module, "get_store", lambda: fake_store)
    plugin._wait_user_action = AsyncMock()
    fake_browser.get.return_value.select = AsyncMock(
        side_effect=lambda selector, timeout=10: None
        if selector == "#auth-mfa-form"
        else MagicMock(send_keys=AsyncMock(), click=AsyncMock())
    )
    plugin._verify_login_generic = AsyncMock(return_value=False)
    result = await plugin.login()
    assert result is False


@pytest.mark.asyncio
async def test_login_save_session_called_only_after_verification(monkeypatch, fake_browser):
    """save_session() must be called only after _verify_login_generic confirms success."""
    plugin = AmazonPlugin(config=_make_config())
    plugin.driver = fake_browser
    fake_store = MagicMock()
    fake_store.get.side_effect = lambda key: "creds" if "EMAIL" in key or "PASSWORD" in key else None
    monkeypatch.setattr(_amazon_module, "get_store", lambda: fake_store)
    plugin._wait_user_action = AsyncMock()
    fake_browser.get.return_value.select = AsyncMock(
        side_effect=lambda selector, timeout=10: None
        if selector == "#auth-mfa-form"
        else MagicMock(send_keys=AsyncMock(), click=AsyncMock())
    )
    plugin._verify_login_generic = AsyncMock(return_value=False)
    plugin.save_session = AsyncMock()
    result = await plugin.login()
    assert result is False
    plugin.save_session.assert_not_awaited()


@pytest.mark.asyncio
async def test_auto_buy_sets_checkout_stage_login_before_login_call(fake_browser):
    """auto_buy sets _checkout_stage='login' immediately before calling login() (Amazon:
    login precedes DOM interaction, Pitfall 3)."""
    cfg = MagicMock()
    cfg.debug.test_mode = False
    cfg.debug.monitor_only = False
    cfg.checkout.step_timeout_secs = 30
    cfg.available.items = []

    plugin = AmazonPlugin(config=cfg)
    plugin.driver = fake_browser
    stage_at_login_call = {}

    async def _fake_login():
        stage_at_login_call["stage"] = plugin._checkout_stage
        return True

    plugin.login = _fake_login
    plugin.place_order_guarded = AsyncMock(return_value=True)

    with patch("models.mark_place_order_attempted_sync"):
        result = await plugin.auto_buy("https://www.amazon.com/dp/B00TEST")

    assert stage_at_login_call.get("stage") == "login"
    assert result is True


@pytest.mark.asyncio
async def test_auto_buy_aborts_on_failed_login(fake_browser):
    """auto_buy returns False and never reaches place-order when login() returns False (D-15)."""
    cfg = MagicMock()
    cfg.debug.test_mode = False
    cfg.debug.monitor_only = False
    cfg.checkout.step_timeout_secs = 30
    cfg.available.items = []

    plugin = AmazonPlugin(config=cfg)
    plugin.driver = fake_browser
    plugin.login = AsyncMock(return_value=False)
    plugin.place_order_guarded = AsyncMock(return_value=True)

    result = await plugin.auto_buy("https://www.amazon.com/dp/B00TEST")

    assert result is False
    plugin.place_order_guarded.assert_not_awaited()
