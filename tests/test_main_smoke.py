"""Source-grep + AST smoke tests for main.py integration invariants.

Phase 1 (01-06): legacy invariants on imports + monkey-patch absence.
Phase 2 (02-04): registry integration assertions and hard-cut of legacy bots.
"""
import ast
import pathlib


MAIN_FILE = pathlib.Path("main.py")


def _src():
    return MAIN_FILE.read_text(encoding="utf-8")


def _main_ast():
    return ast.parse(MAIN_FILE.read_text(encoding="utf-8"))


def _walk_funcs(tree, name):
    return [
        n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name
    ]


# --- Phase 1 invariants (unchanged) ---

def test_no_stdout_monkey_patch():
    assert "sys.stdout = open(os.devnull" not in _src(), "INFRA-03"


def test_no_stderr_monkey_patch():
    assert "sys.stderr = open(os.devnull" not in _src(), "INFRA-03"


def test_imports_appconfig():
    assert "from config_schema import AppConfig" in _src()


def test_imports_collect_cvvs():
    assert "from credentials import collect_cvvs" in _src()


def test_imports_configure_logger():
    assert "from logger import configure" in _src(), "logger.configure must be imported"


def test_python_version_guard():
    src = _src()
    assert "sys.version_info < (3, 11)" in src
    assert "3.11+" in src or "3.11" in src


def test_no_old_app_credential_reads():
    forbidden = [
        "config['app']['bb_email']",
        "config['app']['bb_password']",
        "config['app']['bb_cvv']",
        "config['app']['amz_email']",
        "config['app']['amz_pwd']",
    ]
    src = pathlib.Path("main.py").read_text(encoding="utf-8")
    for needle in forbidden:
        assert needle not in src, f"main.py still contains {needle!r}"


# --- Phase 2 (02-04) registry integration + hard cut ---

def test_amazon_bot_module_removed():
    assert pathlib.Path("amazon_bot.py").exists() is False, \
        "D-02 hard cut: amazon_bot.py must be removed"


def test_bestbuy_bot_module_removed():
    assert pathlib.Path("bestbuy_bot.py").exists() is False, \
        "D-02 hard cut: bestbuy_bot.py must be removed"


def test_main_imports_plugin_registry():
    tree = _main_ast()
    matches = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom) and n.module == "plugin_registry"
    ]
    assert len(matches) >= 1, "main.py must import from plugin_registry"


def test_main_does_not_import_legacy_bots():
    tree = _main_ast()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            assert n.module not in {"amazon_bot", "bestbuy_bot"}, (
                f"Legacy import found: from {n.module} import ..."
            )


def test_main_has_no_handle_amazon():
    tree = _main_ast()
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef):
            assert n.name not in {"_handle_amazon", "_handle_bestbuy"}, (
                f"Legacy helper {n.name} still defined in main.py"
            )


def _calls_named(scope, target_name):
    found = []
    for n in ast.walk(scope):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == target_name:
            found.append(n)
    return found


def test_main_calls_discover():
    tree = _main_ast()
    mains = _walk_funcs(tree, "main")
    assert mains, "main() function must exist"
    # Phase 4: discover_async replaces discover (D-04 stagger).
    assert (
        _calls_named(mains[0], "discover")
        or _calls_named(mains[0], "discover_async")
    ), "main() must call discover(...) or discover_async(...)"


def test_main_calls_verify_coverage():
    tree = _main_ast()
    mains = _walk_funcs(tree, "main")
    assert mains, "main() function must exist"
    assert _calls_named(mains[0], "verify_coverage"), \
        "main() must call verify_coverage(...)"


def test_main_calls_route_url():
    tree = _main_ast()
    assert _calls_named(tree, "route_url"), \
        "main.py must call route_url(...) somewhere"


def test_main_no_amazon_string_dispatch():
    src = _src()
    assert '"amazon.com" in link' not in src, \
        "Legacy amazon.com string dispatch must be removed"
    assert '"bestbuy.com" in link' not in src, \
        "Legacy bestbuy.com string dispatch must be removed"


def test_main_login_at_startup_loop():
    tree = _main_ast()
    mains = _walk_funcs(tree, "main")
    assert mains, "main() function must exist"
    main_node = mains[0]

    has_attr = any(
        isinstance(n, ast.Attribute) and n.attr == "login_at_startup"
        for n in ast.walk(main_node)
    )
    has_login_call = any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "login"
        for n in ast.walk(main_node)
    )
    assert has_attr, "main() must reference plugin.login_at_startup (D-03)"
    assert has_login_call, "main() must call plugin.login(...) (D-03)"


# --- Phase 4 additions: async refactor smoke ---

def test_mainIsAsyncFunctionDef():
    """Phase 4: main() must be `async def`, not `def`."""
    tree = _main_ast()
    mainFn = next(
        (n for n in ast.walk(tree)
         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "main"),
        None,
    )
    assert isinstance(mainFn, ast.AsyncFunctionDef), "main must be an async function"


def test_mainImportsDiscoverAsync():
    tree = _main_ast()
    foundDiscoverAsync = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "plugin_registry":
            for alias in node.names:
                if alias.name == "discover_async":
                    foundDiscoverAsync = True
    assert foundDiscoverAsync, "main.py must import discover_async from plugin_registry"


def test_mainImportsTaskGroupViaAsyncio():
    src = _src()
    assert "asyncio.TaskGroup" in src or "TaskGroup" in src
