# Phase 17: Test Hardening - Context

**Gathered:** 2026-06-09
**Status:** Ready for planning
**Mode:** Infrastructure phase (test hardening) — scope-bounded; minimal grey areas

<domain>
## Phase Boundary

Close unit + integration coverage gaps for the NEW v3.0 features so CI catches regressions (STAB-03). Scope is exactly the four v3.0 feature surfaces, mapped to the success criteria:
1. **Proxy** (Phase 13): proxy config parsing, ban-signal detection, per-instance proxy scoping, cooldown/retire logic.
2. **CAPTCHA** (Phase 14): captcha config parsing, balance-check behavior, run_in_executor wrapping, spend-cap (max_solves) enforcement.
3. **Price** (Phase 16): price comparison/threshold logic, `price_history` DB schema INCLUDING idempotent migration against a real v2.0-schema DB fixture, and price-drop dedup separation from stock-alert dedup.
4. **Plugin ABC** (Phases 15+16): `difficulty`/`requires_proxy`/`requires_captcha` defaults+overrides, and the `get_price()` hook being called alongside `check_availability` in the poll cycle.

</domain>

<decisions>
## Implementation Decisions

### Scope discipline (Claude's Discretion within these fences)
- Target ONLY the v3.0 feature code paths. Do NOT chase blanket coverage of pre-existing v1/v2 plugin code (e.g. legacy `check_availability`/`login`/`auto_buy` bodies, `example_plugin.py`) — that is out of STAB-03 scope and the v3.0 "Out of Scope" list explicitly excludes end-to-end retail checkout tests (legal/TOS + impractical in CI).
- New tests must be deterministic and CI-safe: NO live browser, NO live network, NO real 2captcha/proxy/Amazon. Mock the nodriver tab/CDP, `requests`, and notifier channels (existing test patterns already do this).
- All new tests are additions to the existing pytest suite under `tests/`; reuse existing fixtures/conftest. No new runtime dependency. `pytest-cov` is already installed (7.1.0).

### Required new coverage (from the coverage baseline)
- **v2.0 DB migration fixture (criterion 3, currently MISSING):** a test that builds a SQLite DB with the v2.0 `items` schema (no v3.0 columns / no `price_history`), runs `initialize_db()`, and asserts the new columns + `price_history` table are added with NO data loss and the run is idempotent (run twice). This is the highest-value gap.
- Fill the concrete uncovered branches surfaced by coverage: `core/captcha.py` error/balance/spend-cap paths, `core/registry.py` proxy-scoping (`assign_proxy`/`assign_solver`) branches, `core/stealth.py` ProxyPool cooldown/retire + ban-detect edges, the orchestrator price-path + `get_price()`-alongside-`check_availability` integration.

### Definition of done for the phase
- Each of the 4 success criteria maps to named passing tests. Full suite stays green. Measured coverage of the v3.0 feature modules rises (the gap-analysis report enumerates the specific missing tests).

### Claude's Discretion
- Exact test file organization (extend existing `tests/test_*` files vs. add focused new ones), fixture design for the v2.0 DB, and which specific uncovered lines are worth a test vs. unreachable/trivial — guided by the coverage report and the gap-analysis (RESEARCH) output.

</decisions>

<code_context>
## Existing Code Insights

### Coverage baseline (v3.0 modules, measured 2026-06-09)
- core/stealth.py 93%, core/captcha.py 84%, core/config_schema.py 99%, core/plugin_base.py 100%, core/registry.py 82%, core/service.py 91%, core/orchestrator.py 84%, models.py 94%, notifiers 86-100%, plugins/shopbot_plugin_amazon.py 59% (mostly legacy paths — out of scope).
- 531 tests currently collected; suite green (529 passed, 2 skipped at last run).

### Reusable Assets
- `tests/conftest.py` fixtures (fake nodriver browser/tab, `initialize_db(delete=True)`), existing `tests/test_stealth.py`, `test_proxy_config.py`, `test_proxy_wiring.py`, `test_captcha*.py`, `test_price_*.py`, `test_plugin_base.py`, `test_cli_*.py` as patterns.
- `models.py` idempotent migration (`PRAGMA table_info` + `ALTER`/`CREATE TABLE IF NOT EXISTS`).

### Integration Points
- The plugin-ABC + get_price()-alongside-check_availability integration lives in `core/orchestrator.py` `_check_and_buy`; the registry proxy/solver assignment in `core/registry.py`.

</code_context>

<specifics>
## Specific Ideas

- The v2.0-DB-fixture idempotent-migration test is explicitly named in criterion 3 and is the key missing piece.
- Integration coverage for the plugin ABC additions (criterion 4) must assert defaults AND overrides, and that `get_price()` is invoked in the poll cycle alongside `check_availability`.

</specifics>

<deferred>
## Deferred Ideas

- End-to-end retail checkout tests in CI — Out of Scope (v3.0).
- Blanket coverage of legacy v1/v2 plugin code — out of STAB-03 scope.
- Live-environment manual checks for v3.0 features remain tracked in the per-phase HUMAN-UAT files (12,13,14,15,16).

</deferred>
