"""Tests for plugin reCAPTCHA solve path + manual-pause fallback (ANTI-06, Plan 03).

Covers: Amazon + BestBuy solve-or-pause logic, WAF graceful fallback, token
validation, and non-blocking timeout wrapper. All solver + browser calls are
mocked -- no real HTTP or browser launched.
"""

import asyncio
import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module loading
# ---------------------------------------------------------------------------

_AMAZON_PATH = Path(__file__).parent.parent / "plugins" / "shopbot_plugin_amazon.py"
_BESTBUY_PATH = Path(__file__).parent.parent / "plugins" / "shopbot_plugin_bestbuy.py"


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_amazon_mod = _load_module(_AMAZON_PATH, "shopbot_plugin_amazon_cp")
_bestbuy_mod = _load_module(_BESTBUY_PATH, "shopbot_plugin_bestbuy_cp")

AmazonPlugin = _amazon_mod.AmazonPlugin
BestBuyPlugin = _bestbuy_mod.BestBuyPlugin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_solver(can=True, token="VALID_TOKEN_ABCDEFG"):
    """Return a mock CaptchaSolver."""
    solver = MagicMock()
    solver.can_solve.return_value = can
    solver.solve_recaptcha.return_value = token
    return solver


def _make_tab(sitekey="k_abc123", body="normal page", goku=None, evaluate_side_effect=None):
    """Return an AsyncMock tab.

    evaluate returns values in order:
      1st call: sitekey (or empty string)
      2nd call: gokuProps probe (None = not WAF)
      3rd call: injection (not checked by default)

    Pass evaluate_side_effect to override with a custom side_effect list.
    """
    tab = MagicMock()
    tab.select = AsyncMock(return_value=MagicMock())
    tab.find = AsyncMock(return_value=MagicMock())

    if evaluate_side_effect is not None:
        tab.evaluate = AsyncMock(side_effect=evaluate_side_effect)
    else:
        # WAF probe comes first (gokuProps), then sitekey, then inject
        # Actually the order in _solve_or_pause is: WAF probe, then sitekey, then inject
        tab.evaluate = AsyncMock(side_effect=[
            goku,       # WAF probe
            sitekey,    # sitekey extraction
            None,       # injection (return value not checked)
        ])

    tab.evaluate.return_value = None  # fallback if side_effect exhausted
    return tab


def _make_amazon_plugin(solver=None, config=None):
    plugin = AmazonPlugin(config=config)
    plugin._captcha_solver = solver
    return plugin


def _make_bestbuy_plugin(solver=None, config=None):
    plugin = BestBuyPlugin(config=config)
    plugin._captcha_solver = solver
    return plugin


# ---------------------------------------------------------------------------
# Amazon: solver=None -> manual pause (no solve attempted)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_amazon_solver_none_falls_to_manual_pause():
    """CAPTCHA detected + solver is None -> _wait_user_action called, solve NOT called."""
    plugin = _make_amazon_plugin(solver=None)

    wait_called = []

    async def _fake_wait(event, msg):
        wait_called.append(msg)

    with patch.object(plugin, "_wait_user_action", side_effect=_fake_wait):
        tab = MagicMock()
        await plugin._solve_or_pause(tab, "https://amazon.com/dp/TEST")

    assert len(wait_called) == 1, "_wait_user_action must be called once"


# ---------------------------------------------------------------------------
# Amazon: solver.can_solve() False -> manual pause
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_amazon_solver_cannot_solve_falls_to_manual_pause():
    """solver.can_solve() is False (cap/zero-balance) -> manual pause, solve NOT called."""
    solver = _make_solver(can=False)
    plugin = _make_amazon_plugin(solver=solver)

    wait_called = []

    async def _fake_wait(event, msg):
        wait_called.append(msg)

    with patch.object(plugin, "_wait_user_action", side_effect=_fake_wait):
        tab = MagicMock()
        await plugin._solve_or_pause(tab, "https://amazon.com/dp/TEST")

    assert len(wait_called) == 1
    solver.solve_recaptcha.assert_not_called()


# ---------------------------------------------------------------------------
# Amazon: WAF (gokuProps present) -> INFO log + manual pause, solve_amazon_waf NOT called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_amazon_waf_detected_falls_to_manual_pause():
    """window.gokuProps present -> INFO log + manual pause; solve_amazon_waf NOT called."""
    solver = _make_solver()
    plugin = _make_amazon_plugin(solver=solver)

    wait_called = []

    async def _fake_wait(event, msg):
        wait_called.append(msg)

    # WAF probe returns JSON string (truthy)
    tab = _make_tab(goku='{"key":"k","iv":"i","context":"c"}')

    with patch.object(plugin, "_wait_user_action", side_effect=_fake_wait):
        await plugin._solve_or_pause(tab, "https://amazon.com/dp/TEST")

    assert len(wait_called) == 1, "_wait_user_action must be called on WAF"
    assert not hasattr(solver, "solve_amazon_waf") or not solver.solve_amazon_waf.called, (
        "solve_amazon_waf must NOT be called this phase"
    )


# ---------------------------------------------------------------------------
# Amazon: empty sitekey -> manual pause, solve_recaptcha NOT called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_amazon_empty_sitekey_falls_to_manual_pause():
    """Empty sitekey extracted -> _wait_user_action called, solve_recaptcha NOT called."""
    solver = _make_solver()
    plugin = _make_amazon_plugin(solver=solver)

    wait_called = []

    async def _fake_wait(event, msg):
        wait_called.append(msg)

    # WAF probe None (not WAF), sitekey empty
    tab = _make_tab(sitekey="", goku=None)

    with patch.object(plugin, "_wait_user_action", side_effect=_fake_wait):
        await plugin._solve_or_pause(tab, "https://amazon.com/dp/TEST")

    assert len(wait_called) == 1
    solver.solve_recaptcha.assert_not_called()


# ---------------------------------------------------------------------------
# Amazon: successful solve -> token injected, _wait_user_action NOT called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_amazon_successful_solve_injects_token_no_manual_pause():
    """Successful solve -> token injected via tab.evaluate, _wait_user_action NOT called."""
    solver = _make_solver(token="VALIDTOKEN123456")
    plugin = _make_amazon_plugin(solver=solver)

    wait_called = []

    async def _fake_wait(event, msg):
        wait_called.append(msg)

    tab = _make_tab(sitekey="k_abc", goku=None)
    injection_calls = []

    original_evaluate = tab.evaluate.side_effect

    async def _capture_evaluate(js):
        if original_evaluate is not None:
            results = list(original_evaluate)
            if results:
                return results.pop(0)
        return None

    with patch.object(plugin, "_wait_user_action", side_effect=_fake_wait):
        tab2 = MagicMock()
        tab2.evaluate = AsyncMock(side_effect=[None, "k_abc", None])  # WAF=None, sitekey, inject
        await plugin._solve_or_pause(tab2, "https://amazon.com/dp/TEST")

    assert len(wait_called) == 0, "_wait_user_action must NOT be called on success"
    # Injection call must have been made (3rd evaluate with token)
    assert tab2.evaluate.call_count >= 3, "tab.evaluate must be called at least 3 times (WAF, sitekey, inject)"


# ---------------------------------------------------------------------------
# Amazon: solve raises Exception -> manual pause (no silent skip)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_amazon_solve_exception_falls_to_manual_pause():
    """solve_recaptcha raises RuntimeError -> manual pause, no silent skip."""
    solver = _make_solver()
    solver.solve_recaptcha.side_effect = RuntimeError("2captcha API error")
    plugin = _make_amazon_plugin(solver=solver)

    wait_called = []

    async def _fake_wait(event, msg):
        wait_called.append(msg)

    tab = MagicMock()
    tab.evaluate = AsyncMock(side_effect=[None, "k_abc", None])

    with patch.object(plugin, "_wait_user_action", side_effect=_fake_wait):
        await plugin._solve_or_pause(tab, "https://amazon.com/dp/TEST")

    assert len(wait_called) == 1, "_wait_user_action must be called on solve error"


# ---------------------------------------------------------------------------
# Amazon: asyncio.TimeoutError -> manual pause (no silent skip)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_amazon_solve_timeout_falls_to_manual_pause():
    """asyncio.TimeoutError from run_in_executor -> manual pause, no silent skip."""
    solver = _make_solver()
    plugin = _make_amazon_plugin(solver=solver)

    wait_called = []

    async def _fake_wait(event, msg):
        wait_called.append(msg)

    tab = MagicMock()

    # Patch run_in_executor to raise TimeoutError via asyncio.timeout
    async def _fake_solve_or_pause_timeout(tab, pageurl):
        # Simulate timeout by patching _do_solve to raise TimeoutError
        pass

    # Use a real tab with sitekey present, but patch the executor to simulate timeout
    tab.evaluate = AsyncMock(side_effect=[None, "k_abc"])  # WAF=None, sitekey

    loop = asyncio.get_event_loop()

    original_run_in_executor = loop.run_in_executor

    async def _timeout_executor(executor, fn, *args):
        raise asyncio.TimeoutError()

    with patch.object(plugin, "_wait_user_action", side_effect=_fake_wait), \
         patch.object(loop, "run_in_executor", side_effect=_timeout_executor):
        await plugin._solve_or_pause(tab, "https://amazon.com/dp/TEST")

    assert len(wait_called) == 1, "_wait_user_action must be called on TimeoutError"


# ---------------------------------------------------------------------------
# Amazon: token with quote char -> rejected, manual pause
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_amazon_token_with_quote_rejected():
    """Token containing single-quote is rejected (T-14-inject) -> manual pause."""
    solver = _make_solver(token="TOKEN'WITH'QUOTE")
    plugin = _make_amazon_plugin(solver=solver)

    wait_called = []
    inject_calls = []

    async def _fake_wait(event, msg):
        wait_called.append(msg)

    tab = MagicMock()
    tab.evaluate = AsyncMock(side_effect=[None, "k_abc", None])

    with patch.object(plugin, "_wait_user_action", side_effect=_fake_wait):
        await plugin._solve_or_pause(tab, "https://amazon.com/dp/TEST")

    assert len(wait_called) == 1, "Token with quote must trigger manual pause"
    # Injection must NOT have been called with the bad token
    inject_js_calls = [
        call for call in tab.evaluate.call_args_list
        if "g-recaptcha-response" in str(call)
    ]
    assert len(inject_js_calls) == 0, "Injection JS must NOT be called with quote-bearing token"


# ---------------------------------------------------------------------------
# Amazon: token with newline -> rejected, manual pause
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_amazon_token_with_newline_rejected():
    """Token containing newline is rejected (T-14-inject) -> manual pause."""
    solver = _make_solver(token="TOKEN\nWITH\nNEWLINE")
    plugin = _make_amazon_plugin(solver=solver)

    wait_called = []

    async def _fake_wait(event, msg):
        wait_called.append(msg)

    tab = MagicMock()
    tab.evaluate = AsyncMock(side_effect=[None, "k_abc", None])

    with patch.object(plugin, "_wait_user_action", side_effect=_fake_wait):
        await plugin._solve_or_pause(tab, "https://amazon.com/dp/TEST")

    assert len(wait_called) == 1, "Token with newline must trigger manual pause"


# ---------------------------------------------------------------------------
# Amazon: solve_amazon_waf NOT called at all (WAF deferred assertion)
# ---------------------------------------------------------------------------


def test_amazon_source_does_not_call_solve_amazon_waf():
    """solve_amazon_waf must NOT be called from the plugin source this phase."""
    source = _AMAZON_PATH.read_text()
    # The method may be referenced in a comment; only catch actual call sites
    import re
    call_sites = re.findall(r"(?<!#).*solve_amazon_waf\s*\(", source)
    assert len(call_sites) == 0, (
        f"solve_amazon_waf() must not be called this phase; found: {call_sites}"
    )


# ---------------------------------------------------------------------------
# Amazon: asyncio.timeout(120) present in source
# ---------------------------------------------------------------------------


def test_amazon_source_has_asyncio_timeout():
    """asyncio.timeout(120) must be present in the Amazon plugin source."""
    source = _AMAZON_PATH.read_text()
    assert "asyncio.timeout(120)" in source, (
        "asyncio.timeout(120) must be present in shopbot_plugin_amazon.py"
    )


# ---------------------------------------------------------------------------
# Amazon: str(exc) NOT present in source (Pitfall 6 guard)
# ---------------------------------------------------------------------------


def test_amazon_source_no_str_exc():
    """str(exc) must not appear in Amazon plugin source (Pitfall 6)."""
    source = _AMAZON_PATH.read_text()
    import re
    # Catch 'str(exc', str(e)', etc. but allow comments
    lines = source.splitlines()
    violations = [
        (i + 1, ln)
        for i, ln in enumerate(lines)
        if re.search(r"str\(\s*exc", ln) and not ln.lstrip().startswith("#")
    ]
    assert not violations, (
        "str(exc) found in Amazon plugin:\n" +
        "\n".join(f"  line {n}: {l}" for n, l in violations)
    )


# ===========================================================================
# BestBuy tests
# ===========================================================================


# ---------------------------------------------------------------------------
# BestBuy: has captcha_event attribute
# ---------------------------------------------------------------------------


def test_bestbuy_has_captcha_event():
    """BestBuyPlugin must have a captcha_event asyncio.Event in __init__."""
    plugin = BestBuyPlugin(config=None)
    assert hasattr(plugin, "captcha_event"), "BestBuyPlugin must have captcha_event"
    assert isinstance(plugin.captcha_event, asyncio.Event), (
        "captcha_event must be asyncio.Event"
    )


# ---------------------------------------------------------------------------
# BestBuy: has _wait_user_action
# ---------------------------------------------------------------------------


def test_bestbuy_has_wait_user_action():
    """BestBuyPlugin must define _wait_user_action coroutine method."""
    plugin = BestBuyPlugin(config=None)
    assert hasattr(plugin, "_wait_user_action"), "BestBuyPlugin must have _wait_user_action"
    assert asyncio.iscoroutinefunction(plugin._wait_user_action), (
        "_wait_user_action must be async def"
    )


# ---------------------------------------------------------------------------
# BestBuy: solver=None -> manual pause
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bestbuy_solver_none_falls_to_manual_pause():
    """BestBuy: solver None -> _wait_user_action called."""
    plugin = _make_bestbuy_plugin(solver=None)

    wait_called = []

    async def _fake_wait(event, msg):
        wait_called.append(msg)

    with patch.object(plugin, "_wait_user_action", side_effect=_fake_wait):
        tab = MagicMock()
        await plugin._solve_or_pause(tab, "https://bestbuy.com/site/TEST")

    assert len(wait_called) == 1


# ---------------------------------------------------------------------------
# BestBuy: empty sitekey -> manual pause, solve_recaptcha NOT called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bestbuy_empty_sitekey_falls_to_manual_pause():
    """BestBuy: empty sitekey (non-reCAPTCHA challenge) -> manual pause."""
    solver = _make_solver()
    plugin = _make_bestbuy_plugin(solver=solver)

    wait_called = []

    async def _fake_wait(event, msg):
        wait_called.append(msg)

    tab = MagicMock()
    # BestBuy _solve_or_pause: no WAF probe, just sitekey then fallback
    tab.evaluate = AsyncMock(side_effect=["", None])  # sitekey empty

    with patch.object(plugin, "_wait_user_action", side_effect=_fake_wait):
        await plugin._solve_or_pause(tab, "https://bestbuy.com/site/TEST")

    assert len(wait_called) == 1
    solver.solve_recaptcha.assert_not_called()


# ---------------------------------------------------------------------------
# BestBuy: successful solve -> token injected, no manual pause
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bestbuy_successful_solve_injects_token_no_pause():
    """BestBuy: successful reCAPTCHA solve -> injected, _wait_user_action NOT called."""
    solver = _make_solver(token="BB_VALID_TOKEN_XYZ")
    plugin = _make_bestbuy_plugin(solver=solver)

    wait_called = []

    async def _fake_wait(event, msg):
        wait_called.append(msg)

    tab = MagicMock()
    tab.evaluate = AsyncMock(side_effect=["k_bb_site", None, None])  # sitekey, inject result, extra

    with patch.object(plugin, "_wait_user_action", side_effect=_fake_wait):
        await plugin._solve_or_pause(tab, "https://bestbuy.com/site/TEST")

    assert len(wait_called) == 0, "_wait_user_action must NOT be called on success"
    assert tab.evaluate.call_count >= 2, "tab.evaluate called for sitekey + injection"


# ---------------------------------------------------------------------------
# BestBuy: asyncio.timeout(120) present in source
# ---------------------------------------------------------------------------


def test_bestbuy_source_has_asyncio_timeout():
    """asyncio.timeout(120) must be present in the BestBuy plugin source."""
    source = _BESTBUY_PATH.read_text()
    assert "asyncio.timeout(120)" in source, (
        "asyncio.timeout(120) must be present in shopbot_plugin_bestbuy.py"
    )


# ---------------------------------------------------------------------------
# BestBuy: str(exc) NOT present on new code paths
# ---------------------------------------------------------------------------


def test_bestbuy_source_no_str_exc():
    """str(exc) must not appear in BestBuy plugin source (Pitfall 6)."""
    source = _BESTBUY_PATH.read_text()
    import re
    lines = source.splitlines()
    violations = [
        (i + 1, ln)
        for i, ln in enumerate(lines)
        if re.search(r"str\(\s*exc", ln) and not ln.lstrip().startswith("#")
    ]
    assert not violations, (
        "str(exc) found in BestBuy plugin:\n" +
        "\n".join(f"  line {n}: {l}" for n, l in violations)
    )


# ===========================================================================
# CR-02 regression: token injection uses json.dumps -- no JS breakout possible
# ===========================================================================


@pytest.mark.asyncio
async def test_amazon_token_with_backslash_rejected():
    """Token containing backslash is rejected before injection (CR-02 regression)."""
    solver = _make_solver(token=r"TOKEN\WITH\BACKSLASH")
    plugin = _make_amazon_plugin(solver=solver)

    wait_called = []

    async def _fake_wait(event, msg):
        wait_called.append(msg)

    tab = MagicMock()
    tab.evaluate = AsyncMock(side_effect=[None, "k_abc", None])

    with patch.object(plugin, "_wait_user_action", side_effect=_fake_wait):
        await plugin._solve_or_pause(tab, "https://amazon.com/dp/TEST")

    assert len(wait_called) == 1, "Token with backslash must trigger manual pause"
    inject_js_calls = [
        call for call in tab.evaluate.call_args_list
        if "g-recaptcha-response" in str(call)
    ]
    assert len(inject_js_calls) == 0, "Injection JS must NOT be called with backslash token"


@pytest.mark.asyncio
async def test_amazon_inject_token_uses_json_dumps():
    """_inject_token must embed token via json.dumps so special chars are escaped (CR-02)."""
    import json
    plugin = _make_amazon_plugin()
    tab = MagicMock()
    tab.evaluate = AsyncMock(return_value=None)

    token_with_special = 'hello"world'
    await plugin._inject_token(tab, token_with_special)

    assert tab.evaluate.called
    injected_js = tab.evaluate.call_args[0][0]
    safe = json.dumps(token_with_special)
    assert safe in injected_js, (
        f"json.dumps output {safe!r} must appear in injected JS; got: {injected_js!r}"
    )
    # The raw unescaped form must NOT appear as a bare string
    assert f"'{token_with_special}'" not in injected_js


@pytest.mark.asyncio
async def test_bestbuy_token_with_backslash_rejected():
    """BestBuy: token containing backslash is rejected before injection (CR-02 regression)."""
    solver = _make_solver(token=r"TOKEN\BACKSLASH")
    plugin = _make_bestbuy_plugin(solver=solver)

    wait_called = []

    async def _fake_wait(event, msg):
        wait_called.append(msg)

    tab = MagicMock()
    tab.evaluate = AsyncMock(side_effect=["k_bb", None, None])

    with patch.object(plugin, "_wait_user_action", side_effect=_fake_wait):
        await plugin._solve_or_pause(tab, "https://bestbuy.com/site/TEST")

    assert len(wait_called) == 1, "BestBuy: token with backslash must trigger manual pause"


@pytest.mark.asyncio
async def test_bestbuy_inject_token_uses_json_dumps():
    """BestBuy _inject_token must embed token via json.dumps (CR-02)."""
    import json
    plugin = _make_bestbuy_plugin()
    tab = MagicMock()
    tab.evaluate = AsyncMock(return_value=None)

    token_with_special = "back\\slash"
    await plugin._inject_token(tab, token_with_special)

    assert tab.evaluate.called
    injected_js = tab.evaluate.call_args[0][0]
    safe = json.dumps(token_with_special)
    assert safe in injected_js, (
        f"json.dumps output {safe!r} must appear in injected BestBuy JS; got: {injected_js!r}"
    )
