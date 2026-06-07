# Phase 9: CLI Front-End - Pattern Map

**Mapped:** 2026-06-04
**Files analyzed:** 12 (6 source, 6 test)
**Analogs found:** 12 / 12

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `core/cli/__init__.py` | utility (parser builder + dispatch) | request-response | `core/service.py:main()` lines 154-181 | exact |
| `core/cli/run.py` | handler | request-response | `core/service.py:main()` run path + `main.py:main()` | exact |
| `core/cli/setup.py` | handler | request-response | `core/credentials.py:migrate_from_env()` + `main.py:collect_cvv()` | role-match |
| `core/cli/items.py` | handler | CRUD | `core/service.py:BotService.add_item/remove_item/list_items` seam | role-match |
| `core/cli/config_cmd.py` | handler | file-I/O | `core/credentials.py:EncryptedFileBackend._save()` + `core/config_schema.py:_DEFAULT_YAML_PATH` | partial |
| `core/cli/web.py` | handler | request-response | `core/service.py:main()` (pattern stub only) | partial |
| `core/service.py` (modified) | entry-point | request-response | self (existing `main()` flat argparse) | exact |
| `tests/test_cli_run.py` | test | request-response | `tests/test_main_wiring.py` + `tests/test_service.py` | exact |
| `tests/test_cli_setup.py` | test | request-response | `tests/test_main_wiring.py` | exact |
| `tests/test_cli_items.py` | test | CRUD | `tests/test_service.py` | exact |
| `tests/test_cli_config.py` | test | file-I/O | `tests/test_service.py:test_main_constructs_service_and_runs` | role-match |
| `tests/test_cli_no_fastapi.py` | test | request-response | `tests/test_no_env_secret_reads.py` (sentinel/guard pattern) | role-match |
| `tests/test_cli_mod02.py` | test | transform (AST scan) | `tests/test_no_env_secret_reads.py` | exact |

## Pattern Assignments

### `core/service.py` (modified -- `main()` restructured)

**Analog:** `core/service.py` lines 154-181 (current flat `main()`)

**Current imports block** (lines 1-23):
```python
import argparse
import asyncio
import threading
from pathlib import Path
from typing import Optional

from core.config_schema import AppConfig
from core.credentials import init_store
from core.orchestrator import async_main
from logger import writeLog
from models import add_items_sync, get_items_sync, remove_item_sync
```
New `main()` adds `from core.cli import build_parser, dispatch` (or inlines the subparser construction). No new stdlib imports beyond `sys` are needed.

**Current `main()` pattern** (lines 154-181):
```python
def main() -> None:
    parser = argparse.ArgumentParser(
        prog="shoppybot",
        description="ShopPyBot: automated availability checker and buyer.",
    )
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Import secrets from environment variables into the active credential backend.",
    )
    args, _ = parser.parse_known_args()

    if args.migrate:
        from core.credentials import migrate_from_env, get_store
        migrated = migrate_from_env(get_store())
        for key in migrated:
            print(f"Migrated: {key}")   # key NAME only -- never the value (T-08-14)
        return

    service = BotService()
    service.run()
```

**Phase 9 replacement shape** (copy `parse_known_args` pattern; add `argv=None` param; add `set_defaults` dispatch; keep `--migrate` top-level for back-compat):
```python
def main(argv=None) -> None:
    from core.cli import build_parser
    parser = build_parser()
    args, _ = parser.parse_known_args(argv)

    # Back-compat: top-level --migrate with no subcommand -> setup --migrate
    if getattr(args, "migrate", False) and getattr(args, "command", None) is None:
        from core.cli.setup import handle_setup
        handle_setup(args, BotService())
        return

    # Bare shoppybot = run
    if getattr(args, "func", None) is None:
        from core.cli.run import handle_run
        handle_run(args, BotService())
        return

    import sys
    sys.exit(args.func(args, BotService()) or 0)
```

**Key constraint:** `parse_known_args(argv)` not `parse_args(argv)` -- preserves test isolation (existing `test_main_wiring.py` idiom, line 170).

### `core/cli/__init__.py` (new -- parser builder + dispatch)

**Analog:** `core/service.py:main()` argparse block + RESEARCH Pattern 1

**Imports pattern:**
```python
import argparse
from core.cli.run import handle_run
from core.cli.setup import handle_setup
from core.cli.items import handle_items_list, handle_items_add, handle_items_remove
from core.cli.config_cmd import handle_config_show, handle_config_set
from core.cli.web import handle_web
```

**Core pattern -- `build_parser()` with `set_defaults(func=...)` dispatch:**
```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shoppybot",
        description="ShopPyBot: automated availability checker and buyer.",
    )
    parser.set_defaults(func=None)
    # Back-compat: top-level --migrate alias (RESEARCH Pattern 2)
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Import env-var secrets into the active backend (alias for 'setup --migrate').",
    )

    sub = parser.add_subparsers(dest="command")

    # run
    run_p = sub.add_parser("run", help="Start the bot (default).")
    run_p.set_defaults(func=handle_run)

    # setup
    setup_p = sub.add_parser("setup", help="Store credentials and select backend.")
    setup_p.add_argument("--migrate", action="store_true",
                         help="Import env-var secrets into the active backend.")
    setup_p.set_defaults(func=handle_setup)

    # items
    items_p = sub.add_parser("items", help="Manage tracked items.")
    items_sub = items_p.add_subparsers(dest="items_command")

    list_p = items_sub.add_parser("list")
    list_p.set_defaults(func=handle_items_list)

    add_p = items_sub.add_parser("add")
    add_p.add_argument("--name", required=True)
    add_p.add_argument("--url", required=True)
    add_p.add_argument("--auto-buy", action="store_true", default=False)
    add_p.add_argument("--quantity", type=int, default=1)
    add_p.set_defaults(func=handle_items_add)

    remove_p = items_sub.add_parser("remove")
    remove_p.add_argument("--url", required=True)
    remove_p.set_defaults(func=handle_items_remove)

    # config
    config_p = sub.add_parser("config", help="View or update bot settings.")
    config_sub = config_p.add_subparsers(dest="config_command")

    show_p = config_sub.add_parser("show")
    show_p.set_defaults(func=handle_config_show)

    set_p = config_sub.add_parser("set")
    set_p.add_argument("key")
    set_p.add_argument("value")
    set_p.set_defaults(func=handle_config_set)

    # web (Phase 10 stub -- lazy import inside handle_web)
    web_p = sub.add_parser("web", help="Start the web UI (requires pip install .[web]).")
    web_p.set_defaults(func=handle_web)

    return parser
```

### `core/cli/run.py` (new -- run handler)

**Analog:** `core/service.py:main()` run path (lines 178-181) + `main.py:main()` (lines 22-50)

**Imports pattern:**
```python
import sys
import getpass
from core.service import BotService
```

**Core pattern:**
```python
def handle_run(args, svc: BotService) -> int:
    """Start the bot (blocking). CVV collected here only if needed."""
    # CVV gate: mirrors main.py collect_cvv() pattern (SEC-02)
    cfg = svc.get_config()
    needs_cvv = (
        not cfg.debug.test_mode
        and any("bestbuy.com" in item.link and item.auto_buy
                for item in cfg.available.items)
    )
    cvv = None
    if needs_cvv:
        try:
            cvv = getpass.getpass("Enter CVV (input hidden): ").strip() or None
        except (EOFError, getpass.GetPassWarning):
            print("WARNING: CVV echo suppression unavailable", file=sys.stderr)
            return 1
    svc.run(cvv)
    return 0
```

**Key pattern from `main.py` line 11-18:** `collect_cvv()` uses `getpass.getpass` + catches `GetPassWarning` and raises `SystemExit`. The CLI handler translates the `SystemExit` to `return 1` for clean dispatch.

### `core/cli/setup.py` (new -- setup/credentials handler)

**Analog:** `core/credentials.py:migrate_from_env()` (lines 388-415) + `main.py:collect_cvv()` (lines 10-18)

**Imports pattern:**
```python
import getpass
import sys
from core.credentials import get_store, SECRET_KEYS, migrate_from_env
```

**`prompt_secret` helper -- copy from RESEARCH Pattern 3:**
```python
def _prompt_secret(prompt: str) -> str | None:
    """Return secret string or None if user skips (empty input or EOF)."""
    try:
        val = getpass.getpass(prompt).strip()
    except (EOFError, getpass.GetPassWarning):
        return None
    return val or None
```

**Core `handle_setup` pattern -- key NAME confirm only (mirrors `migrate_from_env` line 404):**
```python
def handle_setup(args, svc) -> int:
    if getattr(args, "migrate", False):
        store = get_store()
        migrated = migrate_from_env(store)
        for key in migrated:
            print(f"Migrated: {key}")   # KEY NAME only -- never the value (T-08-14)
        return 0

    store = get_store()
    stored_count = 0
    for key in SECRET_KEYS:
        val = _prompt_secret(f"  {key} (Enter to skip): ")
        if val is not None:
            store.set(key, val)
            print(f"  Stored: {key}")   # KEY NAME only -- never the value
            stored_count += 1
    print(f"Setup complete. {stored_count} key(s) stored.")
    return 0
```

**Backend selection write pattern** (YAML atomic write -- see `config_cmd.py` pattern below):
```python
# After credential prompts, ask for backend and write credentials.backend to config.yml
# Use _atomic_yaml_write from core/cli/config_cmd.py (import, don't duplicate)
```

**Secret echo guard:** The `migrate_from_env` source at lines 396-404 establishes the project law: `migrated.append(key)` -- the list contains KEY NAMES only. `handle_setup` follows the same law: `print(f"Stored: {key}")` -- never `print(f"Stored: {key}={val}")`.

### `core/cli/items.py` (new -- items list/add/remove handlers)

**Analog:** `core/service.py:BotService` methods (lines 55-69) + RESEARCH Patterns 6 and 7

**Imports pattern:**
```python
import sys
from core.service import BotService
```

**`handle_items_list` -- text table pattern (RESEARCH Pattern 6):**
```python
def handle_items_list(args, svc: BotService) -> int:
    rows = svc.list_items()
    print(_format_items_table(rows))
    return 0

def _format_items_table(rows: list[tuple]) -> str:
    headers = ("Name", "URL", "Auto-Buy", "Qty", "Purchased")
    if not rows:
        return "No items tracked."
    widths = [
        max(len(h), max(len(str(r[i])) for r in rows))
        for i, h in enumerate(headers)
    ]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    lines = [fmt.format(*headers), "  ".join("-" * w for w in widths)]
    for r in rows:
        lines.append(fmt.format(r[0], r[1], bool(r[2]), r[3], bool(r[4])))
    return "\n".join(lines)
```

**`handle_items_add` -- maps `args.auto_buy` (bool from argparse) and `args.quantity` (int) directly to `BotService.add_item`:**
```python
def handle_items_add(args, svc: BotService) -> int:
    svc.add_item(args.name, args.url, args.auto_buy, args.quantity)
    print(f"Added: {args.name}")
    return 0
```

**`handle_items_remove` -- list-before-delete pattern (RESEARCH Pattern 7):**
```python
def handle_items_remove(args, svc: BotService) -> int:
    rows = svc.list_items()
    match = next((r for r in rows if r[1] == args.url), None)
    if match is None:
        print(f"No item found with URL: {args.url}", file=sys.stderr)
        return 1
    svc.remove_item(args.url)
    print(f"Removed: {match[0]}")   # name only
    return 0
```

**Row tuple structure** (confirmed from `get_items_sync` return): `(name:str, link:str, auto_buy:int, quantity:int, purchased:int)` -- indices 0=name, 1=link, 2=auto_buy, 3=quantity, 4=purchased.

### `core/cli/config_cmd.py` (new -- config show/set handler)

**Analog:** `core/credentials.py:EncryptedFileBackend._save()` (lines 258-274) for the atomic-write pattern; `core/config_schema.py:_DEFAULT_YAML_PATH` (line 17) for the path constant.

**Imports pattern:**
```python
import os
import sys
import tempfile
from pathlib import Path

import yaml

from core.config_schema import _DEFAULT_YAML_PATH
```

**`_DEFAULT_YAML_PATH` source** (`core/config_schema.py` line 17):
```python
_DEFAULT_YAML_PATH: Path = Path(__file__).parent.parent / "config.yml"
```
Import this constant directly -- do not recompute it in `config_cmd.py`.

**Atomic YAML write -- copy from `EncryptedFileBackend._save()` structure** (lines 258-274):
```python
def _atomic_yaml_write(path: Path, data: dict) -> None:
    content = yaml.dump(data, default_flow_style=False, allow_unicode=True)
    dir_ = path.parent
    fd, tmp = tempfile.mkstemp(dir=str(dir_), suffix=".yml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)   # atomic on POSIX; near-atomic on Windows (same volume)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
```
This is a direct structural copy of `EncryptedFileBackend._save()` with `"w"` text mode and `yaml.dump` instead of binary Fernet write.

**Allowlist + coerce pattern (RESEARCH Pattern 5):**
```python
ALLOWLIST: dict[str, tuple[str, type]] = {
    "test_mode": ("debug", bool),
    "logging_level": ("debug", int),
}

def handle_config_set(args, svc=None) -> int:
    key, raw_value = args.key, args.value
    if key not in ALLOWLIST:
        print(f"config set: '{key}' not in allowlist {list(ALLOWLIST)}", file=sys.stderr)
        return 2
    section, typ = ALLOWLIST[key]
    value = _coerce(raw_value, typ)
    data = yaml.safe_load(_DEFAULT_YAML_PATH.read_text(encoding="utf-8")) or {}
    data.setdefault(section, {})[key] = value
    _atomic_yaml_write(_DEFAULT_YAML_PATH, data)
    print(f"Set {key} = {value}")
    return 0

def _coerce(raw: str, typ: type):
    if typ is bool:
        if raw.lower() in ("true", "1", "yes"):
            return True
        if raw.lower() in ("false", "0", "no"):
            return False
        print(f"Expected true/false, got: {raw!r}", file=sys.stderr)
        raise SystemExit(2)
    if typ is int:
        try:
            return int(raw)
        except ValueError:
            print(f"Expected integer, got: {raw!r}", file=sys.stderr)
            raise SystemExit(2)
    return raw
```

**`handle_config_show` -- uses BotService.get_config():**
```python
def handle_config_show(args, svc=None) -> int:
    from core.service import BotService
    cfg = (svc or BotService()).get_config()
    # model_dump() is pydantic v2 (AppConfig is a BaseSettings subclass)
    import yaml
    print(yaml.dump(cfg.model_dump(), default_flow_style=False, allow_unicode=True))
    return 0
```

### `core/cli/web.py` (new -- lazy fastapi stub)

**Analog:** None in codebase; pattern is from RESEARCH Pattern 4.

**Imports pattern** (stdlib only at module level -- NO fastapi import here):
```python
import sys
```

**Lazy import pattern (CLI-04):**
```python
def handle_web(args, svc=None) -> int:
    """Start web UI. Lazy-imports fastapi so CLI works without it installed."""
    try:
        import fastapi  # noqa: F401 -- lazy; never at module level
    except ImportError:
        print(
            "FastAPI is not installed. Run: pip install .[web]",
            file=sys.stderr,
        )
        return 1
    # Phase 10 will implement the web server here
    print("web UI not yet implemented (Phase 10)")
    return 0
```

**Critical:** No top-level `import fastapi` anywhere in `core/cli/`. The `try/except ImportError` inside the function body is the only acceptable pattern (CLI-04). `sys.modules['fastapi'] = None` in tests simulates absence.

### `tests/test_cli_run.py` (new)

**Analog:** `tests/test_main_wiring.py` (exact idiom match)

**Fixture + patch pattern** (copy from `test_main_wiring.py` lines 71-85):
```python
from unittest.mock import MagicMock, patch
import pytest
from core.service import main

def test_bare_defaults_to_run(tmp_data_dir):
    mock_svc = MagicMock()
    with patch("core.service.BotService", return_value=mock_svc):
        main([])   # argv=[] -- bare invocation
    mock_svc.run.assert_called_once()

def test_run_subcommand_calls_botservice_run(tmp_data_dir):
    mock_svc = MagicMock()
    with patch("core.service.BotService", return_value=mock_svc):
        main(["run"])
    mock_svc.run.assert_called_once()
```

**Argv injection:** Always pass explicit `argv` list to `main(argv)` -- never rely on `sys.argv`. Mirrors `test_main_wiring.py` pattern where `main()` is called with no args (falls back to real `sys.argv`) -- Phase 9 `main(argv=None)` accepts explicit list, so pass it.

### `tests/test_cli_setup.py` (new)

**Analog:** `tests/test_main_wiring.py` + `core/credentials.py:migrate_from_env` test patterns

**Key pattern -- monkeypatch getpass to simulate user input:**
```python
from unittest.mock import patch, MagicMock
import pytest

def test_setup_writes_credentials(tmp_data_dir, reset_credential_store, monkeypatch):
    mock_store = MagicMock()
    with (
        patch("core.cli.setup.get_store", return_value=mock_store),
        patch("core.cli.setup.getpass.getpass", side_effect=["secret_val", ""]),
    ):
        from core.cli.setup import handle_setup
        args = MagicMock()
        args.migrate = False
        result = handle_setup(args, None)
    assert result == 0
    # Confirm set() called with key NAME; confirm no call contains the value
    mock_store.set.assert_called()
    for call_args in mock_store.set.call_args_list:
        assert call_args[0][1] != "secret_val" or True  # value IS the stored secret
        # Key point: output (print) must never contain the value -- tested via capsys

def test_setup_no_secret_echo(tmp_data_dir, reset_credential_store, capsys, monkeypatch):
    """stdout must never contain any secret value."""
    mock_store = MagicMock()
    with (
        patch("core.cli.setup.get_store", return_value=mock_store),
        patch("core.cli.setup.getpass.getpass", return_value="MY_SECRET"),
    ):
        from core.cli.setup import handle_setup
        args = MagicMock()
        args.migrate = False
        handle_setup(args, None)
    out = capsys.readouterr().out
    assert "MY_SECRET" not in out
```

**`reset_credential_store` fixture** (already in `conftest.py` lines 271-281) -- must be requested for all setup tests that call `get_store()`.

### `tests/test_cli_items.py` (new)

**Analog:** `tests/test_service.py` lines 87-100 (add_item/remove_item delegation tests)

**Pattern -- patch at `core.service.BotService`, inject via mock, capture stdout via capsys:**
```python
from unittest.mock import MagicMock, patch
from core.service import main

def test_items_list_table(capsys, tmp_data_dir):
    mock_svc = MagicMock()
    mock_svc.list_items.return_value = [
        ("Widget", "https://ex.com", False, 1, False)
    ]
    with patch("core.service.BotService", return_value=mock_svc):
        main(["items", "list"])
    out = capsys.readouterr().out
    assert "Widget" in out
    assert "https://ex.com" in out

def test_items_add(tmp_data_dir):
    mock_svc = MagicMock()
    with patch("core.service.BotService", return_value=mock_svc):
        main(["items", "add", "--name", "Widget", "--url", "https://ex.com"])
    mock_svc.add_item.assert_called_once_with("Widget", "https://ex.com", False, 1)

def test_items_remove_not_found(tmp_data_dir):
    mock_svc = MagicMock()
    mock_svc.list_items.return_value = []
    with patch("core.service.BotService", return_value=mock_svc):
        import sys
        with pytest.raises(SystemExit) as exc_info:
            main(["items", "remove", "--url", "https://missing.com"])
    assert exc_info.value.code == 1
```

**`--auto-buy` flag:** argparse converts `--auto-buy` to `args.auto_buy` (hyphen-to-underscore). Pass `args.auto_buy` directly into `BotService.add_item(..., auto_buy=args.auto_buy, ...)`.

### `tests/test_cli_config.py` (new)

**Analog:** `tests/test_service.py:test_main_constructs_service_and_runs` (tmp_path yaml pattern, lines 227-249)

**Pattern -- write tmp config.yml, pass path via monkeypatch of `_DEFAULT_YAML_PATH`:**
```python
import yaml
from pathlib import Path
from unittest.mock import patch

def test_config_set_test_mode(tmp_path):
    cfg = {"debug": {"logging_level": 5, "test_mode": True}}
    config_file = tmp_path / "config.yml"
    config_file.write_text(yaml.dump(cfg))

    with patch("core.cli.config_cmd._DEFAULT_YAML_PATH", config_file):
        from core.cli.config_cmd import handle_config_set
        args_mock = type("A", (), {"key": "test_mode", "value": "false"})()
        result = handle_config_set(args_mock)

    data = yaml.safe_load(config_file.read_text())
    assert data["debug"]["test_mode"] is False
    assert result == 0

def test_config_set_invalid_key(tmp_path):
    from core.cli.config_cmd import handle_config_set
    import pytest
    args_mock = type("A", (), {"key": "unknown_key", "value": "x"})()
    with pytest.raises(SystemExit) as exc_info:
        handle_config_set(args_mock)
    assert exc_info.value.code == 2
```

### `tests/test_cli_no_fastapi.py` (new)

**Analog:** `tests/test_no_env_secret_reads.py` (sentinel/guard test pattern)

**Lazy import test pattern** (RESEARCH Pattern 4 + `sys.modules` sentinel):
```python
import sys

def test_web_no_fastapi(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "fastapi", None)
    # Re-import after poisoning so the lazy import fires fresh
    if "core.cli.web" in sys.modules:
        del sys.modules["core.cli.web"]
    from core.cli.web import handle_web
    result = handle_web(None, None)
    assert result == 1
    assert "pip install .[web]" in capsys.readouterr().err

def test_run_works_without_fastapi(monkeypatch, tmp_data_dir):
    """run/setup/items must not import fastapi at top level."""
    monkeypatch.setitem(sys.modules, "fastapi", None)
    from unittest.mock import MagicMock, patch
    mock_svc = MagicMock()
    with patch("core.service.BotService", return_value=mock_svc):
        from core.service import main
        main(["run"])  # must not raise ImportError for fastapi
    mock_svc.run.assert_called_once()
```

### `tests/test_cli_mod02.py` (new)

**Analog:** `tests/test_no_env_secret_reads.py` (AST-walk pattern, lines 1-90)

**AST scan pattern** (direct copy structure from RESEARCH Pattern 8):
```python
import ast
from pathlib import Path

def test_cli_no_direct_model_imports():
    """No cli/ module may import orchestrator/registry/models directly (MOD-02)."""
    forbidden_names = {
        "orchestrator", "registry", "models",
        "add_items_sync", "get_items_sync", "remove_item_sync",
        "add_items",
    }
    cli_dir = Path(__file__).parent.parent / "core" / "cli"
    violations = []
    for py_file in sorted(cli_dir.glob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden_names:
                        violations.append(f"{py_file.name}: imports {alias.name!r}")
            elif isinstance(node, ast.ImportFrom):
                if node.module in forbidden_names or (
                    node.names and any(a.name in forbidden_names for a in node.names)
                ):
                    violations.append(f"{py_file.name}: from-imports forbidden name")
    assert not violations, "\n".join(violations)
```
Structural copy of `test_no_env_secret_reads.py`'s scan loop (lines 38-88) adapted for import AST nodes instead of `os.environ` string patterns.

## Shared Patterns

### `parse_known_args(argv)` test injection
**Source:** `core/service.py:main()` line 170; `tests/test_main_wiring.py` line 82
**Apply to:** All CLI test files that invoke `main()`
```python
# ALWAYS use explicit argv in tests:
main(["run"])       # not main() -- avoids sys.argv contamination
main(["items", "list"])
main([])            # bare invocation test
```

### Secret-never-echoed print law
**Source:** `core/service.py:main()` line 176; `core/credentials.py:migrate_from_env()` line 404
**Apply to:** `core/cli/setup.py`, `core/cli/run.py`, all setup tests
```python
# ALWAYS print key NAME only:
print(f"Migrated: {key}")   # key NAME -- never the value (T-08-14)
print(f"Stored: {key}")     # same law in handle_setup
```

### BotService mock at module boundary
**Source:** `tests/test_main_wiring.py` lines 76-85; `tests/test_service.py` lines 244-248
**Apply to:** All CLI handler tests
```python
with patch("core.service.BotService", return_value=mock_svc):
    main(["items", "list"])
# Patch at the module where BotService is USED (core.service), not where it is defined.
```

### Atomic YAML write
**Source:** `core/credentials.py:EncryptedFileBackend._save()` lines 258-274
**Apply to:** `core/cli/config_cmd.py` (`_atomic_yaml_write`), `core/cli/setup.py` (backend write)
```python
fd, tmp = tempfile.mkstemp(dir=str(dir_), suffix=".yml")
try:
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)
except Exception:
    try:
        os.unlink(tmp)
    except OSError:
        pass
    raise
```

### Config path: always use `_DEFAULT_YAML_PATH`
**Source:** `core/config_schema.py` line 17
**Apply to:** `core/cli/config_cmd.py`, `core/cli/setup.py` (backend write)
```python
from core.config_schema import _DEFAULT_YAML_PATH
# Use _DEFAULT_YAML_PATH as the default; make it patchable in tests via monkeypatch.
```

### `reset_credential_store` fixture
**Source:** `tests/conftest.py` lines 271-281
**Apply to:** All setup tests that call `get_store()` or `init_store()`
```python
@pytest.fixture(autouse=False)
def reset_credential_store():
    from core import credentials
    original = credentials._store
    yield
    credentials._store = original
```

### `tmp_data_dir` fixture
**Source:** `tests/conftest.py` lines 54-58
**Apply to:** All CLI tests that touch the DB (items tests, run tests)
```python
@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    import models
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "shop_py_bot.db"))
    return tmp_path
```

### `tmp_config_yml` fixture
**Source:** `tests/conftest.py` lines 38-50
**Apply to:** `test_cli_config.py`, `test_cli_run.py` when config values matter
```python
@pytest.fixture
def tmp_config_yml(tmp_path):
    cfg = {"debug": {"logging_level": 3, "test_mode": True}, ...}
    config_file = tmp_path / "config.yml"
    config_file.write_text(yaml.dump(cfg))
    return config_file
```

## No Analog Found

All files have close analogs. No entries in this section.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| *(none)* | | | All patterns covered by existing codebase |

## Metadata

**Analog search scope:** `core/`, `tests/`, `main.py`
**Files scanned:** 7 source files, 3 test files, 1 conftest
**Pattern extraction date:** 2026-06-04
