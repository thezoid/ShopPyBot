---
phase: 37-distributable-artifact
plan: 02
subsystem: infra
tags: [packaging, dependencies, pyproject, extras, clean-install, wheel, supply-chain]

# Dependency graph
requires:
  - phase: 37-distributable-artifact
    plan: 01
    provides: "core/sounds/ as a real package and package-data declarations, so the clean-venv SOUNDS_DIR check has something to find"
provides:
  - "a truthful [project] dependencies list covering every unconditional third-party import in the production tree"
  - "web extra with explicit starlette and websockets floors instead of inherited transitives"
  - "sound extra (pygame) and test extra (pytest, pytest-asyncio, httpx), keeping both off every default install"
  - "requirements.txt free of the dead selenium and webdriver-manager pins"
  - "an empirically proven clean-venv install: shoppybot --help exits 0 and all 8 probed modules import"
affects: [37-03, 37-04 CI wheel job, 38 dependabot queue, PR #21 surface]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "dependency claims are proven by installing a built wheel into a bare venv, never by reading pyproject.toml back"
    - "optional subsystems get extras plus a live absence assertion, not just a mocked degradation test"
    - "packages that arrive transitively but are imported directly get explicit floors matching the parent's declared minimum"

key-files:
  created: []
  modified:
    - pyproject.toml
    - requirements.txt

key-decisions:
  - "Nine runtime dependencies, not the five the scout named: colorama and pyyaml are unconditional logger.py imports that only reach a Windows install by accident, and only under the web extra"
  - "starlette and websockets get floors (>=0.40, >=10.4) matching their parents' declared minimums, not == pins, so they cannot fight fastapi's and uvicorn's resolution"
  - "pygame stays optional in a sound extra; the graceful-degradation path Phase 24 depends on was proven live, not just under mocks"
  - "httpx is test-only; declaring it runtime would ship an unused dependency to every user"
  - "urllib3 deliberately NOT declared: it is a transitive of requests that nothing imports directly, and declaring unimported transitives is the mirror image of the defect being fixed"

requirements-completed: [PKG-02, PKG-03, PKG-04]

# Metrics
duration: 7min
completed: 2026-08-03
---

# Phase 37 Plan 02: Truthful Dependency Declaration Summary

**The built wheel went from dead to working: a clean-venv install with no `requirements.txt` now runs `shoppybot --help` at exit 0 and imports all 8 probed modules, where the scout recorded a `ModuleNotFoundError: No module named 'pydantic_settings'` before command dispatch and only 3 of 8 modules importable.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-08-03T22:00Z
- **Completed:** 2026-08-03T22:07Z
- **Tasks:** 2 of 2
- **Files modified:** 2

## Accomplishments

- **Made the console script run at all.** `[project] dependencies` went from one entry to nine. The single highest-impact omission was `pydantic-settings`, which `core/config_schema.py:12` imports and which killed `core.service` (the console-script entry point) before any argument parsing.
- **Caught the scout's Windows blind spot.** The empirical baseline was measured on Windows only, where `colorama` arrives as a conditional dependency of `click` and PyYAML arrives through `uvicorn[standard]`. Both reach the install only under the `web` extra, and `logger.py:6-7` imports both unconditionally while `logger` is imported by nearly everything. A bare `pip install shoppybot` on any OS would have failed on `colorama` regardless of what the Windows probe showed. Nine declared, not five.
- **Proved the optional paths are genuinely optional.** `pygame` and `httpx` are both confirmed absent from a real `[web]` install, and `utils` imports there with `_AUDIO_AVAILABLE is False`. That is the live counterpart to the mocked coverage in `tests/test_utils_audio.py`, which passes unmodified.
- **Closed 37-01's deliberately open loop.** `utils.SOUNDS_DIR` was verified from inside the clean install, which 37-01 could not do because `import utils` in a bare venv still failed at that point.
- **Removed the two dead pins**, which also shrinks open PR #21's surface by two lines before Phase 38 touches the Dependabot queue.

## Clean-Install Import Matrix

Same eight rows the scout used, so before and after are directly comparable. "Before" is the observed
result in `37-SCOUT.md`; "After" is observed in `cleanenv2` on this run. Both are a bare Python 3.13
venv holding only pip, then `pip install "<abs path>/shoppybot-2.0.0-py3-none-any.whl[web]"` and
nothing else. No `requirements.txt`, no editable install.

| Module | Before (37-SCOUT.md) | Missing then | After | Verified |
|--------|----------------------|--------------|-------|----------|
| `core.service` | **BREAK** | `pydantic_settings` | **OK** | exit 0 |
| `core.config_schema` | **BREAK** | `pydantic_settings` | **OK** | exit 0 |
| `core.orchestrator` | **BREAK** | `requests` | **OK** | exit 0 |
| `core.captcha` | **BREAK** | `requests` | **OK** | exit 0 |
| `core.registry` | **BREAK** | `nodriver` | **OK** | exit 0 |
| `web` | OK | | **OK** | exit 0 |
| `utils` | OK (degraded) | | **OK** (degraded) | exit 0 |
| `models` | OK | | **OK** | exit 0 |
| **Totals** | **3 of 8** | | **8 of 8** | |

Console script, the phase's core claim:

| Command | Before (37-SCOUT.md) | After |
|---------|----------------------|-------|
| `shoppybot --help` | `ModuleNotFoundError: No module named 'pydantic_settings'` at `core/service.py:19` | **exit 0**, prints full usage with all 7 subcommands |

Deliberate exclusions, asserted live rather than assumed:

| Assertion | Result |
|-----------|--------|
| `import pygame` | exit 1, `ModuleNotFoundError: No module named 'pygame'` |
| `import httpx` | exit 1, `ModuleNotFoundError: No module named 'httpx'` |
| `import utils` with pygame absent | exit 0, logs `pygame not installed -- sound notifications disabled` |
| `utils._PYGAME_AVAILABLE` | `False` |
| `utils._AUDIO_AVAILABLE` | `False` |
| `pip list` contains `pygame` or `httpx` | 0 matches |
| `pip list` contains `selenium` or `webdriver-manager` | 0 matches |

Data files, closing 37-01's open loop from inside the install:

```
utils.SOUNDS_DIR = ...\scratchpad\cleanenv2\Lib\site-packages\core\sounds
listing           = ['__init__.py', '__pycache__', 'available.wav', 'buy.wav', 'notification.wav']
```

Asserted programmatically, not by eye: the path contains a `site-packages` segment followed by
`core` then `sounds`, and the `.wav` listing equals exactly the three expected names.

## Declared Dependency Set

Read back from the **built wheel's `METADATA`**, not from `pyproject.toml`:

```
Requires-Dist: colorama==0.4.6
Requires-Dist: cryptography==49.0.0
Requires-Dist: keyring==25.7.0
Requires-Dist: nodriver==0.50.3
Requires-Dist: platformdirs==4.10.0
Requires-Dist: pydantic==2.13.3
Requires-Dist: pydantic-settings[yaml]==2.14.2
Requires-Dist: pyyaml==6.0.2
Requires-Dist: requests==2.33.1
Provides-Extra: web
Requires-Dist: fastapi==0.115.8; extra == "web"
Requires-Dist: uvicorn[standard]==0.30.6; extra == "web"
Requires-Dist: jinja2==3.1.6; extra == "web"
Requires-Dist: python-multipart==0.0.32; extra == "web"
Requires-Dist: starlette>=0.40; extra == "web"
Requires-Dist: websockets>=10.4; extra == "web"
Provides-Extra: sound
Requires-Dist: pygame==2.6.1; extra == "sound"
Provides-Extra: test
Requires-Dist: pytest==9.0.3; extra == "test"
Requires-Dist: pytest-asyncio==1.3.0; extra == "test"
Requires-Dist: httpx==0.28.1; extra == "test"
```

Wheel entry count is **71**, unchanged from 37-01, confirming this plan disturbed none of the
`package-data` work.

Both new extras were dry-run resolved without contaminating the probe environment:

| Extra | `pip install --dry-run` result |
|-------|-------------------------------|
| `[sound]` | `Would install pygame-2.6.1` |
| `[test]` | `Would install Pygments-2.20.0 httpcore-1.0.9 httpx-0.28.1 iniconfig-2.3.0 packaging-26.2 pluggy-1.6.0 pytest-9.0.3 pytest-asyncio-1.3.0` |

`import pygame` was re-checked in `cleanenv2` afterwards and still exits 1, so the dry runs left the
probe environment intact and the 8-of-8 matrix above remains a clean-install result.

## Supply-Chain Pre-Flight

Threat register entries T-37-05 and T-37-SC require a mechanical legitimacy proof before any name
enters `[project] dependencies`. **This phase introduced zero new distributions.** Every one of the
eleven names (nine core plus the two `web` floors) was already resolved and installed in the repo
venv before it was declared, and every observed version matched the planned pin exactly:

| Name | `pip show` version | Planned declaration | Match |
|------|--------------------|---------------------|-------|
| colorama | 0.4.6 | `==0.4.6` | yes |
| cryptography | 49.0.0 | `==49.0.0` | yes |
| keyring | 25.7.0 | `==25.7.0` | yes |
| nodriver | 0.50.3 | `==0.50.3` | yes |
| platformdirs | 4.10.0 | `==4.10.0` | yes |
| pydantic | 2.13.3 | `==2.13.3` | yes |
| pydantic-settings | 2.14.2 | `[yaml]==2.14.2` | yes |
| pyyaml | 6.0.2 | `==6.0.2` | yes |
| requests | 2.33.1 | `==2.33.1` | yes |
| starlette | 0.45.3 | `>=0.40` | satisfies |
| websockets | 16.0 | `>=10.4` | satisfies |

Eleven of eleven passed. No `[ASSUMED]` or `[SUS]` package existed in the change set, so no blocking
human legitimacy checkpoint was required, and no package-manager install of a new name was attempted
at any point.

## Task Commits

1. **Task 1: Declare the real dependency set and delete the dead pins** - `a1fa5ee` (build)
2. **Task 2: Prove it in a clean virtualenv with no requirements.txt** - no commit; see below

**Plan metadata:** see the closing `docs(37-02)` commit.

Task 2 is a pure verification task. Its `<files>` field names `pyproject.toml` and
`requirements.txt`, but both were already correct as committed in Task 1 and pip resolved the
declared set on the first attempt, so there was nothing to change and therefore nothing to commit.
Its output is the evidence recorded above. Encoding the clean-install assertions as executable
guards is `37-04`'s CI wheel job by CONTEXT.md's own assignment, so adding them here would have been
scope creep into a plan that is about to write the same assertions.

## Files Created/Modified

- `pyproject.toml` - `dependencies` expanded from 1 entry to 9; `web` extra extended from 4 entries
  to 6 with the two floors; new `sound` and `test` extra groups; three explanatory comments recording
  why colorama/pyyaml are core, why starlette/websockets are floors rather than pins, and why pygame
  and httpx are not. `version`, `[tool.setuptools.package-data]`, `include-package-data`,
  `[tool.setuptools.packages.find]`, `py-modules` and `[tool.pytest.ini_options]` all untouched.
- `requirements.txt` - exactly 2 deletions, `selenium==4.43.0` and `webdriver-manager==4.0.2`.
  `git diff` confirms `1 file changed, 0 insertions, 2 deletions`. `urllib3==2.7.0` left in place as
  a transitive of requests and explicitly out of this phase's scope.

## Decisions Made

- **Nine, not five.** The scout's `37-SCOUT.md` matrix showed `utils` importing fine on a Windows
  clean install, which made `colorama` and `pyyaml` look declared-enough. They are not: `logger.py`
  imports both unconditionally, and both only reach a Windows install by accident and only under the
  `web` extra. This is recorded as the plan's single most important correction to the baseline.
- **`urllib3` deliberately not declared.** It is a transitive of `requests` that nothing in the
  production tree imports directly. Declaring unimported transitives is the mirror image of the
  defect this phase exists to fix. `grep -n urllib3 pyproject.toml` returns nothing.
- **`==` pins for the nine, floors for the two.** CONTEXT.md's discretion note directs matching
  `requirements.txt`'s existing style for anything already pinned there, which the nine are. The two
  `web` additions are different: they exist because the code imports them directly, but their
  versions are chosen by fastapi and uvicorn. Floors declare the dependency without contesting the
  parent's resolution. T-37-07 records the hard-pin trade as accepted for an application rather than
  a library, and Task 2 proved resolution succeeds against a real index rather than assuming it.
- **`version = "2.0.0"` left byte-identical**, as in 37-01. release-please owns versioning and has
  PR #23 open proposing 2.1.0.

## Deviations from Plan

### Auto-fixed Issues

None. No bug, missing critical functionality, or blocker was encountered; pip resolved the declared
set on the first attempt with no conflict, so the plan's "report the exact conflict and stop"
escape hatch was never needed.

### Plan Criterion Discrepancy (recorded, not fixed)

**1. Task 1 acceptance criterion 2 expects 8 where the correct answer is 9**

- **Found during:** Task 1 verification
- **Issue:** The criterion is
  `grep -c "^colorama\|^cryptography\|^keyring\|^nodriver\|^platformdirs\|^pydantic\|^pygame\|^requests" requirements.txt`
  "returns 8, confirming no other line was disturbed". It returns **9**, because `^pydantic` matches
  two lines: `pydantic==2.13.3` and `pydantic-settings[yaml]==2.14.2`. Eight patterns, nine matching
  lines. This is an arithmetic slip in the plan, not a defect in the change.
- **Action:** Not "fixed" by editing anything. The criterion's actual intent, that no line other than
  the two dead pins was disturbed, was verified more directly and more strictly with
  `git diff -- requirements.txt`, which reports `1 file changed, 0 insertions(+), 2 deletions(-)`
  and names exactly `selenium==4.43.0` and `webdriver-manager==4.0.2`. A diff is a stronger proof
  than a match count in any case.
- **Files modified:** none
- **Commit:** n/a

**Total deviations:** 0 auto-fixed, 1 recorded plan-criterion discrepancy
**Impact on plan:** None. Every substantive criterion passed as written.

## Issues Encountered

**`gsd-sdk query state.record-metric` and `state.add-decision` reject positional arguments.** Both
handlers returned `{"error": "..."}` when called with the positional form the executor workflow
documents (`state.record-metric "$PHASE" "$PLAN" ...`). Both succeeded with named flags
(`--phase 37 --plan 02 --duration 7min --tasks 2 --files 2`, and `--summary "..."`). Worth knowing
for the remaining plans in this phase. `state.record-session` returned
`{"recorded": false, "reason": "No session fields found in STATE.md"}` in either form, so the
Session Continuity and Current Position blocks were updated by direct edit instead.

**`state.advance-plan` blanks `last_activity`.** It rewrote both the frontmatter `last_activity` and
the Current Position `Last activity:` line down to a bare date, dropping the descriptive tail that
every prior entry carries. Restored by direct edit.

## Verification Evidence

- Wheel built from the tree at `a1fa5ee`; `build/` and `shoppybot.egg-info/` removed from the repo
  root by name afterwards. `git clean` was not used at any point. `git status --porcelain` returns
  empty after the build, and no `build/`, `dist/` or `*.egg-info/` path exists in the repo root.
- `cleanenv2` created with `py -3.13 -m venv`; `pip list` immediately after creation showed exactly
  `pip==26.0.1` and nothing else. The wheel plus its `[web]` extra then resolved 41 distributions in
  one pip invocation with no resolution error and no second install command.
- `shoppybot --help` exit 0 with full usage output listing `run`, `setup`, `items`, `config`,
  `plugins`, `status`, `web`.
- Eight separate interpreter invocations, one per module, so a failure would have named exactly one
  module. 8 pass, 0 fail.
- Probes ran with `PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring` so the keyring import never
  touches a real secret store (T-37-08), and `SHOPBOT_DATA_DIR` pointed under the scratchpad so
  nothing wrote to the real user data directory. `core/paths.py:25` confirms that env var is honoured.
- `tests/test_utils_audio.py` passes **unmodified**: 8 passed. `git log -1` on that path shows its
  last touch is `8284735` from Phase 24; `git diff HEAD` on it is empty.
- Full suite: **965 passed, 2 skipped**, byte-identical to the 37-01 baseline. This plan adds no
  tests and regresses none.
- All build and venv artifacts live under the session scratchpad. Nothing was created inside the
  repo.

## User Setup Required

None. Purely local packaging work: no push, no PR, no GitHub state mutated, and no new distribution
added to the dependency graph.

## Next Phase Readiness

- **37-03 and 37-04 are unblocked.** 37-04's CI wheel job now has its first two assertions in
  concrete, proven form: `shoppybot --help` exits 0, then the eight-module import matrix. Both are
  cheaper than starting a server and both would have caught today's defect.
- **Two probe details worth reusing in CI:** set `PYTHON_KEYRING_BACKEND` to the null backend so the
  keyring import never probes D-Bus on Linux (the existing `ci.yml` test job already does this), and
  set `SHOPBOT_DATA_DIR` to a temp path so the probe never writes to a real user data directory.
- **The wheel job must install by absolute `.whl` path with no `requirements.txt` present.** The
  current `ci.yml` installs from `requirements.txt` first, deliberately, per a comment on master.
  That is correct for the test job and would silently invalidate the wheel job.
- **Phase 38 note:** PR #21 proposes upgrading `selenium` 4.43.0 to 4.46.0 and `webdriver-manager`
  4.0.2 to 4.1.2. Both lines are now moot; the packages are gone. That PR's remaining surface is
  smaller by two entries.
- **CI runs on `ubuntu-latest` as well as `windows-latest`,** and this plan's central correction is
  that the previous baseline was Windows-only. The nine-package declaration should be exercised on
  Linux by 37-04's job specifically because that is where the old `colorama`/`pyyaml` accident does
  not save it.
- No blockers.

## Known Stubs

None. No placeholder value, empty collection, or "coming soon" string was introduced; this plan
modified two declaration files and wrote no application code.

## Threat Flags

None. No network endpoint, auth path, file-access pattern, or schema at a trust boundary was
created or changed. The only trust-boundary surface this plan touches is the declared dependency
set itself, which is exactly what T-37-05 and T-37-SC cover, and the pre-flight table above is the
mitigation those entries require.

## Self-Check: PASSED

- `pyproject.toml` exists and its `tomllib`-parsed content asserts `len(dependencies) == 9`,
  `set(optional-dependencies) == {web, sound, test}` with sizes 6/1/3, and `version == "2.0.0"`.
- `requirements.txt` exists; `grep -c "selenium\|webdriver-manager"` returns 0.
- `.planning/phases/37-distributable-artifact/37-02-SUMMARY.md` exists (this file).
- Commit `a1fa5ee` resolves in `git log`.
- `git status --porcelain` clean before this SUMMARY was written.

---
*Phase: 37-distributable-artifact*
*Completed: 2026-08-03*
