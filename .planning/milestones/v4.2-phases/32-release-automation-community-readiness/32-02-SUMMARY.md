---
phase: 32-release-automation-community-readiness
plan: 02
subsystem: docs
tags: [readme, documentation, badges, community-readiness]

# Dependency graph
requires:
  - phase: 32-01
    provides: pyproject.toml version reconciled to 2.0.0; release-please.yml, codeql-analysis.yml, ci.yml, gitleaks.yml workflows confirmed as the only existing workflow files
provides:
  - Accurate, current README.md documenting the 7-platform plugin ecosystem, web dashboard/observability, price monitoring, anti-detection, and encrypted session persistence
  - Correct install/run instructions (pip install -e .[web], shoppybot entry point, Python 3.11+, real clone URL)
  - Badges that resolve to live workflows only, plus a static Python-version badge; no fabricated license badge
  - Credential guidance aligned with SECURITY.md's env-var/.env model
affects: [32-03, README consumers, new contributors/operators]

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified: [README.md]

key-decisions:
  - "Simplified the badge block from a master/dev two-row split to a single master-branch row (CI, CodeQL, Gitleaks) plus one static Python 3.11+ badge — the original dev-branch duplication wasn't required by the plan and added no reader value"
  - "Left the per-platform (Best Buy / Amazon) account-prerequisite subsections under Setup untouched — out of this plan's explicit task scope (task 1 only specified prereq version, clone URL, install command; task 2 scope was Overview/Features/Configuration/Credits), avoiding scope creep per CLAUDE.md Scope Control"
  - "Configuration section restructured to 3 numbered steps (copy config, edit non-secret items, set up .env credentials) instead of patching the old single wrong instruction, since the old step conflated non-secret config with secret credentials"

patterns-established: []

requirements-completed: [RH-06]

# Metrics
duration: 9min
completed: 2026-07-02
---

# Phase 32 Plan 02: README Accuracy Rewrite Summary

**Rewrote README.md to document the current 7-platform plugin architecture, web dashboard, price monitoring, anti-detection, and encrypted sessions — replacing pre-refactor two-platform content, dead badges, a placeholder clone URL, and a credential instruction that contradicted SECURITY.md.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-07-02T21:31Z (approx, first commit 17:31:40-04:00)
- **Completed:** 2026-07-02T21:33Z (approx, second commit 17:32:43-04:00)
- **Tasks:** 2
- **Files modified:** 1 (README.md)

## Accomplishments
- Badge block replaced: three dead `app_*Build.yml` badges (master+dev, 6 total) removed; new badges point at `ci.yml`, `codeql-analysis.yml`, `gitleaks.yml` (all confirmed present in `.github/workflows/`) plus a static shields.io "python 3.11+" badge — no fabricated license badge
- Prerequisites/Install/Run corrected: Python 3.8+ → 3.11+, `pip install -r requirements.txt` → `pip install -e .[web]`, `python main.py` → `shoppybot` (documented as primary, `python main.py` noted as still-working alternative), clone URL `yourusername` → real `thezoid/ShopPyBot`
- Overview and Features rewritten to name all 7 platforms (Amazon, BestBuy, Walmart, Target, GameStop, NewEgg, Square Enix) and document the plugin framework, web dashboard/observability (SSE, health surface, log filtering), price monitoring, anti-detection (fingerprint/proxy rotation + 2captcha), and encrypted session persistence (Fernet + scrypt)
- Configuration section credential instruction ("edit config.yml to include your Amazon and BestBuy account details") replaced with the correct env-var/`.env` model, cross-linked to `SECURITY.md#credentials-and-secrets`
- Fixed the malformed Credits link (`[text]https://...)` missing its opening parenthesis)

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix header, badges, prerequisites, install, run, and clone URL** - `8f74300` (docs)
2. **Task 2: Rewrite Overview/Features for the 7-platform ecosystem and correct the credential model** - `f69f340` (docs)

**Plan metadata:** (this commit, following SUMMARY write)

## Files Created/Modified
- `README.md` - Badges, prerequisites, install/run instructions, clone URL, Overview, Features, Configuration credential guidance, Credits link fix

## Decisions Made
- Collapsed the old master/dev two-block badge layout to one master-branch badge row plus the static Python-version badge — not required by the plan, reduces redundant/stale surface (dev-branch CI status isn't reader-critical for a README)
- Left the Best Buy/Amazon-specific account-prerequisite subsections unchanged (out of task scope; not flagged as incorrect, just incomplete relative to the 7-platform list) — noted below as an adjacent issue, not actioned
- Restructured Configuration into 3 explicit steps (config copy → non-secret item edits → `.env` credential setup) rather than a single patched sentence, to make the non-secret/secret split unambiguous to a new reader

## Deviations from Plan

None - plan executed exactly as written, including the plan-checker-flagged addition (static Python-version badge) called out in the orchestrator's additional_instruction.

## Issues Encountered
None.

## Adjacent Issues (flagged, not actioned — per plan's `<verification>` operator-action-items list)

1. **No LICENSE file exists** (`gh api repos/thezoid/ShopPyBot/license` → 404, re-confirmed this session by absence of any `LICENSE*` at repo root). The README intentionally carries no license badge to avoid a fabricated legal claim. **Operator debt:** add a LICENSE (e.g., MIT) before/at first public release if the project is intended to be open-source-licensed.
2. **Root-level `amazon_bot.py` / `bestbuy_bot.py` and `_deprecated/`** appear superseded by `plugins/shopbot_plugin_amazon.py` / `plugins/shopbot_plugin_bestbuy.py`. Out of RH-06 scope (README accuracy, not dead-code removal) — flag only, not deleted.
3. **CLAUDE.md's Architecture section** still describes the pre-refactor single-process `while True` / `amazon_bot.py`/`bestbuy_bot.py` design, not the current plugin/orchestrator/web-dashboard architecture. Out of scope for this plan — flagged only, `CLAUDE.md` was not edited.

None of these three block RH-06's success criteria; all were pre-identified in 32-RESEARCH.md's Open Questions and this plan's `<verification>` section as explicitly out-of-scope for this plan.

## User Setup Required

None - no external service configuration required. This plan only edited README.md prose/markup.

## Next Phase Readiness
- RH-06 is complete. README.md now accurately reflects the current 7-platform, plugin-based, web-dashboard-capable project for a new contributor or operator.
- Ready for 32-03 (RH-07: SECURITY.md / CODE_OF_CONDUCT.md real security-contact rewrite), the last plan in Phase 32.
- Full test suite verified green at 889 passed, 2 skipped (no regression); `tests/test_docs.py` (4 tests) passes — README changes did not affect any doc-assertion test coverage (those tests target `docs/PLUGIN_REGISTRY.md`, `CONTRIBUTING.md`, `.github/PULL_REQUEST_TEMPLATE.md`, `plugins/PLUGIN_DEV.md`, not `README.md`).

---
*Phase: 32-release-automation-community-readiness*
*Completed: 2026-07-02*

## Self-Check: PASSED

- FOUND: README.md
- FOUND: .planning/phases/32-release-automation-community-readiness/32-02-SUMMARY.md
- FOUND: 8f74300 (Task 1 commit)
- FOUND: f69f340 (Task 2 commit)
