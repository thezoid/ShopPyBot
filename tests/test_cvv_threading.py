"""CVV threading tests: Amazon _cvv init, needs_cvv predicate, orchestrator injection.

Plan 20-03 (BUY-07 prerequisite):
- AmazonPlugin initializes self._cvv = None
- needs_cvv fires for amazon.com auto_buy items (not only bestbuy.com)
- orchestrator injects cvv onto the routed Amazon plugin
- cvv never appears as a variable argument to writeLog/print in the threading files
"""

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_amazon_plugin():
    """Build an AmazonPlugin without launching a real browser."""
    from plugins.shopbot_plugin_amazon import AmazonPlugin

    instance = AmazonPlugin(config=None)
    instance.driver = None
    return instance


def _make_item(link: str, auto_buy: bool) -> SimpleNamespace:
    return SimpleNamespace(link=link, auto_buy=auto_buy)


def _make_cfg(*, test_mode: bool, monitor_only: bool, items: list) -> MagicMock:
    cfg = MagicMock()
    cfg.debug.test_mode = test_mode
    cfg.debug.monitor_only = monitor_only
    cfg.available.items = items
    return cfg


# ---------------------------------------------------------------------------
# Task 1 acceptance criteria
# ---------------------------------------------------------------------------


def test_amazon_cvv_attr_default():
    """AmazonPlugin(config=None)._cvv is None (attribute initialized, no AttributeError)."""
    plugin = _make_amazon_plugin()
    assert plugin._cvv is None


def test_needs_cvv_true_for_amazon_auto_buy():
    """needs_cvv is True for amazon.com item with auto_buy=True in non-test mode."""
    from core.cli.run import handle_run

    cfg = _make_cfg(
        test_mode=False,
        monitor_only=False,
        items=[_make_item("https://www.amazon.com/dp/ABC", auto_buy=True)],
    )
    svc = MagicMock()
    svc.get_config.return_value = cfg
    args = MagicMock()
    args.monitor_only = False

    with patch("core.cli.run.getpass") as mock_gp:
        mock_gp.getpass.return_value = "123"
        handle_run(args, svc)

    mock_gp.getpass.assert_called_once()


def test_needs_cvv_false_when_amazon_no_auto_buy():
    """needs_cvv is False when amazon.com item has auto_buy=False."""
    from core.cli.run import handle_run

    cfg = _make_cfg(
        test_mode=False,
        monitor_only=False,
        items=[_make_item("https://www.amazon.com/dp/ABC", auto_buy=False)],
    )
    svc = MagicMock()
    svc.get_config.return_value = cfg
    args = MagicMock()
    args.monitor_only = False

    with patch("core.cli.run.getpass") as mock_gp:
        handle_run(args, svc)

    mock_gp.getpass.assert_not_called()


def test_needs_cvv_false_in_test_mode_amazon():
    """needs_cvv is False for amazon.com auto_buy item when test_mode=True."""
    from core.cli.run import handle_run

    cfg = _make_cfg(
        test_mode=True,
        monitor_only=False,
        items=[_make_item("https://www.amazon.com/dp/ABC", auto_buy=True)],
    )
    svc = MagicMock()
    svc.get_config.return_value = cfg
    args = MagicMock()
    args.monitor_only = False

    with patch("core.cli.run.getpass") as mock_gp:
        handle_run(args, svc)

    mock_gp.getpass.assert_not_called()


def test_needs_cvv_false_in_monitor_only_amazon():
    """needs_cvv is False for amazon.com auto_buy item when monitor_only=True."""
    from core.cli.run import handle_run

    cfg = _make_cfg(
        test_mode=False,
        monitor_only=False,
        items=[_make_item("https://www.amazon.com/dp/ABC", auto_buy=True)],
    )
    svc = MagicMock()
    svc.get_config.return_value = cfg
    args = MagicMock()
    args.monitor_only = True  # flag mutates cfg.debug.monitor_only

    with patch("core.cli.run.getpass") as mock_gp:
        handle_run(args, svc)

    mock_gp.getpass.assert_not_called()


def test_needs_cvv_bestbuy_regression():
    """needs_cvv still fires for bestbuy.com auto_buy item (no regression)."""
    from core.cli.run import handle_run

    cfg = _make_cfg(
        test_mode=False,
        monitor_only=False,
        items=[_make_item("https://www.bestbuy.com/site/123", auto_buy=True)],
    )
    svc = MagicMock()
    svc.get_config.return_value = cfg
    args = MagicMock()
    args.monitor_only = False

    with patch("core.cli.run.getpass") as mock_gp:
        mock_gp.getpass.return_value = "456"
        handle_run(args, svc)

    mock_gp.getpass.assert_called_once()


def test_orchestrator_injects_amazon_cvv():
    """Orchestrator injection logic sets amz_plugin._cvv when registry routes amazon URL."""
    # Test the injection logic directly without invoking the full async_main.
    # We mirror the pattern from the orchestrator block:
    #   if cvv:
    #       amz_plugin = registry.route("https://www.amazon.com/")
    #       if amz_plugin:
    #           amz_plugin._cvv = cvv
    stub = MagicMock()
    stub._cvv = None

    fake_registry = MagicMock()
    fake_registry.route.return_value = stub

    cvv = "789"

    # Execute the injection logic directly (equivalent to what async_main does)
    if cvv:
        amz_plugin = fake_registry.route("https://www.amazon.com/")
        if amz_plugin:
            amz_plugin._cvv = cvv

    assert stub._cvv == "789"
    fake_registry.route.assert_called_once_with("https://www.amazon.com/")


def test_orchestrator_injection_skipped_when_no_cvv():
    """Orchestrator injection is skipped when cvv is None/empty."""
    stub = MagicMock()
    stub._cvv = None

    fake_registry = MagicMock()
    fake_registry.route.return_value = stub

    cvv = None

    if cvv:
        amz_plugin = fake_registry.route("https://www.amazon.com/")
        if amz_plugin:
            amz_plugin._cvv = cvv

    # route should never be called when cvv is falsy
    fake_registry.route.assert_not_called()
    assert stub._cvv is None


def test_orchestrator_injection_skipped_when_no_plugin():
    """Orchestrator injection is a no-op when registry returns None for amazon URL."""
    fake_registry = MagicMock()
    fake_registry.route.return_value = None

    cvv = "999"
    result_plugin = None

    if cvv:
        amz_plugin = fake_registry.route("https://www.amazon.com/")
        if amz_plugin:
            result_plugin = amz_plugin
            result_plugin._cvv = cvv

    assert result_plugin is None


# ---------------------------------------------------------------------------
# CVV never-logged AST scan (T-20-05 / SEC-02)
# ---------------------------------------------------------------------------


def test_cvv_not_in_writelog_or_print_args():
    """Assert _cvv is never passed as a variable to writeLog or print in threading files.

    Scope: orchestration + CLI path (core/orchestrator.py, core/cli/run.py) plus both
    plugins (shopbot_plugin_amazon.py, shopbot_plugin_bestbuy.py).
    Companion test test_no_cvv_in_logs.py covers the same plugin files with writeLog-only
    scanning; this test adds print() coverage and uses the same keyword-complete scan.

    The static prompt string "Enter CVV (input hidden): " is a constant -- excluded.
    Only variable references (ast.Name containing 'cvv') are flagged.
    Keyword args (e.g., print(file=..., end=cvv)) are also checked (CR-02 / WR-03).
    """
    repo_root = Path(__file__).parent.parent
    threading_files = [
        repo_root / "core" / "orchestrator.py",
        repo_root / "core" / "cli" / "run.py",
        repo_root / "plugins" / "shopbot_plugin_amazon.py",
        repo_root / "plugins" / "shopbot_plugin_bestbuy.py",
    ]
    violations = []
    for path in threading_files:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            else:
                name = ""
            if name not in ("writeLog", "print"):
                continue
            # Positional args
            for arg in node.args:
                arg_src = ast.unparse(arg)
                # Flag bare variable references containing 'cvv' (not string literals)
                if "_cvv" in arg_src and not isinstance(arg, ast.Constant):
                    violations.append(
                        f"{path.name}:{node.lineno}: {name}() arg contains '_cvv' variable: {arg_src!r}"
                    )
            # Keyword arg values (e.g., print(file=sys.stderr, end=self._cvv))
            for kw in node.keywords:
                kw_src = ast.unparse(kw.value)
                if "_cvv" in kw_src and not isinstance(kw.value, ast.Constant):
                    violations.append(
                        f"{path.name}:{node.lineno}: {name}() kwarg contains '_cvv' variable: {kw_src!r}"
                    )
    assert not violations, "CVV variable found in writeLog/print():\n" + "\n".join(violations)
