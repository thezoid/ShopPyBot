---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Resilience + Ecosystem
status: verifying
last_updated: "2026-06-09T07:24:49.376Z"
last_activity: 2026-06-09
progress:
  total_phases: 6
  completed_phases: 2
  total_plans: 7
  completed_plans: 7
  percent: 33
---

# ShopPyBot — State

## Project Reference

**Core Value**: Drop-in plugin framework — community adds retail platform integrations via a single Python file in `plugins/`; no core changes required.

**Project**: ShopPyBot
**Milestone**: v3.0 Resilience + Ecosystem
**Total Phases**: 6 (Phases 12-17)
**Total Requirements**: 18

---

## Current Position

Phase: 13 (anti-detection-layer-1-fingerprint-proxy) — COMPLETE
Plan: 3 of 3
Status: Phase 13 complete -- all 3 plans done; ready for Phase 14 planning
Last activity: 2026-06-09 -- Phase 13 Plan 03 complete (stealth+proxy wired into all 8 plugins)

## Phase Status

| Phase | Goal Summary | Status | Reqs |
|-------|-------------|--------|------|
| 12 — Stability Foundation | Close v2.0 deferred OS checks + 4 audit tech-debt items | Not started | 2 |
| 13 — Anti-Detection Layer 1 (Fingerprint + Proxy) | JS stealth patch + proxy rotation with ban detection | Not started | 3 |
| 14 — Anti-Detection Layer 2 (CAPTCHA Solving) | 2captcha opt-in with balance check, async executor, spend cap | Not started | 2 |
| 15 — Plugin Ecosystem Registry | ABC difficulty attrs, GitHub wiki table, plugins list CLI, updated contributor docs | Not started | 4 |
| 16 — Price Monitoring | Per-item target price, price history table, fan-out alerts, price-history CLI | Not started | 6 |
| 17 — Test Hardening | Unit + integration coverage for all v3.0 features | Not started | 1 |

---

## Performance Metrics

**Plans completed**: 2 (Phase 13 Plans 01-02)
**Requirements completed**: 4 (ANTI-08, ANTI-04 core logic, ANTI-04 config surface, ANTI-05 core logic)
**Phases completed**: 0
**Blockers resolved**: 0

---

## Accumulated Context

### Key Decisions Logged

- [Phase 10-01]: create_app() router imports deferred inside factory body to avoid circular import; all fastapi imports confined to web/ package (CLI-04)
- [Phase 10-01]: WEB_ALLOWLIST extends CLI ALLOWLIST with 4 notifier toggles only (no platform enables -- AppConfig has no enabled field per config-scope-note)
- [Phase 10-01]: TemplateResponse uses new Starlette API signature: TemplateResponse(request, name, context) to avoid DeprecationWarning
- Plugin interface: only `check_availability` and `auto_buy` are abstract; `login` and `detect_captcha` get no-op defaults — preserves contributor-friendliness
- Plugin naming convention enforced: `shopbot_plugin_*.py`; non-matching files get a warning log, not a crash
- One WebDriver instance per plugin (`self.driver` in `__init__`); no shared global driver — required for async safety
- CVV via `getpass` at runtime; credentials via env vars only — must be complete before open source launch
- SMS/Twilio is opt-in disabled by default to prevent accidental charges
- nodriver preferred over Selenium for new plugins (async-native, bot-detection resistant); Selenium retained for Phase 1/2 refactor continuity

### Research Flags (carry into planning)

- Phase 13 (proxy): Authenticated proxy support is broken in nodriver via `--proxy-server`; must use CDP `Fetch.continueWithAuth` or IP-allowlisted proxies only — fail loudly, never silently fall back to direct connection (PITFALLS 1.1)
- Phase 13 (proxy): WebRTC leaks real IP through proxied sessions; inject three Chrome prefs at browser launch to disable non-proxied UDP (PITFALLS 1.2)
- Phase 13 (proxy): Proxy selection must be per plugin instance (`self._proxy`), never a module-level singleton (PITFALLS 1.6)
- Phase 13 (fingerprint): Apply fingerprint overrides in `setup()` before first navigation only; test against CreepJS before merging; Chrome-only UAs in rotation pool (PITFALLS 3.2, 3.3)
- Phase 14 (CAPTCHA): Add `CAPTCHA_API_KEY` to `SECRET_KEYS` before writing any CAPTCHA code; no `captcha.api_key` field in Pydantic schema (PITFALLS 2.2)
- Phase 14 (CAPTCHA): Wrap solve call with `run_in_executor` + `asyncio.timeout(120)` mandatory — sync SDK blocks event loop (PITFALLS 2.3)
- Phase 16 (price): Use JSON-LD > OG > CSS extraction cascade; store raw price text alongside parsed float to enable debugging (PITFALLS 4.1)
- Phase 16 (price): Price alert state uses dedicated columns (`price_alert_armed`, `price_last_notified`) — do not reuse `last_notified` which tracks stock dedup (PITFALLS 7.2)
- Phase 16 (price): Idempotent `ALTER TABLE` with `PRAGMA table_info` check for every new column; CI migration fixture test against v2.0 DB (PITFALLS 4.4)
- Phase 15 (registry): GitHub wiki is directory listing only; all API contract docs live in `PLUGIN_DEV.md` in-repo (PITFALLS 5.1)
- All phases: Log only `exc.__class__.__name__` on proxy/CAPTCHA exception paths — never `str(exc)` which may contain credential strings in URLs (PITFALLS 6.4)

### Active Todos

- Run `/gsd:plan-phase 12` to begin Phase 12 planning

### Blockers

- None

---

## Deferred Items

Items acknowledged and deferred at v2.0 milestone close on 2026-06-05. All are live cross-OS/UI manual checks documented in docs/PLATFORMS.md; none are code gaps. Phase 12 closes all of these.

| Category | Item | Status |
|----------|------|--------|
| verification | Phase 08 — keyring/encrypted-file live backend selection + restart persistence | human_needed |
| verification | Phase 09 — masked-TTY setup entry (Windows PowerShell + Ubuntu) | human_needed |
| verification | Phase 10 — web dashboard live render / Start-Stop / log poll / 0.0.0.0 warning | human_needed |
| verification | Phase 11 — live cross-OS path + backend matrix | human_needed |
| uat | Phase 11 — 11-HUMAN-UAT.md (6 live cross-OS scenarios) | partial (6 pending) |
| uat | Phase 01 — 01-UAT.md | partial (0 pending) |

---
| Phase 13 P01 | 7min | 2 tasks | 2 files |
| Phase 13 P02 | 5min | 2 tasks | 3 files |
| Phase 12-stability-foundation P01 | 3min | 2 tasks | 2 files |
| Phase 12-stability-foundation P02 | 237 | 2 tasks | 2 files |
| Phase 12 P03 | 4min | - tasks | - files |
| Phase 12 P04 | 5min | 2 tasks | 1 files |
| Phase 13 P03 | 13min | 3 tasks | 11 files |

## Session Continuity

**Last action**: Phase 13 Plan 03 complete -- stealth+proxy wired end-to-end: service startup log, orchestrator ProxyPool construction, registry.assign_proxy, all 8 plugins (ANTI-04/ANTI-05/ANTI-08)
**Next action**: Run /gsd:plan-phase 14 to begin CAPTCHA Solving planning
**Context to carry**: Phase 13 fully complete. 414 tests passing. PLUGIN_API_VERSION=2 (no bump). Proxy rotation disabled by default; opt-in via cfg.proxy.enabled. Each plugin receives self._proxy from registry.assign_proxy before setup(). Fail-loud on pool exhaustion. apply_stealth called before first nav in all 8 plugins.

---

*Last updated: 2026-06-07 — v3.0 roadmap created by gsd-roadmapper*

## Performance Metrics (v1 + v2.0 history)

| Phase | Plan | Duration | Notes |
|-------|------|----------|-------|
| Phase 01-foundations-security P01 | 8m | 3 tasks | 5 files |
| Phase 01 P02 | 5m | - tasks | - files |
| Phase 01 P03 | 5m | 2 tasks | 2 files |
| Phase 01 P04 | 8min | 3 tasks | 3 files |
| Phase 01 P05 | 11min | 3 tasks | 4 files |
| Phase 02-plugin-migration P01 | 207 | 2 tasks | 2 files |
| Phase 02-plugin-migration P03 | 20m | 2 tasks | 2 files |
| Phase 02-plugin-migration P04 | 20min | 2 tasks | 4 files |
| Phase 02-plugin-migration P06 | 15 | 2 tasks | 3 files |
| Phase 02-plugin-migration P05 | 10 | 1 tasks | 1 files |
| Phase 03-community-documentation P01 | 8m | 2 tasks | 3 files |
| Phase 03-community-documentation P02 | 5min | 2 tasks | 5 files |
| Phase 04-async-orchestrator P01 | 15 | 2 tasks | 3 files |
| Phase 04-async-orchestrator P04 | 15m | 2 tasks | 5 files |
| Phase 04-async-orchestrator P05 | 15 | 1 tasks | 3 files |
| Phase 05-notification-system P02 | 12m | 2 tasks | 3 files |
| Phase 05-notification-system P03 | 4m | 2 tasks | 3 files |
| Phase 05-notification-system P04 | 3 | 1 tasks | 3 files |
| Phase 05-notification-system P05 | 25 | 2 tasks | 4 files |
| Phase 06-platform-expansion P01 | 15 | 2 tasks | 9 files |
| Phase 06-platform-expansion P06-02 | 5 minutes | - tasks | - files |
| Phase 06 P03 | 12 | 3 tasks | 9 files |
| Phase 06-platform-expansion P04 | 4m | 2 tasks | 4 files |
| Phase 06-platform-expansion P05 | 5m | 2 tasks | 2 files |
| Phase 07-modular-core-service P01 | 375s | 2 tasks | 3 files |
| Phase 07-modular-core-service P02 | 4min | 1 tasks | 3 files |
| Phase 07-modular-core-service P03 | 5m | 2 tasks | 2 files |
| Phase 08-credential-store P01 | 8min | 3 tasks | 4 files |
| Phase 08-credential-store P02 | 7min | 2 tasks | 3 files |
| Phase 08 P03 | 12min | 3 tasks | 4 files |
| Phase 08-credential-store P04 | 15min | 3 tasks | 14 files |
| Phase 09-cli-front-end P01 | 12m | 3 tasks | 15 files |
| Phase 09-cli-front-end P02 | 8min | 2 tasks | 4 files |
| Phase 09-cli-front-end P03 | 4min | 2 tasks | 2 files |
| Phase 09-cli-front-end P04 | 4m | 1 tasks | 1 files |
| Phase 10-optional-web-ui P01 | 15m | 3 tasks | 21 files |
| Phase 10-optional-web-ui P02 | 6m | 2 tasks | 2 files |
| Phase 10-optional-web-ui P03 | 3m | 1 tasks | 1 files |
| Phase 10-optional-web-ui P04 | 8min | 2 tasks | 3 files |
| Phase 11 P01 | 5m | 3 tasks | 4 files |
| Phase 11 P02 | 8min | 3 tasks | 5 files |
| Phase 11 P03 | 7m | 3 tasks | 3 files |
| Phase 11 P04 | 8m | 2 tasks | 2 files |

## Decisions

- [Phase ?]: Used importlib.reload + monkeypatch.chdir in tests to isolate config.py module-level load without touching production code
- [Phase ?]: PLUGIN_API_VERSION defined module-level before class body; importable without instantiation (T-01-VER)
- [Phase 01-03]: yaml_file= constructor kwarg (not _yaml_file=) used for test injection; _active_yaml_file class sentinel bridges __init__ to classmethod settings_customise_sources
- [Phase 01-03]: No env_prefix on AppConfig; single-user tool keeps DEBUG__LOGGING_LEVEL format simpler than SHOPBOT_DEBUG__LOGGING_LEVEL
- [Phase ?]: [Phase 01-04]: Pinned all deps to exact installed versions; added nodriver==0.50.3 and pydantic-settings[yaml]==2.14.0 after human package-legitimacy approval; logger caches level at import (_LOGGING_LEVEL), eliminating per-loop config.yml reads
- [Phase ?]: Phase-1 SEC-04: navigator.webdriver hidden on the existing Selenium driver via CDP injection; nodriver replaces it in Phase 2
- [Phase ?]: Credentials sourced from env vars (BB_EMAIL/BB_PASSWORD); CVV via runtime getpass, never persisted or logged
- [Phase ?]: open_browser hardcoded False pending AppConfig relocation (app block removed for SEC-01)
- [Phase ?]: pytest-asyncio 1.3.0 with asyncio_mode=auto: no decorators needed on plain async def test_ functions
- [Phase ?]: _route_all routes against _all_plugins to enable lazy-launch before active list is populated
- [Phase ?]: D-02 closed: nodriver handles stealth architecturally; Selenium imports gone
- [Phase ?]: Placeholder email SECURITY_CONTACT_PLACEHOLDER@example.com in SECURITY.md and CODE_OF_CONDUCT.md; maintainer must replace before launch
- [Phase ?]: Anchored /config.yml in .gitignore to repo root to prevent ISSUE_TEMPLATE/config.yml exclusion
- [Phase ?]: config.yml contact_links url points to SECURITY.md blob on master branch for private vulnerability reporting
- [Phase ?]: TaskGroup of per-plugin coroutines with 1.5s stagger and single write-queue drain via asyncio.Queue
- [Phase ?]: stdin listener thread uses loop.call_soon_threadsafe as the only thread-safe Event bridge; no direct event.set() from non-loop threads (ASYNC-03)
- [Phase ?]: run_in_executor used only for sqlite3 calls and stdin readline; nodriver browser work stays on the event loop (ASYNC-01 primary model)
- [Phase ?]: SoundNotifier: synchronous pygame calls (no executor, thread-safety unconfirmed)
- [Phase ?]: DiscordNotifier: secret-safe error logging (class+status only, never webhook URL or str(exc))
- [Phase ?]: Discord 429: raises RuntimeError with Retry-After; no retry loop in Phase 5 scope
- [Phase ?]: build_dispatcher factory selects notifiers from config flags; dedup edge-trigger notifies once per restock via get_item_notification_state_sync
- [Phase ?]: squareenix (no underscore) chosen for config key
- [Phase ?]: Naming difference is intentional and documented
- [Phase ?]: No separate helper module; Option A from RESEARCH Pattern 4
- [Phase ?]: getattr-chain platform_key lookup: no hardcoded class-name string munging for jitter config
- [Phase ?]: ANTI-02 UA always active -- falls back to DEFAULT_USER_AGENTS when platform user_agents empty
- [Phase ?]: SC1 registry gate
- [Phase 07-01]: BotService uses daemon thread with its own asyncio event loop for non-blocking start/stop from any sync caller
- [Phase 07-01]: stop() cancels task via loop.call_soon_threadsafe so async_main's finally block runs teardown_all (no orphaned Chrome)
- [Phase 07-01]: run() = asyncio.run(async_main(cfg, cvv)) identical to v1 behavior; CVV is a parameter only (never logged)
- [Phase ?]: parse_known_args() in core.service:main() avoids sys.argv contamination when test calls main() directly
- [Phase ?]: plugins/__init__.py added to make plugins/ a proper setuptools package; Phase 07-02 shoppybot entry point = core.service:main via pyproject.toml [project.scripts]
- [Phase 07-03]: main.py is now a thin shim: validate+seed+getpass CVV gate then BotService(cfg).run(cvv); asyncio.run and async_main imports removed from main.py (now internal to core/service.py)
- [Phase ?]: get_store lazy-fallback to EnvVarBackend keeps monkeypatch.setenv tests green (CRED-04)
- [Phase ?]: _build_store stub returns EnvVarBackend in plan 08-01; auto-detection keyring->file->env deferred to plan 08-03
- [Phase ?]: KeyringBackend uses SERVICE=shopbot hardcoded; keyring has no enumerate API so list() probes each SECRET_KEY individually (CRED-02)
- [Phase ?]: EncryptedFileBackend: scrypt n=2**14 + fresh 16B salt per write; fdopen-in-with + os.replace-outside for Windows-safe atomic write; InvalidToken -> ValueError(SHOPBOT_STORE_PASSPHRASE) (CRED-03)
- [Phase ?]: _build_store: explicit config > real keyring > encrypted-file (passphrase in env) > env-var; getpass deferred to explicit 'file' backend path only
- [Phase ?]: get_store().get(KEY) replaces all os.environ secret reads in consumers; SC1 grep guard enforces no regression
- [Phase 09-01]: build_parser() in core/cli/__init__.py owns the parser; core/service.py:main() delegates to it via build_parser() + parse_known_args(argv)
- [Phase 09-01]: parse_known_args(argv) with explicit argv=None param; tests pass argv=[] to avoid sys.argv contamination in Python 3.13 strict subparser choices
- [Phase 09-01]: handle_setup stub handles --migrate branch for back-compat; full interactive prompt body deferred to plan 09-02
- [Phase ?]: [Phase 09-02]: handle_config_set raises SystemExit(2) for unknown keys -- consistent with _coerce pattern, required by test scaffold
- [Phase ?]: [Phase 09-02]: sys.stdin.readline() in _prompt_backend instead of input() -- ASYNC-03 compliance
- [Phase ?]: [Phase 09-02]: setup._write_backend reads _DEFAULT_YAML_PATH via import core.cli.config_cmd at call-time for monkeypatch testability
- [Phase ?]: web.py lazy-import seam was correct from 09-01 stub; CLI-04 guard tests unskipped with SystemExit fix for run subcommand dispatch
- [Phase ?]: bot_stop uses run_in_executor to dispatch blocking svc.stop() off event loop (T-10-08 mitigation)
- [Phase ?]: svc.start() called with zero args (no CVV) per locked web-scope decision
- [Phase ?]: bool() coercion applied to auto_buy and purchased when serializing 5-tuples to JSON items list
- [Phase 10-03]: import core.credentials as module (not from-import) so patch("core.credentials.get_store") resolves the reference at call time in tests
- [Phase ?]: [Phase 10-04]: Config routes in web/routes/config.py; WEB_ALLOWLIST gate (notifier toggles only, no platform enabled fields); SC3 HTML-leak guard test green
- [Phase ?]: [Phase 11-01]: appauthor=False suppresses redundant vendor subdir on Windows for platformdirs
- [Phase ?]: [Phase 11-01]: data_dir/config_path/log_dir re-read SHOPBOT_DATA_DIR on every call; env override seam keeps 341 tests green
- [Phase ?]: [Phase 11-01]: platformdirs==4.10.0 pinned in requirements.txt and pyproject.toml core deps; tox-dev org, pre-vetted
- [Phase ?]: [Phase 11-02]: logger.py lazy-imports core.paths.log_dir inside writeLog to avoid circular import with Plan 03
- [Phase ?]: [Phase 11-04]: items list smoke pre-initializes DB via initialize_db() -- BotService.__init__ only calls init_store(), not initialize_db()
- [Phase ?]: Option A (lazy import inside _load_logging_level) chosen over Option B (delete _CONFIG_PATH) to retain the constant for tooling inspection
- [Phase ?]: [Phase 12-01]: TD-1 test isolation via finally-block reload: both tests restore logger to original import-time state to prevent _LOGGING_LEVEL bleed
- [Phase ?]: TD-2 closed: Switch all three dirs_to_scan to rglob (not just core/) for future-proofing; companion assertion on core/cli/config_cmd.py proves recursion coverage
- [Phase ?]: TD-3 closed: Separator guard anchored to Path(__file__).parent.parent with len(src_files)>0 guard; silent empty-list false-pass eliminated
- [Phase ?]: [Phase 12-03]: TD-4 config seam accepted under MOD-02 -- write_web_config writes directly to _DEFAULT_YAML_PATH; BotService scope covers DB/registry/orchestrator only; WEB_ALLOWLIST is the safety boundary
- [Phase ?]: [Phase 12-03]: MC-4 is_non_local banner gate proven both ways -- banner present when is_non_local=True, absent when is_non_local=False (Jinja2 conditional enforced in CI)
- [Phase 12-04]: MC-1..MC-4 Windows variants recorded PENDING in docs/PLATFORMS.md (non-interactive agent env, no real TTY/restart cycle); MC-4 CI-asserted by tests/test_web_dashboard.py Plan 12-03; Ubuntu variants pending Ubuntu access
- [Phase 13-01]: _parse_proxy_url uses stdlib urlparse; host_port always separate from credentials (T-13-01 mitigation; host_port stored on _ProxyEntry at construction time)
- [Phase 13-01]: setup_proxy_auth is a no-op when username is empty; add_handler called before fetch.enable to avoid missing first 407 challenge (Pitfall 4)
- [Phase 13-01]: ProxyPool.advance() returns None when all proxies retired; caller must fail loudly, never silently fall back to direct connection (Pitfall 2)
- [Phase 13-01]: time.monotonic used for cooldown retired_until timestamps; module-level time attribute patched in tests (not global monotonic) for testability
- [Phase 13-02]: ProxyConfig placed after CredentialsConfig before AppConfig; proxy: ProxyConfig = ProxyConfig() default-instance pattern; no model_validator or os.environ reads in ProxyConfig (credentials live in config.yml per RESEARCH Open Question 3)
- [Phase 13-02]: sample.config.yml proxy example uses proxy.example.com placeholder only; real URLs in user's gitignored config.yml
- [Phase ?]: [Phase 13-03]: Per-instance proxy scoping via registry.assign_proxy; conftest mock_nodriver_start gets AsyncMock on main_tab.send for apply_stealth compatibility

## Operator Next Steps

- Run `/gsd:plan-phase 12` to begin Stability Foundation planning
