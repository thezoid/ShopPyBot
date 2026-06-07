# Phase 9: CLI Front-End - Research

**Researched:** 2026-06-04
**Domain:** argparse subparser CLI, cross-platform interactive input, lazy imports, YAML in-place update
**Confidence:** HIGH

## Summary

Phase 9 restructures the existing flat `core.service:main()` into a fully-articulated argparse subcommand CLI while keeping `main.py` shim and all 256 existing tests green. The scope is deliberately narrow: a thin adapter layer over `BotService` and `CredentialStore` with no new dependencies and no duplicated bot logic.

The primary engineering challenge is not the feature set -- it is the structural wiring: nested subparsers (`items list/add/remove`, `config show/set`), a bare-command default, a back-compat `--migrate` alias, and the lazy-import seam for `web`. All five areas have been prototyped against the live codebase with verified outcomes.

The second challenge is test design. The existing patterns in `test_main_wiring.py` and `test_service.py` establish the idioms: patch at the module boundary (`patch.object(module, 'BotService', ...)`), inject config via `AppConfig(yaml_file=tmp_path/...)`, and capture stdout via `capsys`. Phase 9 tests follow the same patterns applied to the new CLI handler functions.

**Primary recommendation:** Implement the CLI as a `cli/` package inside `core/` (i.e., `core/cli/`) with one module per command group (`run.py`, `setup.py`, `items.py`, `config_cmd.py`) and a thin `core/cli/__init__.py` that builds the parser and wires dispatch. `core/service.py:main()` shrinks to parser construction + dispatch only. This keeps every file under 300 lines (CLAUDE.md constraint), isolates each command group for testing, and makes the MOD-02 grep guard trivially scoped to `core/cli/`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Argument parsing and dispatch | CLI front-end (`core/cli/`) | `core/service.py:main()` builds parser | argparse is the front-end concern; dispatch fans out to handlers |
| Bot lifecycle (run/stop) | `BotService` | CLI handler calls `.run(cvv)` | All bot logic stays in service layer (MOD-02) |
| Credential prompting and storage | CLI `setup.py` handler | `CredentialStore.set()` writes | Front-end collects via getpass; backend stores |
| Item CRUD | `BotService` (wraps models) | CLI `items.py` calls service | DB never touched directly from CLI (MOD-02) |
| Config read/write | CLI `config_cmd.py` + PyYAML | `AppConfig` validates on next load | YAML edit is a CLI concern; schema validation deferred to next run |
| Lazy fastapi guard | `core/cli/web.py` handler only | pyproject.toml `[web]` extra | Import inside handler body; no top-level fastapi ref in any CLI module |

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Use `argparse` (stdlib) with subparsers -- no new dependency.
- Command shape: `shoppybot <run|setup|items|config>`; `items` nests `list|add|remove`; `config` nests `show|set`.
- Bare `shoppybot` with no subcommand defaults to `run`.
- `python main.py` stays a thin shim that reaches `BotService.run()`; both paths call `BotService.start()`/`run()` with zero duplicated orchestrator logic.
- The Phase-8 migration moves under `shoppybot setup --migrate`; the existing top-level `shoppybot --migrate` is kept as a back-compat alias.
- Setup: prompt for credentials grouped by platform/notifier; Enter skips a key (do not force all 19 SECRET_KEYS).
- Secret values entered via `getpass` (no terminal echo); confirm each stored value BY KEY NAME only, never the value.
- Setup asks which credential backend to use (auto default) and writes `credentials.backend` to config.yml.
- Setup scope: credentials + backend selection only; general settings managed by `shoppybot config`.
- Setup works correctly on both Ubuntu and Windows.
- `items list` prints a plain aligned text table (no `--json` flag).
- `items add --name "..." --url "..." [--auto-buy] [--quantity N]`; defaults: `auto_buy=False`, `quantity=1`.
- `items remove --url "..."` removes by URL, no confirmation prompt, prints removed item name.
- All item/config operations route through `BotService`, never DB directly (MOD-02).
- `config show` prints current effective config; `config set <key> <value>` updates a small allowlist (`test_mode`, `logging_level`) in config.yml.
- Exit codes: 0 success, 1 runtime error, 2 usage error (argparse default).
- Input via stdlib `getpass` (PowerShell-safe); reuse existing `colorama` for colored output.
- No-FastAPI guarantee: `web` command lazy-imports fastapi INSIDE its handler; if fastapi is missing, prints a clear `pip install .[web]` hint and exits non-zero.
- `--help` available per command and subcommand.

### Claude's Discretion
- Exact module layout for the CLI (e.g. a `cli/` package vs expanding `core/service.py:main()`).
- How subparsers are wired.
- The precise allowlist enforcement for `config set`.
- Table column formatting.
- How `setup` groups keys.
- All above provided the locked decisions hold, `BotService`/`CredentialStore` remain the only seams, and the existing 255-test suite stays green.

### Deferred Ideas (OUT OF SCOPE)
- The FastAPI web UI implementation and `shoppybot web` full behavior (Phase 10) -- Phase 9 only ships the lazy-import seam.
- `--json` output for `items list` -- add later if a real consumer needs it.
- Richer `config set` coverage beyond the scalar allowlist -- future.
- Cross-platform verification matrix / CI (Phase 11).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CLI-01 | `shoppybot run` (default) starts the bot through `BotService`; keeps `python main.py` working as a shim | Dispatcher pattern: bare cmd defaults to `_handle_run`; `BotService.run(cvv)` is the call |
| CLI-02 | `shoppybot setup` interactively stores/updates credentials; works on Ubuntu and Windows | getpass is `win_getpass` on Windows (no echo via `msvcrt.getwch`); grouped prompt loop over SECRET_KEYS; `get_store().set()` writes; atomic YAML update writes `credentials.backend` |
| CLI-03 | `shoppybot items` (list/add/remove) and `shoppybot config` manage items + settings via core API | `BotService.list_items()`, `.add_item()`, `.remove_item()`; config allowlist; PyYAML round-trip |
| CLI-04 | CLI is fully functional with NO web UI installed or running | Lazy-import seam in `web` handler; `sys.modules['fastapi'] = None` in tests validates this |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `argparse` | stdlib | Subcommand CLI, help generation | Locked decision; no new deps; already used in `core/service.py:main()` |
| `getpass` | stdlib | Secret input without echo | Already used in `main.py`; `win_getpass` on Windows uses `msvcrt.getwch` (no echo, no GetPassWarning on normal PowerShell) |
| `pyyaml` | 6.0.2 (pinned) | YAML parse + write for `config set` | Already in requirements.txt; `yaml.safe_load` + `yaml.dump` covers the allowlist round-trip |
| `colorama` | 0.4.6 (pinned) | Colored output in CLI | Already a dep; `Fore`/`Style` used in `logger.py` |

[VERIFIED: live codebase] All four libraries confirmed present in `requirements.txt` or stdlib; versions confirmed via `pip show` and `python -c "import X; print(X.__version__)"`.

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `ruamel.yaml` | 0.19.1 (transitive via check-jsonschema, NOT in requirements.txt) | Comment-preserving YAML round-trip | NOT recommended for `config set` -- it is a transitive dependency only and adding it as a direct dep violates the no-new-deps constraint. Use `pyyaml` instead; comments are lost on `config set` and that is acceptable. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| argparse subparsers | click, typer | Both require new dependencies -- locked out by CONTEXT decision |
| pyyaml round-trip | ruamel.yaml | Preserves comments but adds direct dep; not in requirements.txt |
| getpass | msvcrt directly | Getpass wraps msvcrt on Windows already; stdlib is the right level |

**Installation:** No new packages required. All libraries are stdlib or already pinned in `requirements.txt`.

## Package Legitimacy Audit

No new packages are being added in this phase. The CLI relies entirely on stdlib (`argparse`, `getpass`) and already-pinned dependencies (`pyyaml==6.0.2`, `colorama==0.4.6`).

**Packages removed due to slopcheck:** none
**Packages flagged as suspicious:** none

## Architecture Patterns

### System Architecture Diagram

```
shoppybot [argv]
     |
     v
core/service.py:main(argv=None)
     |
     +-- parse_known_args(argv or sys.argv[1:])
     |        |
     |        +-- bare / 'run' command ---------> _handle_run(args, svc)
     |        |                                        |
     |        +-- 'setup' / '--migrate' ---------> _handle_setup(args, svc)
     |        |                                        |
     |        +-- 'items' -> 'list'  ------------> _handle_items_list(args, svc)
     |        |           -> 'add'   ------------> _handle_items_add(args, svc)
     |        |           -> 'remove'-----------> _handle_items_remove(args, svc)
     |        |
     |        +-- 'config' -> 'show' -----------> _handle_config_show(args)
     |        |            -> 'set'  -----------> _handle_config_set(args)
     |        |
     |        +-- 'web' ---[lazy import]---------> _handle_web(args)
     |
     v
BotService  <-- all item/lifecycle calls
CredentialStore  <-- all secret reads/writes via get_store()
config.yml  <-- atomic YAML edit for 'config set' and setup backend write
```

Data flows:
- `run`: main() -> BotService(cfg).run(cvv) [blocking]
- `setup`: getpass prompts -> get_store().set(key, value) -> yaml write `credentials.backend`
- `items add`: argparse flags -> BotService.add_item(name, link, auto_buy, quantity)
- `items remove`: BotService.list_items() [for name lookup] -> BotService.remove_item(link)
- `config set`: yaml.safe_load -> allowlist validate -> yaml.dump -> os.replace atomic write

### Recommended Project Structure

```
core/
  service.py          # main() grows subparser; handlers here or delegated to cli/
  cli/                # (Claude's discretion) one module per command group
    __init__.py       # build_parser() + dispatch; imported by service.py:main()
    run.py            # handle_run(args, svc)
    setup.py          # handle_setup(args, svc)  [getpass + get_store().set]
    items.py          # handle_items_*(args, svc)
    config_cmd.py     # handle_config_*(args)    [PyYAML round-trip]
    web.py            # handle_web(args)         [lazy fastapi import]
tests/
  test_cli_run.py         # new -- CLI-01
  test_cli_setup.py       # new -- CLI-02
  test_cli_items.py       # new -- CLI-03
  test_cli_config.py      # new -- CLI-03
  test_cli_no_fastapi.py  # new -- CLI-04
  test_cli_mod02.py       # new -- MOD-02 grep guard for cli/ modules
```

The `core/cli/` layout keeps every file under 300 lines (CLAUDE.md), isolates testable units, and gives the MOD-02 grep guard a clean scan target.

### Pattern 1: `func`-dispatch with `set_defaults`

**What:** Each subparser (and nested subparser) calls `.set_defaults(func=handler_fn)`. After parsing, a single `args.func(args, service)` dispatches without an `if/elif` chain.

**When to use:** Whenever the number of subcommands exceeds 2-3; scales cleanly; is the idiomatic argparse dispatch pattern.

**Example:**
```python
# Source: Python stdlib argparse documentation (docs.python.org/3/library/argparse.html)
def build_parser():
    parser = argparse.ArgumentParser(prog="shoppybot", description="ShopPyBot CLI")
    parser.set_defaults(func=None)  # bare shoppybot has no func initially

    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Start the bot (default).")
    run_p.set_defaults(func=handle_run)

    setup_p = sub.add_parser("setup", help="Store credentials and select backend.")
    setup_p.add_argument("--migrate", action="store_true",
                         help="Import env-var secrets into the active backend.")
    setup_p.set_defaults(func=handle_setup)

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

    return parser


def main(argv=None) -> None:
    parser = build_parser()
    args, _ = parser.parse_known_args(argv)

    # Back-compat: top-level --migrate treated as 'shoppybot setup --migrate'
    if getattr(args, "migrate", False) and args.command is None:
        args.func = handle_setup  # redirect

    # Bare shoppybot = run
    if args.func is None:
        handle_run(args, BotService())
        return

    svc = BotService() if _needs_service(args) else None
    sys.exit(args.func(args, svc) or 0)
```

[VERIFIED: live codebase] Prototyped against Python 3.13.13 on Windows; `parse_known_args([])` returns `func=None` confirming bare-command fallback works.

### Pattern 2: Back-compat `--migrate` top-level alias

**What:** The existing `shoppybot --migrate` path must keep working. Since `--migrate` will not be a top-level argparse flag in Phase 9 (it moves to `setup --migrate`), the cleanest approach is to add `--migrate` as a top-level parser argument that is ALSO available under `setup`, and treat both identically in dispatch.

**Alternative:** Use `parse_known_args` to catch `--migrate` in the unknown-args list and redirect. This avoids adding a top-level `--migrate` declaration to the new parser.

**Recommended:** Keep `--migrate` as a top-level `add_argument` (just as it is now) AND also add it under `setup`. When `args.migrate` is True and `args.command` is None, dispatch to `handle_setup` (with migration logic). This is the lowest-risk migration path -- no behavioral change for existing users.

[VERIFIED: live codebase] Confirmed `parse_known_args(['--migrate'])` returns the flag in `unknown` list if not declared, so top-level declaration is needed for back-compat.

### Pattern 3: getpass on Windows PowerShell

**What:** Python's `getpass.getpass()` on Windows uses `win_getpass()` which calls `msvcrt.getwch()` -- reads one character at a time with echo suppression via the Windows console API. This does NOT raise `GetPassWarning` on a normal PowerShell terminal. `GetPassWarning` is only raised when stdin is redirected (non-interactive), which is the same behavior on Linux/Ubuntu.

**Pitfall:** `getpass.getpass()` raises `EOFError` when stdin is closed (e.g., piped input). The setup handler should catch `EOFError` and skip the key (same as pressing Enter).

**Cross-platform handling:**
```python
# Source: Python stdlib getpass.py (C:\Program Files\Python313\Lib\getpass.py)
def prompt_secret(prompt: str) -> str | None:
    """Return secret string or None if user skips (empty input or EOF)."""
    try:
        val = getpass.getpass(prompt).strip()
    except EOFError:
        return None
    except getpass.GetPassWarning:
        # stdin redirected -- treat as skip
        return None
    return val or None  # empty Enter = skip
```

[VERIFIED: live codebase] `getpass.__file__` points to `C:\Program Files\Python313\Lib\getpass.py`; `win_getpass` function confirmed present; `GetPassWarning` is a `UserWarning` subclass.

### Pattern 4: Lazy fastapi import seam (CLI-04)

**What:** The `web` command handler must import fastapi inside the function body only. No `import fastapi` at module level in any `core/cli/` file.

**Test approach:** `sys.modules['fastapi'] = None` before calling the handler simulates the package being absent. Python raises `ImportError: import of fastapi halted; None in sys.modules`. In pytest this is `monkeypatch.setitem(sys.modules, 'fastapi', None)`.

```python
# Source: live codebase prototype -- sys.modules sentinel confirmed working
def handle_web(args, svc):
    try:
        import fastapi  # noqa: F401 -- lazy import; never at module level
    except ImportError:
        print("FastAPI is not installed. Run: pip install .[web]", file=sys.stderr)
        return 1
    # Phase 10 will fill this in
    print("web UI not yet implemented (Phase 10)")
    return 0
```

**Test:**
```python
def test_web_without_fastapi(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "fastapi", None)
    from core.cli.web import handle_web
    result = handle_web(None, None)
    assert result == 1
    captured = capsys.readouterr()
    assert "pip install .[web]" in captured.err
```

[VERIFIED: live codebase] `sys.modules['_test_absent_pkg'] = None` then `import _test_absent_pkg` raises `ImportError` with the expected sentinel message. Same pattern works for fastapi.

### Pattern 5: PyYAML atomic config set

**What:** `config set <key> <value>` reads `config.yml` with `yaml.safe_load`, updates the allowlist field, and writes back with `yaml.dump` using tempfile + `os.replace` (same atomic-write pattern already in `EncryptedFileBackend`). Comments are lost on write -- this is acceptable and documented.

**Allowlist:** `{'test_mode': ('debug', bool), 'logging_level': ('debug', int)}`

**Type coercion:** `test_mode` parses `"true"/"false"` -> bool; `logging_level` parses `"0"-"5"` -> int with range check.

```python
# Source: live codebase prototype; confirmed with yaml 6.0.2
ALLOWLIST: dict[str, tuple[str, type]] = {
    "test_mode": ("debug", bool),
    "logging_level": ("debug", int),
}

def _config_set(key: str, raw_value: str, config_path: Path) -> None:
    if key not in ALLOWLIST:
        print(f"config set: '{key}' is not in the allowlist {list(ALLOWLIST)}", file=sys.stderr)
        raise SystemExit(2)
    section, typ = ALLOWLIST[key]
    value = _coerce(raw_value, typ)          # raises SystemExit(2) on bad value
    data = yaml.safe_load(config_path.read_text()) or {}
    data.setdefault(section, {})[key] = value
    _atomic_yaml_write(config_path, data)    # tempfile + os.replace


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

[VERIFIED: live codebase] `yaml.safe_load` + `yaml.dump` round-trip confirmed; `_DEFAULT_YAML_PATH` is `Path(__file__).parent.parent / "config.yml"` (importable from `core.config_schema`).

### Pattern 6: items list text table

**What:** `BotService.list_items()` returns `list[tuple[name, link, auto_buy, quantity, purchased]]` -- confirmed by inspecting `get_items_sync()`.

```python
# Source: live codebase -- get_items_sync() returns (name, link, auto_buy, quantity, purchased)
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

[VERIFIED: live codebase] Row structure confirmed: `(name:str, link:str, auto_buy:int, quantity:int, purchased:int)`.

### Pattern 7: items remove name lookup

**What:** `BotService.remove_item(link)` returns `None` (delegates to `remove_item_sync` which issues a `DELETE` with no return). To print the removed item's name, the CLI must call `BotService.list_items()` BEFORE `remove_item()` to find the matching row.

```python
def handle_items_remove(args, svc: BotService) -> int:
    url = args.url
    rows = svc.list_items()
    match = next((r for r in rows if r[1] == url), None)
    if match is None:
        print(f"No item found with URL: {url}", file=sys.stderr)
        return 1
    svc.remove_item(url)
    print(f"Removed: {match[0]}")   # name only
    return 0
```

[VERIFIED: live codebase] `remove_item_sync` confirmed to issue silent no-op DELETE; name lookup via `list_items()` prior to delete is the correct strategy.

### Pattern 8: MOD-02 grep guard test

**What:** A test scans all files in `core/cli/` (and any front-end modules) for direct imports of `orchestrator`, `registry`, `models`, `add_items_sync`, `get_items_sync`, or `remove_item_sync`. These are the forbidden seams.

```python
# Follows the same AST-scan pattern as test_no_env_secret_reads.py
def test_cli_no_direct_model_imports():
    forbidden_names = {
        "orchestrator", "registry", "models",
        "add_items_sync", "get_items_sync", "remove_item_sync",
        "add_items",
    }
    cli_dir = Path(__file__).parent.parent / "core" / "cli"
    violations = []
    for py_file in cli_dir.glob("*.py"):
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

[VERIFIED: live codebase] Pattern adapted from `test_no_env_secret_reads.py` which uses the same AST-walk approach.

### Anti-Patterns to Avoid

- **Importing BotService at CLI module top-level without guarding:** BotService.__init__ calls `init_store(cfg)` which may call `getpass.getpass()` if the `file` backend needs a passphrase. Do not construct BotService before argument parsing completes.
- **Using `parser.parse_args()` instead of `parse_known_args()`:** The established project pattern is `parse_known_args()` to avoid sys.argv contamination in tests. Deviation would break `test_main_wiring.py` idioms.
- **Echoing any credential value in setup:** Confirm by key NAME only, never by value. Pattern already established in `migrate_from_env` (T-08-14).
- **Direct `open()` write to config.yml without atomic pattern:** Non-atomic write leaves a partially-written YAML on crash. Use tempfile + `os.replace` as in `EncryptedFileBackend._save()`.
- **Top-level `import fastapi` in any `core/cli/` module:** Violates CLI-04. Even a commented-out import that gets accidentally uncommented would break the invariant. The lazy-import must be inside the handler function body only.
- **Using `sys.argv[0]` as the prog name:** `argparse.ArgumentParser(prog="shoppybot")` must be explicit so `--help` output and error messages are consistent regardless of how the entry point is invoked.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Echo-suppressed secret input | Custom `msvcrt` loop | `getpass.getpass()` | Handles Windows/Linux/EOF/GetPassWarning already |
| YAML atomic write | Custom file rename | `tempfile.mkstemp` + `os.replace` | Pattern already in `EncryptedFileBackend._save()`; copy it |
| Subcommand dispatch | `if/elif args.command == "run"` chain | `set_defaults(func=...)` | Scales; eliminates a long conditional; argparse idiom |
| Missing-package detection | Custom `importlib.util.find_spec` guard | `try: import fastapi` / `except ImportError` | Simpler; correct; `sys.modules[key] = None` test idiom works with this |

**Key insight:** Every hand-roll in this CLI domain is already solved in the existing codebase or by stdlib. The phase is wiring, not invention.

## Common Pitfalls

### Pitfall 1: bare `shoppybot` dispatches to `func=None`
**What goes wrong:** After building nested subparsers with `set_defaults(func=handler)`, calling `parser.parse_known_args([])` returns `args.func == None` because no subcommand was given. `args.func(args, svc)` then raises `TypeError: 'NoneType' object is not callable`.

**Why it happens:** `set_defaults(func=None)` on the top-level parser is the fallback. Nested `set_defaults` only apply when that subparser is selected.

**How to avoid:** After parsing, check `if args.func is None: handle_run(args, svc); return`.

**Warning signs:** `TypeError: 'NoneType' object is not callable` in tests that call `main([])`.

[VERIFIED: live codebase] `parse_known_args([])` returns `func=None` confirmed in prototype.

### Pitfall 2: `--migrate` back-compat breaks when subparsers introduced
**What goes wrong:** Adding subparsers changes how `parse_known_args` handles unknown flags. If `--migrate` is not declared at the top-level parser, it ends up in the `unknown` list, not `args.migrate`. Existing callers/tests that check `args.migrate` will fail silently.

**Why it happens:** argparse subparser introduction does not automatically inherit parent-level flags unless `add_argument` is explicitly called on both the parent and subparser.

**How to avoid:** Keep `--migrate` as a top-level `add_argument` on the root parser (aliased to `setup --migrate`). Confirmed required by prototype: `parse_known_args(['--migrate'])` puts it in `unknown` if not declared.

**Warning signs:** `test_main_wiring.py`-style tests that invoke `main(['--migrate'])` and expect migration to run.

### Pitfall 3: `getpass.getpass()` in setup raises `GetPassWarning` in CI
**What goes wrong:** In a non-interactive environment (CI, piped stdin), `getpass.getpass()` emits `GetPassWarning` and may echo. The setup handler must catch this and skip the key rather than crashing.

**Why it happens:** `GetPassWarning` is a `UserWarning`; if the caller does not catch it, it surfaces as a warning in test output. If `sys.stdin` is closed, `EOFError` is raised.

**How to avoid:** Wrap each `getpass.getpass()` call in a `try/except (EOFError, getpass.GetPassWarning)` and treat both as "skip this key".

**Warning signs:** pytest emitting unexpected `GetPassWarning`; `EOFError` in setup tests that mock stdin.

### Pitfall 4: `config set` writes config.yml cwd-relative instead of project-root
**What goes wrong:** `open('config.yml', 'w')` uses the current working directory. If the user runs `shoppybot config set` from a different directory, it creates a new config.yml in the wrong location or silently writes the wrong file.

**Why it happens:** The existing `AppConfig` uses `_DEFAULT_YAML_PATH = Path(__file__).parent.parent / "config.yml"` (absolute, repo-root relative). A naive `open('config.yml')` ignores this.

**How to avoid:** Import `_DEFAULT_YAML_PATH` from `core.config_schema` and use it as the default config path. Make the path overridable via an `--config` argument (or just use the constant for now).

**Warning signs:** Tests running from `tmp_path` and failing to find config.yml; `yaml.safe_load` returning `None` (empty file).

### Pitfall 5: `items remove` silently succeeds when URL not found
**What goes wrong:** `BotService.remove_item(link)` wraps `remove_item_sync(link)` which issues `DELETE FROM items WHERE link=?`. If the URL does not match any row, no error is raised -- the operation silently no-ops.

**Why it happens:** SQLite `DELETE` with no matching rows is not an error.

**How to avoid:** Call `BotService.list_items()` first, check for a matching URL, and exit with a clear message and code 1 if not found. This also gives the CLI the item name to print on success.

**Warning signs:** `items remove --url https://typo.com` prints "Removed: " with no name.

### Pitfall 6: `config set` `bool` type coercion from argparse string
**What goes wrong:** `argparse` delivers `"true"` as a string, not Python `True`. Directly writing `"true"` to YAML will be interpreted as the string `"true"` by PyYAML, not the YAML boolean `true`. `AppConfig` will then fail to load it as a bool.

**Why it happens:** `yaml.dump({"test_mode": "true"})` serializes as `test_mode: 'true'` (quoted string), not `test_mode: true`.

**How to avoid:** Explicitly coerce the string to a Python `bool` before `yaml.dump`. The `_coerce()` pattern above handles this.

**Warning signs:** `AppConfig()` raises `ValidationError: test_mode: Input should be a valid boolean` after `config set test_mode true`.

### Pitfall 7: `main(argv=None)` signature not accepted by argparse `parse_known_args`
**What goes wrong:** `parse_known_args(None)` falls back to `sys.argv[1:]` (correct behavior). But if a test calls `main(argv=[])` and `parse_known_args(argv)` receives the explicit empty list, that is also correct (it means "parse no args"). The two cases behave identically. The pitfall is tests that pass `main([])` expecting the same result as `main()`.

**How to avoid:** Use `parse_known_args(argv)` directly (not `parse_known_args(argv or sys.argv[1:])`) -- argparse already handles `None` correctly.

**Warning signs:** Tests that check for "run" default behavior failing when `main([])` is used instead of `main()`.

## Code Examples

### Verified patterns from live codebase

### Argparse nested subparser dispatch
```python
# Source: prototyped against Python 3.13.13 stdlib (E:/repos/ShopPyBot)
parser = argparse.ArgumentParser(prog="shoppybot")
parser.set_defaults(func=None)
sub = parser.add_subparsers(dest="command")

run_p = sub.add_parser("run")
run_p.set_defaults(func=handle_run)

items_p = sub.add_parser("items")
items_sub = items_p.add_subparsers(dest="items_command")
list_p = items_sub.add_parser("list")
list_p.set_defaults(func=handle_items_list)

args, _ = parser.parse_known_args(["items", "list"])
# args.func is handle_items_list; args.items_command is "list"
```

### sys.modules None sentinel for testing absent import
```python
# Source: prototyped against Python 3.13.13 (E:/repos/ShopPyBot)
# In pytest:
def test_web_no_fastapi(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "fastapi", None)
    from core.cli.web import handle_web  # import after poisoning
    rc = handle_web(None, None)
    assert rc == 1
    assert "pip install .[web]" in capsys.readouterr().err
```

### getpass skip-on-EOF pattern
```python
# Source: stdlib getpass.py; pattern derived from main.py existing usage
def prompt_secret(prompt: str) -> str | None:
    try:
        val = getpass.getpass(prompt).strip()
    except (EOFError, getpass.GetPassWarning):
        return None
    return val or None
```

### PyYAML allowlist config set
```python
# Source: prototyped against pyyaml 6.0.2 (E:/repos/ShopPyBot)
from core.config_schema import _DEFAULT_YAML_PATH
import yaml, os, tempfile

def _atomic_yaml_write(path, data):
    content = yaml.dump(data, default_flow_style=False, allow_unicode=True)
    dir_ = path.parent
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

### Test pattern: invoke main() with argv injection and mock BotService
```python
# Source: test_service.py pattern extended to subcommands
def test_items_list(capsys, tmp_data_dir):
    mock_svc = MagicMock()
    mock_svc.list_items.return_value = [
        ("Widget", "https://ex.com", False, 1, False)
    ]
    with patch("core.service.BotService", return_value=mock_svc):
        from core.service import main
        main(["items", "list"])   # explicit argv -- no sys.argv dependency
    out = capsys.readouterr().out
    assert "Widget" in out
    assert "https://ex.com" in out
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Flat `main()` with only `--migrate` | Subcommand dispatch with `set_defaults(func=...)` | Phase 9 | `shoppybot setup/items/config` become first-class commands |
| `python main.py` as the only entry | `shoppybot` console script (already wired in Phase 7) | Phase 7 | `shoppybot` CLI exists; Phase 9 adds real subcommands |
| Secrets via env vars only | CredentialStore with getpass setup flow | Phase 8 | `setup` command now has a real credential store to write to |

**Deprecated/outdated in Phase 9:**
- The flat `parse_known_args()` loop in `core/service.py:main()` is replaced by subparser dispatch. The `--migrate` handling moves into a `setup` handler (back-compat alias kept).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `main(argv=None)` with explicit argv parameter is the clean pattern for test injection | Pattern 1 | If main() must stay `main()` with no params, tests must patch `sys.argv` instead -- slightly more verbose but workable |
| A2 | Comments in config.yml being lost on `config set` is acceptable to the user | Pattern 5 | If comment preservation is required, `ruamel.yaml` must be added to requirements.txt (new dep, violates constraint) |
| A3 | `core/cli/` package inside `core/` is the right module layout (Claude's discretion) | Recommended Structure | Planner may choose a different layout; constraints hold regardless |

**If this table is empty:** All claims in this research were verified or cited -- no user confirmation needed.

A1 and A3 are under Claude's discretion per CONTEXT.md. A2 is the practical consequence of the no-new-deps constraint already locked in CONTEXT.md.

## Open Questions (RESOLVED)

1. **RESOLVED — `main(argv=None)` parameter added.** Use `parse_known_args(argv)` with an explicit `argv=None` parameter for clean test injection (falls back to sys.argv). Locked in plan 09-01 T3; backward compatible.
   - Context: `parse_known_args(argv)` accepts `None` or an explicit list; existing `test_service.py::test_main_constructs_service_and_runs` patches `BotService` so `run()` never fires.

2. **RESOLVED — dual `--migrate` path kept.** Both top-level `shoppybot --migrate` AND `shoppybot setup --migrate` work. Locked in plan 09-02; top-level stays as a back-compat alias for existing scripts.
   - Context: CONTEXT.md says "setup --migrate replaces/aliases top-level --migrate"; dual-path satisfies both back-compat and the new subcommand.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.13 | All CLI code | Yes | 3.13.13 | -- |
| argparse | CLI parsing | Yes (stdlib) | 3.13.13 stdlib | -- |
| getpass | Secret prompts | Yes (stdlib) | 3.13.13 stdlib; `win_getpass` confirmed | -- |
| pyyaml | `config set` write | Yes | 6.0.2 | -- |
| colorama | Colored output | Yes | 0.4.6 | Omit color if unavailable |
| keyring | CredentialStore (Phase 8) | Yes (from reqs) | Confirmed via Phase 8 | -- |
| cryptography | EncryptedFileBackend | Yes (from reqs) | Confirmed via Phase 8 | -- |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (asyncio_mode=auto per pyproject.toml) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_cli_*.py -x -q` |
| Full suite command | `pytest -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CLI-01 | `shoppybot run` calls `BotService.run(cvv)` | unit | `pytest tests/test_cli_run.py -x` | No -- Wave 0 |
| CLI-01 | `shoppybot` (bare) defaults to run | unit | `pytest tests/test_cli_run.py::test_bare_defaults_to_run -x` | No -- Wave 0 |
| CLI-01 | `python main.py` still routes through `BotService.run()` | unit | `pytest tests/test_main_wiring.py -x` | Yes (255 passing) |
| CLI-02 | `setup` prompts per group; Enter skips key | unit | `pytest tests/test_cli_setup.py::test_enter_skips_key -x` | No -- Wave 0 |
| CLI-02 | `setup` writes to `get_store().set(key, val)` | unit | `pytest tests/test_cli_setup.py::test_setup_writes_credentials -x` | No -- Wave 0 |
| CLI-02 | `setup` confirms by key name only, never value | unit | `pytest tests/test_cli_setup.py::test_setup_no_secret_echo -x` | No -- Wave 0 |
| CLI-02 | `setup` writes `credentials.backend` to config.yml | unit | `pytest tests/test_cli_setup.py::test_setup_writes_backend -x` | No -- Wave 0 |
| CLI-02 | `setup --migrate` imports env vars | unit | `pytest tests/test_cli_setup.py::test_setup_migrate -x` | No -- Wave 0 |
| CLI-03 | `items list` prints text table with all items | unit | `pytest tests/test_cli_items.py::test_items_list_table -x` | No -- Wave 0 |
| CLI-03 | `items add` calls `BotService.add_item(name, link, auto_buy, qty)` | unit | `pytest tests/test_cli_items.py::test_items_add -x` | No -- Wave 0 |
| CLI-03 | `items remove` calls `BotService.remove_item(link)` and prints name | unit | `pytest tests/test_cli_items.py::test_items_remove -x` | No -- Wave 0 |
| CLI-03 | `items remove` exits 1 when URL not found | unit | `pytest tests/test_cli_items.py::test_items_remove_not_found -x` | No -- Wave 0 |
| CLI-03 | `config show` prints effective config | unit | `pytest tests/test_cli_config.py::test_config_show -x` | No -- Wave 0 |
| CLI-03 | `config set test_mode true` writes YAML correctly | unit | `pytest tests/test_cli_config.py::test_config_set_test_mode -x` | No -- Wave 0 |
| CLI-03 | `config set logging_level 3` writes YAML correctly | unit | `pytest tests/test_cli_config.py::test_config_set_logging_level -x` | No -- Wave 0 |
| CLI-03 | `config set unknown_key` exits 2 | unit | `pytest tests/test_cli_config.py::test_config_set_invalid_key -x` | No -- Wave 0 |
| CLI-04 | `shoppybot run/setup/items` work with fastapi absent | unit | `pytest tests/test_cli_no_fastapi.py -x` | No -- Wave 0 |
| CLI-04 | `shoppybot web` prints pip hint and exits 1 when fastapi absent | unit | `pytest tests/test_cli_no_fastapi.py::test_web_no_fastapi -x` | No -- Wave 0 |
| MOD-02 | No cli/ module imports orchestrator/registry/models directly | AST scan | `pytest tests/test_cli_mod02.py -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_cli_*.py -x -q` (new CLI tests only -- fast)
- **Per wave merge:** `pytest -x -q` (full 256+ test suite)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps (files to create before implementation)
- `tests/test_cli_run.py` -- covers CLI-01
- `tests/test_cli_setup.py` -- covers CLI-02
- `tests/test_cli_items.py` -- covers CLI-03 items
- `tests/test_cli_config.py` -- covers CLI-03 config
- `tests/test_cli_no_fastapi.py` -- covers CLI-04
- `tests/test_cli_mod02.py` -- covers MOD-02 grep guard
- `core/cli/__init__.py` -- build_parser() and dispatch
- `core/cli/run.py`, `core/cli/setup.py`, `core/cli/items.py`, `core/cli/config_cmd.py`, `core/cli/web.py`

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No -- CLI does not authenticate users to a service | -- |
| V3 Session Management | No | -- |
| V4 Access Control | No | -- |
| V5 Input Validation | Yes -- `config set` key/value | allowlist + type coercion (Pattern 5) |
| V6 Cryptography | No -- CLI does not implement crypto | `CredentialStore` handles all crypto (Phase 8) |

### Known Threat Patterns for CLI

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secret echo in setup output | Info Disclosure | `getpass.getpass()` + confirm by key NAME only (never value) |
| YAML injection in `config set` | Tampering | `yaml.safe_load` (not `yaml.load`) + allowlist gate prevents arbitrary writes |
| Partial YAML write on crash | Tampering / DoS | Atomic tempfile + `os.replace` write pattern |
| fastapi top-level import leaking | Information | Lazy import inside handler; CLI-04 test verifies absence |

## Sources

### Primary (HIGH confidence)
- `E:/repos/ShopPyBot/core/service.py` -- existing `main()`, `BotService` API, `parse_known_args` pattern
- `E:/repos/ShopPyBot/core/credentials.py` -- `SECRET_KEYS`, `get_store()`, `migrate_from_env`, `EncryptedFileBackend._save()` atomic write pattern
- `E:/repos/ShopPyBot/core/config_schema.py` -- `AppConfig`, `_DEFAULT_YAML_PATH`, `DebugConfig` fields
- `E:/repos/ShopPyBot/tests/test_service.py` -- established test patterns for BotService mocking
- `E:/repos/ShopPyBot/tests/test_main_wiring.py` -- argv injection and module-level patch patterns
- `E:/repos/ShopPyBot/tests/test_no_env_secret_reads.py` -- AST-scan guard pattern for MOD-02
- `E:/repos/ShopPyBot/tests/conftest.py` -- `tmp_data_dir`, `reset_credential_store` fixtures
- Python 3.13.13 stdlib: `getpass.getpass` (`win_getpass` on Windows confirmed)
- pyyaml 6.0.2: `yaml.safe_load` / `yaml.dump` round-trip confirmed

### Secondary (MEDIUM confidence)
- Live prototype: `parse_known_args([])` -> `func=None` behavior (run in-process)
- Live prototype: `sys.modules['key'] = None` -> `ImportError` sentinel (run in-process)
- Live prototype: `yaml.dump(data)` round-trip (run in-process; comments lost, confirmed acceptable)
- Live prototype: `get_items_sync()` returns `(name, link, auto_buy, quantity, purchased)` 5-tuples

### Tertiary (LOW confidence)
- None -- all claims verified in-process or against live codebase.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries confirmed in requirements.txt or stdlib
- Architecture: HIGH -- BotService API prototyped against live code; all return types verified
- Pitfalls: HIGH -- each pitfall reproduced in-process during research
- Test patterns: HIGH -- adapted from existing passing tests in the same repo

**Research date:** 2026-06-04
**Valid until:** 2026-07-04 (stable stdlib APIs; 30-day window adequate)
