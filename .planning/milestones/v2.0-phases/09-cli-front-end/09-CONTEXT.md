# Phase 9: CLI Front-End - Context

**Gathered:** 2026-06-04
**Status:** Ready for planning

<domain>
## Phase Boundary

The `shoppybot` command-line tool exposes all bot operations (run, setup, item management, config) as thin adapters over `BotService` and `CredentialStore`. No bot/orchestrator/registry/DB logic lives in the CLI layer (MOD-02). The CLI is fully functional with no web UI installed (CLI-04). Covers CLI-01..CLI-04. No new dependencies.

NOT in scope: the optional FastAPI web UI itself (Phase 10 — only the lazy-import seam that guarantees the CLI works without it is in scope here), cross-platform CI matrix (Phase 11). The CVV stays a runtime getpass prompt in the front-end, never stored.
</domain>

<decisions>
## Implementation Decisions

### CLI Framework & Command Structure (CLI-01)
- Use `argparse` (stdlib) with subparsers — no new dependency (KISS / dep-minimal project rule).
- Command shape: `shoppybot <run|setup|items|config>`; `items` nests `list|add|remove`; `config` nests `show|set`.
- Bare `shoppybot` with no subcommand defaults to `run` — preserves `python main.py` default behavior (CLI-01).
- `python main.py` stays a thin shim that reaches the same `BotService.run()` path; both `shoppybot run` and `main.py` call `BotService.start()`/`run()` with zero duplicated orchestrator logic.
- The Phase-8 migration moves under `shoppybot setup --migrate`; the existing top-level `shoppybot --migrate` is kept as a back-compat alias.

### Setup Flow (CLI-02)
- Prompt for credentials grouped by platform/notifier; pressing Enter skips a key (do not force all 19 SECRET_KEYS).
- Secret values entered via `getpass` (no terminal echo); confirm each stored value BY KEY NAME only, never the value.
- Setup asks which credential backend to use (auto default) and writes `credentials.backend` to config.yml.
- Setup scope = credentials + backend selection only. General settings (test_mode, logging_level, platform/notifier enables) are managed by `shoppybot config`, not setup.
- Setup completes correctly on both Ubuntu (interactive terminal) and Windows (PowerShell).

### Items & Config Commands (CLI-03)
- `items list` prints a plain aligned text table (no `--json` flag — YAGNI).
- `items add --name "..." --url "..." [--auto-buy] [--quantity N]`; defaults: `auto_buy=False`, `quantity=1`. Calls `BotService.add_item(...)`.
- `items remove --url "..."` removes by URL (the unique key), no confirmation prompt (scriptable), prints the removed item name. Calls `BotService.remove_item(...)`.
- `config show` prints the current effective config; `config set <key> <value>` updates a small allowlist of top-level scalars (test_mode, logging_level) in config.yml.
- All item/config operations route through `BotService` (and config layer), never the DB directly (MOD-02).

### Errors & Cross-Platform (CLI-04)
- Exit codes: 0 success, 1 runtime error, 2 usage error (argparse default).
- Input via stdlib `getpass` (PowerShell-safe); reuse the existing `colorama` for any colored output.
- No-FastAPI guarantee: the `web` command imports fastapi lazily INSIDE its handler; CLI core modules never import fastapi at top level. If fastapi is missing, `shoppybot web` prints a clear `pip install .[web]` hint and exits non-zero. Uninstalling fastapi leaves run/setup/items/config fully functional.
- `--help` available per command and subcommand (argparse).

### Claude's Discretion
- Exact module layout for the CLI (e.g. a `cli/` package vs expanding `core/service.py:main()`), how subparsers are wired, the precise allowlist enforcement for `config set`, table column formatting, and how `setup` groups keys — provided the locked decisions hold, `BotService`/`CredentialStore` remain the only seams, and the existing 255-test suite stays green.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/service.py` `BotService`: `get_config()`, `get_status()`, `list_items()`, `add_item(name, link, auto_buy, quantity)`, `remove_item(link)`, `start(cvv)`, `stop()`, `run(cvv)` — the complete seam the CLI adapts over.
- `core/service.py:main()`: existing argparse entry (currently flat with `--migrate`); this is what gets restructured into subcommands. Entry point already wired: `pyproject.toml [project.scripts] shoppybot = "core.service:main"`.
- `core/credentials.py`: `get_store()`, `init_store(cfg)`, `SECRET_KEYS` (19 keys), `migrate_from_env(store)` — setup writes via `get_store().set(key, value)`; `--migrate` calls `migrate_from_env`.
- `core/config_schema.py`: `AppConfig` + `CredentialsConfig` (backend selector + data-dir); `config set` updates config.yml fields.
- `models.py`: item CRUD sync funcs (`get_items_sync`, `add_items_sync`, `remove_item_sync`) — already wrapped by BotService; CLI must NOT call these directly.
- `main.py`: existing thin shim (Phase 7) — keep it working identically.

### Established Patterns
- `parse_known_args()` already used in `main()` to avoid sys.argv contamination in tests (Phase 7 decision).
- Secrets never logged/echoed; getpass for runtime secret entry (Phase 1/8 pattern).
- Front-ends are thin adapters over BotService (MOD-02, enforced by grep test).

### Integration Points
- `shoppybot` console entry → `core.service:main()` → subparser dispatch → `BotService`/`CredentialStore`.
- `web` subcommand is the only seam to Phase 10; it must lazy-import fastapi so CLI-04 holds.
</code_context>

<specifics>
## Specific Ideas

- SC4 guardrail: a test asserting `shoppybot run/setup/items` work with fastapi uninstalled (no top-level fastapi import in CLI core).
- MOD-02 grep guard: no orchestrator/registry/DB calls from CLI modules bypassing BotService.
- Setup must never echo a secret and must confirm by key name only (mirrors CRED-07 / Phase 8 migrate behavior).
</specifics>

<deferred>
## Deferred Ideas

- The FastAPI web UI implementation and `shoppybot web` full behavior (Phase 10) — Phase 9 only ships the lazy-import seam.
- `--json` output for `items list` — add later if a real consumer needs it.
- Richer `config set` coverage beyond the scalar allowlist — future.
- Cross-platform verification matrix / CI (Phase 11).
</deferred>

---

*Phase: 9-cli-front-end*
*Context gathered: 2026-06-04 via smart discuss (autonomous)*
