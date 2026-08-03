---
phase: 37-distributable-artifact
plan: 04
subsystem: infra
tags: [packaging, ci, wheel, regression-gate, negative-control, pkg-05]

# Dependency graph
requires:
  - phase: 37-distributable-artifact
    plan: 01
    provides: "core/sounds/ as a package plus package-data, so assertion 3 has files to find and a SOUNDS_DIR to resolve"
  - phase: 37-distributable-artifact
    plan: 02
    provides: "a wheel whose clean-venv install actually runs, so assertions 1, 2 and 5 can pass at all"
  - phase: 37-distributable-artifact
    plan: 03
    provides: "core.paths.bundled_plugins_dir(), which makes assertion 4 a one-liner needing only platformdirs"
provides:
  - "scripts/verify_wheel.py: a stdlib-only runner for the five locked wheel assertions, identical in CI and locally"
  - "a CI wheel job on ubuntu-latest and windows-latest that installs the built wheel into a clean venv with no requirements.txt in sight"
  - "recorded negative-control evidence: the gate was observed exiting 1 and naming assertion 3, on both halves of it"
  - "a one-command local reproduction of the CI job, so a red wheel job is debuggable without a push"
affects: [38 SHA-pinning and permissions sweep, 43 plugin-root discovery, every future dependency bump]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "a gate that has never been seen to fail is not known to be a gate; prove it by breaking the artifact, not the assertion"
    - "assertions run cheapest-failing-first as an ordered data structure, so CI's first output line names the layer that broke"
    - "readiness is an observed HTTP response, never a log line the process printed before doing the risky work"

key-files:
  created:
    - scripts/verify_wheel.py
  modified:
    - .github/workflows/ci.yml

key-decisions:
  - "assertion 3 checks both halves separately (wheel zip entries AND a runtime SOUNDS_DIR resolve) because a dropped core.sounds package marker passes one and fails the other; both halves were then proven to fail independently"
  - "assertion 5 polls real HTTP because core/cli/web.py prints the dashboard URL with flush=True BEFORE create_app() runs, so the printed line proves nothing about the app being constructible"
  - "the wheel is resolved by globbing *.whl and failing on zero or multiple matches; a hardcoded versioned filename would break the job the first time release-please bumps the version"
  - "every clean-env subprocess runs with -I and a cwd outside the repo, so the checkout cannot shadow site-packages and turn a broken wheel into a green run"
  - "two negative controls instead of one, because assertion 3 makes two independent claims and only one of them was ever at risk of being written as decoration"

requirements-completed: [PKG-05]

# Metrics
duration: 19min
completed: 2026-08-03
---

# Phase 37 Plan 04: The Wheel Gate Summary

**Every fact this phase established is now a build gate, and the gate has been watched failing: two deliberately doctored wheels made `scripts/verify_wheel.py` exit 1 and name assertion 3, once for shipping nothing and once for shipping a file that does not resolve.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-08-03T22:26Z
- **Completed:** 2026-08-03T22:45Z
- **Tasks:** 2 of 2
- **Files created/modified:** 2

## Accomplishments

- **Turned three plans of hand-proof into one command.** 37-01, 37-02 and 37-03 each proved something once, by hand, in a scratch virtualenv. Those proofs are now a 299-line checked-in script that reproduces all of them in a fresh environment on demand.
- **Proved the gate is a gate.** The plan's most important acceptance criterion is the negative control, and it was run for real, twice. A wheel with `web/static/` stripped fails assertion 3's zip half; a wheel that still ships `core/sounds/__init__.py` but no `.wav` files passes the zip half and fails the runtime half. Verbatim output below.
- **Kept the two CI jobs genuinely separate.** The `test` job still installs `requirements.txt` first, deliberately, and is byte-identical to `HEAD` when both are parsed. The `wheel` job has its own install step that never sees it.
- **Put the job on Ubuntu as well as Windows.** 37-02's central correction was that the previous baseline was Windows-only and `colorama` and `pyyaml` reached the install by accident there. A Windows-only wheel job would keep missing exactly that class of defect.
- **Made a red CI run debuggable without a push.** The script's argparse interface is the same locally and in the job, so the third step's command runs unchanged on a laptop.

## The Five Assertions, Observed Passing

Verbatim, from a clean `py -3.13` venv holding only pip, then a single
`pip install "<abs path>/shoppybot-2.0.0-py3-none-any.whl[web]"`. No pinned dev requirements
file, no install from source:

```
PASS 1: `shoppybot --help` exits 0
PASS 2: all 8 modules import: core.service, core.orchestrator, core.registry, core.config_schema, core.captcha, web, utils, models
PASS 3: wheel entries [web/static/ 5, web/templates/ 1, core/sounds/ 4]; notification.wav found under SOUNDS_DIR=...\cienv\Lib\site-packages\core\sounds
PASS 4: bundled_plugins_dir() holds exactly 7 plugins at ...\cienv\Lib\site-packages\plugins
PASS 5: `shoppybot web` serves on port 59421 (HTTP 200)
all 5 assertions passed
```

Exit code 0. The absolute scratchpad prefix is elided above for width; the resolved paths are
`C:\Users\brand\AppData\Local\...\scratchpad\cienv\...` and the `site-packages` segment in both
lines 3 and 4 is asserted by the script, not merely printed.

Assertion 5 is an HTTP 200 read back from `http://127.0.0.1:59421/`, not the dashboard URL the
process printed. That distinction is the whole point: `core/cli/web.py:95` prints the URL with
`flush=True` at line 95 and only calls `create_app()` at line 101, so a `StaticFiles`
`RuntimeError` would land after the print and a script that trusted the printed line would
report a green run against a dead server.

## The Negative Control

**A gate that has never failed is not known to be a gate.** Assertion 3 makes two independent
claims, so both were broken separately, each in a throwaway copy of the real wheel with the
matching `RECORD` lines removed. Both throwaway venvs were discarded afterwards.

### NC-1, the zip half: files do not ship

Removed from a copy of the wheel: `web/static/components.css`, `web/static/dashboard.css`,
`web/static/tokens.css`, `web/static/vendor/uplot.iife.min.js`, `web/static/vendor/uplot.min.css`.
This is the exact defect 37-01 fixed, where the scout observed `web/static` at 0 entries.

```
PASS 1: `shoppybot --help` exits 0
PASS 2: all 8 modules import: core.service, core.orchestrator, core.registry, core.config_schema, core.captcha, web, utils, models
FAIL 3: data files ship and a sound resolves
       wheel ships nothing under ['web/static/']
counts: web/static/ 0, web/templates/ 1, core/sounds/ 4
EXIT: 1
```

### NC-2, the runtime half: files ship but do not resolve

Removed from a copy of the wheel: `core/sounds/available.wav`, `core/sounds/buy.wav`,
`core/sounds/notification.wav`. `core/sounds/__init__.py` was deliberately left in place, so the
`core/sounds/` prefix still has an entry and the zip half still passes.

```
PASS 1: `shoppybot --help` exits 0
PASS 2: all 8 modules import: core.service, core.orchestrator, core.registry, core.config_schema, core.captcha, web, utils, models
FAIL 3: data files ship and a sound resolves
       notification.wav does not resolve at runtime
stdout:
[INFO][core][2026August03@18:37:47] pygame not installed -- sound notifications disabled
SOUNDS_DIR=...\nc2env\Lib\site-packages\core\sounds
stderr:

EXIT: 1
```

(The captured stdout carries ANSI colour codes from `writeLog`; they are stripped above for
readability. Nothing else is changed.)

**What the two controls establish, beyond "it can fail":**

| Property | Evidence |
|----------|----------|
| The script exits non-zero on a real defect | `EXIT: 1` in both runs |
| It names the failing assertion by number | `FAIL 3` in both, never a bare traceback |
| The order is real, not decorative | assertions 1 and 2 still printed `PASS` first; the run stopped at 3 and never reached 4 or 5 |
| Both halves of assertion 3 are load-bearing | NC-1 trips the zip half, NC-2 trips the runtime half while the zip half passes |
| PKG-05's wording is satisfied literally | NC-2 is precisely the "ships but does not resolve" case, which a zip-entry-only check would have reported green |

Without NC-2, the runtime half of assertion 3 would be an untested line of code claiming to be a
safety property.

## The CI Job

Added as a second job named `wheel`, alongside `test`. `git diff --numstat` reports
`37  0  .github/workflows/ci.yml`: thirty-seven additions, zero deletions.

| Property | Value | How it was checked |
|----------|-------|--------------------|
| jobs defined | `['test', 'wheel']` | `yaml.safe_load` of the working tree |
| `test` job vs `HEAD` | identical | parsed both, compared the `test` sub-dict for equality |
| matrix | `['ubuntu-latest', 'windows-latest']` | parsed |
| `fail-fast` | `False` | parsed |
| steps mention `verify_wheel.py` | yes | `str(job['steps'])` |
| steps mention `requirements.txt` | no | asserted absent from `str(job['steps'])` |
| steps mention a source install (`-e`) | no | asserted absent from `str(job['steps'])` |
| `actions/checkout@v6` occurrences | 2 | `grep -c`, matching the existing tag style |
| `permissions:` block | 0 | `grep -c`; Phase 38 owns this |
| `runner.temp` occurrences | 3, all inside a step-level `env:` | `grep -n`, lines 44, 80, 81 |

The three steps after checkout and Python setup are: install `pip` and `build` into the job
environment, `python -m build --wheel --outdir dist`, then
`python scripts/verify_wheel.py --wheel-dir dist --venv "${{ env.WHEEL_VENV }}"`. `build` never
enters the clean venv, which the script creates itself.

A comment above the job states in full why it must never install from `requirements.txt` and why
Ubuntu is not optional. That comment is the guard against a well-meaning future edit (T-37-14),
and it sits alongside two mechanical guards: the parsed-steps assertion above, and the fact that
`scripts/verify_wheel.py` does not contain the string at all.

**The CI job has not run on a runner and is not green.** It exists only on
`chore/v4.0-milestone-close`, which is unpushed. Its first real execution happens when this
branch is pushed, which is outside this plan's authority. What has been established is narrower
and should not be overstated: the exact command the third step runs was executed on this machine,
on Windows, against a real clean-venv install, and exited 0 with five `PASS` lines. The
`ubuntu-latest` leg is entirely unexercised, and it is the leg most likely to surface something,
since 37-02's central finding was that the previous baseline was Windows-only.

## Task Commits

1. **Task 1: Write the wheel verification script and run it end to end locally** - `6ca6d1e` (feat)
2. **Task 2: Add the wheel job to CI, installing without requirements.txt** - `e013e55` (ci)

**Plan metadata:** see the closing `docs(37-04)` commit.

## Files Created/Modified

- `scripts/verify_wheel.py` (new, 299 lines) - argparse interface with `--wheel-dir` (default
  `dist`) and a required `--venv`. Resolves the wheel by glob and fails loudly on zero or multiple
  matches. Creates the environment with the stdlib `venv` module and installs the wheel by
  absolute path with the `web` extra, and nothing else. Five assertion functions each return a
  `Result(ok, message, detail)`, driven from an ordered `ASSERTIONS` tuple so the sequence is data
  rather than control flow. Standard library only: the fourteen import roots are `__future__`,
  `argparse`, `glob`, `os`, `pathlib`, `shutil`, `socket`, `subprocess`, `sys`, `time`, `typing`,
  `urllib`, `venv`, `zipfile`, every one of them in `sys.stdlib_module_names`.
- `.github/workflows/ci.yml` - `wheel` job appended. The `test` job is untouched, proven by
  parsing it out of both `HEAD` and the working tree and comparing.

## Decisions Made

- **Two negative controls, not one.** The plan asked for one. Assertion 3 makes two independent
  claims and only the second one is novel, so breaking only the zip half would have left the
  runtime check unproven. NC-2 is the case PKG-05 is actually worried about.
- **`-I` plus a cwd outside the repo for every probe.** Without both, a `python -c "import core"`
  launched from the repo root imports the checkout rather than `site-packages`, and a wheel
  missing every data file would sail through. `-I` keeps cwd off `sys.path` and the cwd is set to
  the created venv directory regardless. `PYTHONPATH`, `PYTHONHOME` and `VIRTUAL_ENV` are dropped
  from the child environment for the same reason.
- **`reset` of the venv directory refuses to delete a non-venv.** The script removes `--venv`
  before recreating it. A typo in that flag would otherwise be a destructive operation against an
  arbitrary directory, so it raises unless a `pyvenv.cfg` is present.
- **`WHEEL_VENV` is a step-level `env:` entry rather than inline `${{ runner.temp }}` in the
  `run:` line.** Both are valid, but this keeps every `runner.temp` reference inside a step-level
  `env:` block, which is the shape the plan asked for, and `${{ env.WHEEL_VENV }}` is expanded by
  Actions before either shell sees it, so it needs no `$VAR` versus `$env:VAR` handling across the
  bash and pwsh matrix legs.
- **Wheel resolved by glob, never by name.** release-please has PR #23 open proposing 2.1.0. A
  hardcoded `shoppybot-2.0.0-py3-none-any.whl` would have made the job fail on the first release
  after this one, which is the single most predictable way for this gate to become noise.
- **`version = "2.0.0"` left byte-identical**, as in 37-01, 37-02 and 37-03.

## Deviations from Plan

### Auto-fixed Issues

None. No bug, missing critical functionality, or blocker was encountered. The script passed all
five assertions on its first end-to-end run and the YAML parsed on the first attempt.

### Plan Criterion Discrepancies (recorded, not fixed)

**1. Assertion 3's expected `core/sounds/` count is 4, not the 3 the plan predicts**

- **Found during:** Task 1, first end-to-end run
- **Issue:** The acceptance criterion reads "per-prefix counts of 5 for `web/static/`, 1 for
  `web/templates/`, and 3 for `core/sounds/`". The observed counts are 5, 1 and **4**. The prefix
  count includes `core/sounds/__init__.py` alongside the three `.wav` files. The criterion counted
  only the sound files.
- **Why it is not a defect:** `__init__.py` is what makes `core.sounds` a package, which is the
  entire mechanism 37-01 chose so that `importlib.resources.files("core.sounds")` resolves from an
  installed layout. Its presence in the prefix is the fix working, not a stray file. Total wheel
  entries are 71, byte-identical to the counts recorded in 37-01 and 37-02, so nothing new is
  shipping. Full listing:
  `core/sounds/__init__.py`, `core/sounds/available.wav`, `core/sounds/buy.wav`,
  `core/sounds/notification.wav`.
- **Action:** None. The script asserts each prefix is non-empty and reports the actual counts, so
  it neither hardcodes 3 nor hardcodes 4. Hardcoding either would make an innocent added file a CI
  failure. The one count the script does pin exactly is assertion 4's seven plugins, where the
  plan explicitly argues for exactness.
- **Files modified:** none
- **Commit:** n/a

**2. The plan's suggested negative control would have failed at assertion 1, not 3**

- **Found during:** Task 1, designing the negative control
- **Issue:** The plan suggests "point the script at a wheel built before plan 37-01". A pre-37-01
  wheel also predates 37-02's dependency work, so it dies at assertion 1 with
  `ModuleNotFoundError: No module named 'pydantic_settings'` and never reaches assertion 3. The
  plan's other suggestion, renaming the installed `core/sounds` directory, fails at assertion 2
  instead, because `utils` resolves `SOUNDS_DIR` at import time and `import utils` is assertion 2's
  eighth probe.
- **Why it is not a defect:** both of those outcomes are the ordering working correctly. They are
  simply not the outcome the criterion asks to observe.
- **Action:** Doctored copies of the current wheel were used instead, removing one prefix at a
  time so that everything cheaper than assertion 3 still passes and assertion 3 is provably the
  thing that trips. Recorded above as NC-1 and NC-2.
- **Files modified:** none in the repo. The doctoring helper lives in the session scratchpad.
- **Commit:** n/a

**Total deviations:** 0 auto-fixed, 2 recorded plan-criterion discrepancies, 0 architectural,
0 blocked.
**Impact on plan:** None. Every substantive criterion passed, and the negative-control criterion
passed more thoroughly than it was written.

## Verification Evidence

- `.venv/Scripts/python.exe -m build --wheel --outdir <scratch>/dist` exits 0, producing
  `shoppybot-2.0.0-py3-none-any.whl` at 71 entries.
- `scripts/verify_wheel.py` run against that wheel with a fresh `--venv`: exit 0, five `PASS`
  lines numbered 1 to 5 in the locked order. Run twice, against two independently created clean
  venvs (`wheelenv` for Task 1, `cienv` for Task 2's "run the job's real command" criterion).
- Negative controls NC-1 and NC-2: exit 1, `FAIL 3` in both, quoted verbatim above.
- Mechanical script checks, all run with `ast` and string counts against the file on disk:
  299 lines (limit 300); longest function 23 lines (limit 30); no line over 99 characters;
  `requirements.txt` count 0; `editable` count 0; `shoppybot-2.0.0` count 0; every top-level
  import root present in `sys.stdlib_module_names`; contains `shopbot_plugin_` and `site-packages`
  as the plan's `must_haves` require.
- `yaml.safe_load` of `.github/workflows/ci.yml` succeeds; `sorted(d['jobs'])` is
  `['test', 'wheel']`; the `test` job parsed from `git show HEAD:.github/workflows/ci.yml` compares
  equal to the `test` job parsed from the working tree.
- `git diff --numstat` on `ci.yml`: `37 additions, 0 deletions`. A `grep -c '^-[^-]'` over the
  diff returns 0, confirming no line was removed or modified.
- Full suite: **969 passed, 2 skipped**, byte-identical to the 37-03 baseline. This plan adds no
  application code and no tests, and regresses nothing.
- `grep -n '^version' pyproject.toml` = `version = "2.0.0"`, untouched.
- Both per-task commits checked with `git diff --diff-filter=D --name-only HEAD~1 HEAD`: no file
  deletions in either.
- `build/` and `shoppybot.egg-info/` were removed from the repo root **by name** after the build.
  `git clean` was not used at any point in this plan. `git status --porcelain` verified clean after
  the build and after each commit, and no `build/`, `dist/` or `*.egg-info/` path exists in the
  repo root.
- Every venv, wheel, doctored wheel and helper script lives under the session scratchpad. Nothing
  was created inside the repo except the two files this plan owns.

## User Setup Required

**One action, and it is a push, not a setting.** The `wheel` job runs for the first time when
`chore/v4.0-milestone-close` is pushed and its PR opened. Until then the job is committed code
that no runner has executed. Nothing in GitHub settings needs changing for it: it uses only
`actions/checkout@v6` and `actions/setup-python@v6`, both first-party and both already in use by
the `test` job.

Expect the `ubuntu-latest` leg to be the informative one. If it fails, the reproduction is one
local command with no push required:

```
python -m build --wheel --outdir dist
python scripts/verify_wheel.py --wheel-dir dist --venv <a scratch path>
```

## Next Phase Readiness

- **Phase 37 is complete.** PKG-01 through PKG-06 are all closed and all six were proven against a
  real built wheel rather than against `pyproject.toml`.
- **Phase 38 inherits a consistent `ci.yml`.** The new job deliberately uses `@v6` tags and adds no
  `permissions:` block, so Phase 38's SHA-pinning and permissions sweep sees one uniform file with
  two jobs rather than a half-converted one.
- **Phase 38 should not "simplify" the two install steps into one.** They differ on purpose. The
  comment above the `wheel` job says so, and T-37-14 records this as the highest-value failure mode
  in the plan: it converts a real gate into a green rubber stamp while still reporting success.
- **Phase 43 gains a permanent guard.** Assertion 4 pins the bundled plugin root at exactly seven
  `shopbot_plugin_*.py` files. When Phase 43 adds a second root, that number becomes a deliberate
  edit to this script rather than a silent drift.
- **Every future dependency bump now meets a real gate.** Assertion 1 is the cheapest possible
  canary for an undeclared dependency, and it is the exact command that failed on master before
  this phase.
- No blockers.

## Known Stubs

None. No placeholder value, empty collection, or "coming soon" string was introduced. Every
assertion runs a real subprocess against a real installed artifact, and each one was observed both
passing and, for assertion 3, failing.

## Threat Flags

None. No new network endpoint, auth path, or schema at a trust boundary was created. The register
entries this plan owns were each mitigated as specified:

| Threat ID | Mitigation as shipped |
|-----------|----------------------|
| T-37-14 | three defences: an explanatory comment above the job, a parsed-steps assertion that `requirements.txt` and `-e` are absent, and the script never containing the string at all |
| T-37-15 | assertion 5 polls an actual HTTP GET; the printed dashboard URL is never read |
| T-37-16 | `PYTHON_KEYRING_BACKEND` forced to the null backend and `SHOPBOT_DATA_DIR` redirected into a throwaway directory inside `--venv`, so no probe reads or writes a real secret store or the user data directory |
| T-37-17 | the served child is terminated in a `finally` path, waited on with a timeout, and killed if the wait expires; the port comes from binding port 0 so concurrent matrix legs cannot collide |
| T-37-18 | two negative controls, run for real, quoted verbatim above |
| T-37-SC | no new distribution was introduced; the job installs `build` into the runner environment and the locally built wheel by absolute path into the clean venv, so there is no index-resolved project name and no name-confusion surface |

One surface worth naming rather than leaving implicit: the clean venv resolves this project's
declared dependencies from PyPI on every push, so the wheel job is a recurring supply-chain
touchpoint. That is inherent to proving a wheel installs, and every name it resolves was already
declared and legitimacy-checked in 37-02.

## Self-Check: PASSED

- `scripts/verify_wheel.py` exists.
- `.github/workflows/ci.yml` exists.
- `.planning/phases/37-distributable-artifact/37-04-SUMMARY.md` exists (this file).
- Commit `6ca6d1e` resolves in `git log`.
- Commit `e013e55` resolves in `git log`.
- `git status --porcelain` clean of build artifacts before this SUMMARY was written.

*Phase: 37-distributable-artifact*
*Completed: 2026-08-03*
