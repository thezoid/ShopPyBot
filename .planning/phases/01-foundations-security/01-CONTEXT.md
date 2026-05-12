# Phase 1: Foundations + Security - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Lock the plugin ABC contract and `PLUGIN_API_VERSION = 1`, validate `config.yml` at startup with Pydantic, and harden every credential and driver security gap so the codebase is safe to publish open source. The existing Selenium-based Amazon and BestBuy bots remain runnable end-to-end through Phase 1; the nodriver swap and plugin migration happen atomically in Phase 2.

Scope: 14 requirements (CORE-01, CORE-02, CORE-05, CORE-06, CORE-07, SEC-01..06, INFRA-01..03).

Out of scope for Phase 1: refactoring Amazon/BestBuy bots into plugin form (Phase 2), nodriver adoption (Phase 2), async orchestrator (Phase 4), notifications (Phase 5).
</domain>

<decisions>
## Implementation Decisions

### D-01: Plugin ABC method signatures (Area 1)
- ABC method signatures drop the `driver` parameter. Methods take only `self` plus domain args.
- Final shapes:
  - `check_availability(self, url: str) -> bool` (abstract)
  - `auto_buy(self, url: str, config) -> bool` (abstract)
  - `login(self, config) -> None` (no-op default)
  - `detect_captcha(self) -> bool` (no-op default returning False)
- Plugin owns its driver as `self.driver`, constructed in `__init__`.
- This **revises CORE-01 wording** in REQUIREMENTS.md (currently lists `driver` as a parameter on three methods). REQUIREMENTS.md must be edited during planning to match.

### D-02: Plugin `__init__` shape (Area 1, follow-up)
- Signature: `__init__(self, platform_config)`.
- Orchestrator slices `AppConfig.platforms.<name>` and passes only that platform's block.
- Plugin constructs `self.driver` synchronously inside `__init__`. Phase 4 may revisit if nodriver requires async-only construction.
- No global config import inside plugins. No cross-platform reads from `__init__`.

### D-03: Selenium drop deferred to Phase 2 (Area 2)
- Phase 1 keeps Selenium and `webdriver_manager` in `requirements.txt`.
- Phase 1 hardens the **existing** Selenium driver against bot-detection signals:
  - SEC-03: remove `--disable-web-security` flag from `ChromeOptions`.
  - SEC-04: hide `navigator.webdriver` via Selenium's CDP command (`execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", ...)`).
  - SEC-05: real Chrome user agent string set via `ChromeOptions.add_argument(f"user-agent={...}")`.
- Phase 2 swaps Selenium for nodriver atomically with the plugin migration (PLG-01, PLG-02, PLG-03).
- HANDOFF.json decision tagged "Drop Selenium → nodriver, phase: 1" should be retagged Phase 2 in any future state regeneration.
- Bot remains runnable end-to-end after every Phase 1 plan ships.

### D-04: CVV prompt timing (Area 3)
- `getpass.getpass()` fires **once at startup**, looping over enabled platforms that have `auto_buy: true` on at least one item.
- CVV held only in memory (no persistence, no logging).
- If a CVV is required but missing, the bot exits before entering the polling loop (fail-fast).

### D-05: Non-TTY behavior (Area 3, follow-up)
- Default: when `sys.stdin.isatty()` is False and any platform has `auto_buy: true`, the bot exits with a clear error message.
- Opt-in escape hatch for headless deployments (systemd, container, cron):
  - User must set `SHOPBOT_ALLOW_CVV_ENV=true` (acknowledgement flag).
  - Per-platform CVV read from `SHOPBOT_<PLATFORM>_CVV` env var (e.g., `SHOPBOT_AMAZON_CVV`).
  - Documented in SEC-06 README disclaimer as "trusted infrastructure only".
- Without the opt-in flag, the env var is ignored even if set.

### D-06: Config migration policy (Area 4)
- On startup, Pydantic validation also scans for **deprecated keys** (`app.amz_email`, `app.amz_pwd`, `app.bb_email`, `app.bb_password`).
- If any old key is detected:
  1. Print a structured migration block listing each old key and its new location (env var or `platforms.<name>.<field>`).
  2. Exit with non-zero status.
  3. Do **not** read or remap old credential fields under any circumstance (would defeat SEC-01).
- No back-compat shim. No auto-rewrite. User edits `config.yml` once and re-runs.

### D-07: Pydantic strictness + env var naming (Area 5, Claude default)
- `model_config = SettingsConfigDict(extra="forbid", env_nested_delimiter="__", env_prefix="SHOPBOT_")`.
- Unknown config keys produce an actionable Pydantic validation error at startup (CORE-05 acceptance).
- Env var convention: `SHOPBOT_PLATFORMS__AMAZON__EMAIL`, `SHOPBOT_PLATFORMS__BESTBUY__PASSWORD`, etc. (pydantic-settings nested delimiter syntax).
- CVV env vars under the opt-in flag use a flat name: `SHOPBOT_AMAZON_CVV`, `SHOPBOT_BESTBUY_CVV` (separate from the nested config schema; CVV is runtime-only).

### Claude's Discretion
- Exact wording of Pydantic validation error messages.
- Internal module layout under a `core/` package vs flat root (codebase currently flat; planner will choose during PATTERNS analysis).
- Logger singleton implementation pattern for INFRA-02 (module-level vs `functools.cache` vs metaclass).
- Whether `requirements.txt` pins use `==X.Y.Z` only or `==X.Y.Z` with hash pins.
- Choice of `getpass` exception handling (KeyboardInterrupt at prompt = exit 130 vs treat as opt-out).

### Folded Todos
None — no pending todos crossed Phase 1 scope.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project-level specs
- `.planning/PROJECT.md` — full decision log, core value, constraints
- `.planning/REQUIREMENTS.md` — 44 requirements; **CORE-01 needs revision per D-01 before planning**
- `.planning/ROADMAP.md` §"Phase 1: Foundations + Security" — goal statement, success criteria, requirement list
- `.planning/research/SUMMARY.md` — recommended stack changes, top 5 pitfalls (especially #1, #2, #3, #5 for Phase 1)

### Codebase analysis
- `.planning/codebase/STRUCTURE.md` — current flat module layout, where to add new code
- `.planning/codebase/CONCERNS.md` — existing technical debt the phase must address
- `.planning/codebase/CONVENTIONS.md` — naming and patterns to preserve
- `.planning/codebase/STACK.md` — current dependency state

### External library docs (planner should query Context7 during planning)
- `pydantic-settings` 2.13.1 — `SettingsConfigDict`, `env_nested_delimiter`, YAML source loader
- `pydantic` 2.x — `field_validator`, `model_validator`, `ValidationError` formatting
- Selenium 4.x `execute_cdp_cmd` — for SEC-04 webdriver-property hiding via CDP
- Selenium 4.x `ChromeOptions` — for SEC-03 flag removal and SEC-05 user agent override

### Operational state
- `.planning/STATE.md` — **stale**: claims 5 phases / 39 reqs; ROADMAP.md is authoritative (6 phases / 44 reqs). Reconcile during planning or via small docs commit.
- `.planning/HANDOFF.json` — pause-state from project init; the "Drop Selenium → nodriver, phase: 1" decision is retagged to Phase 2 per D-03.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `models.py` — SQLite CRUD layer for items table; keep as-is for Phase 1, the WAL mode + write queue work is Phase 4 (ASYNC-04, ASYNC-05).
- `utils.py` — pygame sound playback; untouched in Phase 1, wrapped by `SoundNotifier` in Phase 5.
- `tests/` — existing pytest suite (`test_config.py`, `test_models.py`, `test_utils.py`); Phase 1 plans must add tests for Pydantic validation, ABC import, CDP patch, env-var credential read.

### Established Patterns
- Flat module layout (no `src/` directory). Phase 1 introduces the plugin ABC and Pydantic config schema; placement under a new `core/` package is a planner decision.
- snake_case modules; verb-prefixed snake_case functions (`check_amazon_item`, `update_item_purchased`).
- Custom `writeLog(message, type)` logger with verbosity levels in config (`debug.logging_level` 0..5). INFRA-02 fixes the per-call config re-read.

### Integration Points
- `config.py` — singleton `config` dict loaded at import time. Phase 1 replaces this with a Pydantic `AppConfig` instance; every consumer (`main.py`, `amazon_bot.py`, `bestbuy_bot.py`, `logger.py`, `utils.py`) currently does `from config import config`. Migration touches the whole codebase.
- `main.py` lines 92-136 — domain routing (`if "amazon.com" in link`...). Phase 1 leaves this intact; the plugin registry that replaces it is Phase 2 (CORE-03, CORE-04).
- `amazon_bot.py` / `bestbuy_bot.py` driver setup — Phase 1 modifies the existing `webdriver.Chrome(...)` call sites for SEC-03/04/05 (remove `--disable-web-security`, add CDP webdriver hide, set real UA). Plugin extraction is Phase 2.
- `requirements.txt` — INFRA-01 pins all versions, removes duplicates, adds `python_requires >= 3.11` declaration to `setup.py` or `pyproject.toml`.
- `main.py` line ~1 (sys.stdout monkey-patch block) — INFRA-03 deletes this and routes ChromeDriver output via `Service(log_path=...)`.

### Anti-patterns to NOT carry forward
- Shared global WebDriver: Phase 1 does not introduce one driver per plugin (that is Phase 2 PLG-03). Phase 1 leaves the current shared driver in place but does NOT add new code that depends on it.
- `config.yml` re-read per log call: INFRA-02 fixes this in Phase 1.
- Plaintext credentials in `config.yml`: SEC-01 moves these to env vars in Phase 1; `sample.config.yml` updates to show only env-var pointers.
- `--disable-web-security` flag: SEC-03 removes in Phase 1.
</code_context>

<specifics>
## Specific Ideas

- The `PluginDriver` Protocol option (Area 1, Option B) was considered and rejected. If a future major version wants to support drivers other than nodriver, that becomes a `PLUGIN_API_VERSION = 2` migration. Captured here so future planners do not re-litigate.
- The migration block printed by D-06 should be a single ASCII block the user can copy-paste into a comment, listing each old `app.<key>` and its replacement (env var name OR new `platforms.<name>.<field>` location). Exact format is a planner-level detail.
- Hard-fail message for D-05 (non-TTY) must instruct the user how to opt in (`SHOPBOT_ALLOW_CVV_ENV=true`) AND warn that this stores CVV in a process env var visible to anything reading `/proc/<pid>/environ`.
</specifics>

<deferred>
## Deferred Ideas

- Driver Protocol abstraction (`PluginDriver`) for multi-driver support — defer to v2 / `PLUGIN_API_VERSION = 2`.
- Auto-migration of old `config.yml` to new schema with `.bak` backup — explicitly rejected in D-06; revisit only if user feedback shows the manual migration is too painful.
- Two-phase async `__init__` + `setup()` for nodriver-native plugins — not needed in Phase 1 since Selenium is sync; Phase 4 (async orchestrator) revisits if nodriver requires async construction.
- Per-purchase CVV prompting — rejected in D-04; revisit if shared-workstation / paranoid-mode users request it.
- Pre-commit hook scanning for `_pwd` / `_cvv` patterns in committed files — research SUMMARY.md mentions this as a defense layer; not a Phase 1 requirement, captured for INFRA backlog.
</deferred>

---

*Phase: 01-foundations-security*
*Context gathered: 2026-05-02*
