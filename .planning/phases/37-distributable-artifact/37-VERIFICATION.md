---
phase: 37-distributable-artifact
status: passed
verified: 2026-08-03
requirements_verified: [PKG-01, PKG-02, PKG-03, PKG-04, PKG-05, PKG-06]
final_master_sha: bd70601f3fc79f5a26cf0e98d96b615f9c3320bd
---

# Phase 37: Verification

## Verdict: PASSED

All six PKG requirements verified against a real built wheel installed into a clean virtualenv,
not against `pyproject.toml` text. Landed on `master` via PR #24 with all 8 checks green.

## Goal Achievement

**Phase goal:** "An installed wheel is a working ShopPyBot, so release-please publishing one
becomes worth doing."

Achieved. The measured before and after:

| | Before | After |
|---|---|---|
| `shoppybot --help` from clean install | `ModuleNotFoundError: pydantic_settings` | exit 0 |
| Modules importable clean (of 8) | 3 | 8 |
| Data files in wheel | 0 | 9 |
| Declared runtime dependencies | 1 | 9 |
| Wheel entries | 61 | 71 |

## Requirement Results

| Req | Assertion | Result |
|-----|-----------|--------|
| PKG-01 | Wheel ships `web/static`, `web/templates`, sounds | **PASS**. 5 + 1 + 4 entries. `sounds/` moved to the `core/sounds/` package because it was structurally unshippable: `utils` is top-level, so `os.path.dirname(__file__)` resolved to `site-packages/sounds`, which cannot be package data of anything |
| PKG-02 | `pyproject.toml` declares every real runtime dependency | **PASS**. 9 core dependencies, up from 1 |
| PKG-03 | `websockets`, `starlette`, `httpx`, `requests` each declared in the right place | **PASS**, and broader than the requirement text. `starlette` and `websockets` on floors, `httpx` as a test dependency, `requests` as runtime. Also caught: `pydantic-settings` (unnamed by PKG-03, and the actual cause of the dead entry point), plus `colorama`, `pyyaml`, `nodriver`, `keyring`, `cryptography` |
| PKG-04 | Dead `selenium` and `webdriver-manager` pins removed | **PASS**. Exactly 2 deletions, 0 insertions |
| PKG-05 | CI job installs the wheel clean and asserts it works | **PASS**. `scripts/verify_wheel.py` (299 lines, stdlib only) plus a `wheel` CI job on `ubuntu-latest` and `windows-latest`, installing without `requirements.txt`. Both legs green on PR #24 |
| PKG-06 | `bundled_plugins_dir()` resolves correctly from an installed wheel | **PASS**. Returns `site-packages/plugins` with exactly 7 `shopbot_plugin_*.py` files |

## PKG-06: the Phase 43 gate, closed

The roadmap declared PKG-06 a hard gate on Phase 43, with the fallback that if the bundled root
did not survive a wheel install, the `importlib.resources` fix would belong to this workstream
rather than to H.

**It survives. No `importlib.resources` rewrite is needed. Phase 43 (EXT-03) is unblocked.**

Two corrections to how PKG-06 was written, both now resolved:

1. `bundled_plugins_dir()` did not exist when the requirement was authored. It named a function
   that was nowhere in the codebase; the real mechanism was a bare path expression. The accessor
   now exists for real, at `core/paths.py`.
2. The expression appeared at **three** call sites, not the one the plan located
   (`core/orchestrator.py:814` plus `core/service.py:133` and `:159`). All three collapsed into
   the accessor.

The accessor is computed from `__file__`, deliberately **not** via `core/paths.py::_repo_root()`,
which honours a module-global `_REPO_ROOT_OVERRIDE` that the test suite monkeypatches. Routing
through it would have silently converted a "pure refactor" into a behavior change under exactly
the conditions the tests create, and would have made the root of a directory whose every `.py`
file gets `exec_module`'d settable from a module global. A test asserts the override cannot move
the result.

**Phase 43 must preserve this distinction:** the user plugin root under `data_dir()` legitimately
follows `SHOPBOT_DATA_DIR` and the test override. The bundled root must not.

## The Scouting Correction Worth Recording

The pre-planning scout (`37-SCOUT.md`) probed on Windows only, and was therefore incomplete in a
way that would have shipped a broken wheel.

`logger.py:6-7` imports `colorama` and `yaml` unconditionally, and `logger` is imported by nearly
everything. Both reach a Windows install only by accident: `click` declares `colorama` behind a
`win32` marker, and `uvicorn[standard]` pulls PyYAML. Both arrive only under the `web` extra, so
a bare `pip install shoppybot` would have failed on **every** OS.

Caught by the planner reading `logger.py` rather than trusting the scout's probe results. The
permanent fix is not the two added declarations, it is the `wheel` CI job running on
`ubuntu-latest` as well, which turns a lucky catch into a standing gate.

## The Gate Was Proven To Fail

A gate never observed failing is not known to be a gate. The negative control was run for real,
twice, because assertion 3 makes two independent claims:

- Doctored wheel with `web/static/*` stripped: exit 1, `FAIL 3: wheel ships nothing under
  ['web/static/']`
- Doctored wheel with `.wav` files stripped but `core/sounds/__init__.py` kept: the zip half
  passes at count 1, then `FAIL 3: notification.wav does not resolve at runtime`

That second case is precisely PKG-05's "ships but does not resolve" gap, which a zip-entry-only
check would have reported green. Assertions 1 and 2 printed PASS in both runs, confirming the
failure was isolated to the intended assertion.

## Evidence

- PR #24 merged to `master` at `bd70601f3fc79f5a26cf0e98d96b615f9c3320bd`, 2026-08-03T22:54:03Z.
- All 8 PR checks green: `CodeQL`, `gitleaks`, `Analyze (python)`, `Analyze (actions)`,
  `test (ubuntu-latest)`, `test (windows-latest)`, **`wheel (ubuntu-latest)`**,
  **`wheel (windows-latest)`**. Both wheel legs were running for the first time.
- Local suite 969 passed / 2 skipped, up from the 961 / 2 baseline by exactly the new tests.
- `version = "2.0.0"` untouched throughout. release-please owns versioning.

## Deviations

1. **Wave 3's plan named one call site; there were three.** Implementing it literally would have
   made the plan's own seam-guard test fail. Corrected in execution and recorded.
2. **The `core/sounds/` prefix count is 4, not the 3 the plan expected.**
   `core/sounds/__init__.py` is the package marker that makes
   `importlib.resources.files("core.sounds")` resolve at all. The script asserts non-empty and
   reports actual counts rather than pinning a number that would break on a legitimate change.
3. **The plan's suggested negative controls would not have named assertion 3.** A pre-Phase-37
   wheel dies at assertion 1; renaming installed `core/sounds` dies at assertion 2. Doctored
   wheels were used so everything cheaper than assertion 3 still passed.

## Outstanding

| Item | Owner | Note |
|------|-------|------|
| PR #21 (pip group) | next | Safe half is 8 dependency upgrades. Breaking half is FastAPI 0.115 to 0.141, which unregisters `/api/events` and kills the dashboard SSE channel. Split it |
| PR #23 (release 2.1.0) | Phase 38 | Blocked: GitHub suppresses `pull_request` checks on PRs opened by `GITHUB_TOKEN`, so the two required test contexts never report. Needs a GitHub App, deliberately NOT a PAT (public repo, `enforce_admins: false`, so an owner-identity token would bypass branch protection entirely) |
| `site-packages/plugins` namespace | Phase 43 | The bundled root lands as a top-level entry. Works, but Phase 43's multi-root design should own the location rather than inherit it |
| Roadmap criterion 5 tail | Phase 38 | "no Dependabot alert references either" is a GitHub-side outcome needing the alert queue to drain. Phase 38 owns it |
