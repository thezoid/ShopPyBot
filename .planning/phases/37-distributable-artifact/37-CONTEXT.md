# Phase 37: Distributable Artifact - Context

**Gathered:** 2026-08-03
**Status:** Ready for planning
**Mode:** Autonomous. The operator delegated the run with "do everything you can without me", so
the five open decisions from `37-SCOUT.md` were made by Claude and are recorded below with
reasoning. Each is reversible and flagged as a Claude call rather than an operator call.

<domain>
## Phase Boundary

Make an installed wheel a working ShopPyBot, so that release-please publishing one is worth
doing. In scope: shipping the data files the app needs, declaring the dependencies it actually
imports, removing dead pins, adding a CI job that proves a clean install works, and recording the
PKG-06 answer that Phase 43 depends on.

Out of scope: the release process itself (release-please already works and has opened PR #23),
plugin discovery redesign (Phase 43), dependency version upgrades beyond what is needed to make
the wheel functional, and anything about PR #21's FastAPI breakage.
</domain>

<decisions>
## Implementation Decisions

### Baseline (established empirically, not assumed)

`37-SCOUT.md` records a built-and-installed wheel probed in a clean venv. Its findings are inputs
to this phase, not things to re-derive. Headline: the wheel is not degraded, it is dead.
`shoppybot --help` fails at import on `pydantic_settings` before any command dispatch.

### PKG-06 and the Phase 43 gate: ANSWERED, favorably

- The bundled plugin root **does** survive a wheel install. `Path(core.__file__).parent.parent /
  "plugins"` resolves to `site-packages/plugins` and contains all 7 `shopbot_plugin_*.py` files.
  No `importlib.resources` rewrite is needed. **Phase 43 (EXT-03) is unblocked.**
- PKG-06 names a function `bundled_plugins_dir()` that **does not exist** in the codebase. The
  real mechanism is a bare expression at `core/orchestrator.py:814` consumed by
  `core/registry.py::_discover_plugins`.
- **Decision (Claude):** introduce `bundled_plugins_dir()` as a real named accessor in this
  phase, and have `core/orchestrator.py` call it instead of inlining the path expression.
  Rationale: workstream H (Phases 43 through 48) needs a stable seam for multi-root discovery,
  and PKG-06 is written against this name so satisfying it literally is cheaper than rewording
  the requirement. It is a pure refactor with no behavior change, provable by asserting the new
  accessor returns the same path the inline expression did.

### PKG-01, data files

- **Decision (Claude): move `sounds/` inside the `core` package as `core/sounds/`,** and resolve
  it via `importlib.resources`. `utils.SOUNDS_DIR` stays a module-level constant so existing
  callers do not change, but it is computed from the package rather than from
  `os.path.dirname(__file__)`.
  Rationale: `utils` is a top-level module, so today `SOUNDS_DIR` resolves to
  `site-packages/sounds`, which cannot be package data of anything because `sounds` is not a
  package. The two alternatives are worse: declaring a top-level `sounds` package pollutes
  `site-packages` with a junk package purely to carry three files, and shipping to a platformdirs
  location adds first-run copy logic this phase does not need. This is the option that leaves the
  installed tree clean.
- `web/static/*` and `web/templates/*` are already inside the `web` package, so they only need
  `[tool.setuptools.package-data]` plus `include-package-data = true`. No relocation.
- Verify by inspecting the built wheel's entry list, not by trusting the config.

### PKG-02 and PKG-03, dependency declaration

- Declare every module actually imported at runtime. Confirmed missing from the clean install and
  required: `pydantic-settings`, `requests`, `nodriver`, `keyring`, `cryptography`.
- **Decision (Claude): `pygame` is declared as an optional extra, not a core dependency.**
  Rationale: `utils` already degrades gracefully and logs "pygame not installed, sound
  notifications disabled". That is deliberate existing behavior and forcing pygame on every
  install to support an optional audio feature is the wrong trade, especially for the headless
  server case that Phase 24 already handled.
- **Decision (Claude): `httpx` is declared as a test dependency, not a runtime one.** Rationale:
  nothing on an exercised runtime path imports it. It is a hard top-level import for starlette's
  `TestClient`, which is test-only. Declaring it as runtime would ship an unused dependency to
  every user.
- **Decision (Claude): `websockets` and `starlette` get explicit declarations even though they
  currently arrive transitively** via `uvicorn[standard]` and `fastapi`. Rationale: PKG-03 asks
  for them and relying on a transitive is exactly the kind of thing that breaks silently on an
  unrelated upgrade. Declare with floors rather than hard pins so they do not fight their
  parents' resolution.
- **PKG-03 as written omits `pydantic-settings`, which is the single highest-impact missing
  dependency** since it is what kills the console-script entry point. Treat the requirement's
  named list as incomplete rather than authoritative.

### PKG-04, dead pins

- Remove `selenium` and `webdriver-manager` from `requirements.txt`. Nothing imports them; the
  codebase uses `nodriver`.
- Sequence this before any action on PR #21, which proposes upgrading both. Removing them first
  shrinks that PR's surface.

### PKG-05, the CI job

- The wheel job must install **without** `requirements.txt` present, or it proves nothing. The
  existing test job deliberately installs from `requirements.txt` first (there is a comment on
  master explaining why). These are separate jobs with separate install steps, not a shared one.
- **Decision (Claude): assertion order is cheapest-failing-first**, so a regression names itself:
  1. `shoppybot --help` exits 0. Catches every undeclared-dependency break at once without
     starting a server. This is the assertion that would have caught today's actual bug.
  2. Import each of `core.service`, `core.orchestrator`, `core.registry`, `core.config_schema`,
     `core.captcha`, `web`, `utils`, `models`. Pinpoints which dependency regressed.
  3. Wheel contains at least one entry under `web/static/`, `web/templates/`, and `core/sounds/`.
  4. `bundled_plugins_dir()` returns a directory with 7 `shopbot_plugin_*.py` files. Protects the
     PKG-06 result from silently regressing and breaking Phase 43 later.
  5. `shoppybot web` starts. Last, because by then it is unlikely to be the first thing broken.

### Versioning

- **Decision (Claude): leave `version = "2.0.0"` in `pyproject.toml` alone.** release-please owns
  versioning, it now works, and it has already opened PR #23 proposing 2.1.0. Hand-editing the
  version here would conflict with that PR and re-break the thing Phase 36 just fixed.

### Claude's Discretion

- Exact `package-data` glob syntax and whether `MANIFEST.in` is added alongside it.
- Whether dependency declarations use `==` pins matching `requirements.txt` or `>=` floors.
  Prefer matching the existing `requirements.txt` style for anything already pinned there.
- Plan decomposition and task ordering.
</decisions>

<code_context>
## Existing Code Insights

All verified against a real built wheel and a clean-venv install. Full detail in `37-SCOUT.md`.

### Current packaging config
- `dependencies = ["platformdirs==4.10.0"]` is the entire core declaration.
- `[project.optional-dependencies] web` has fastapi, uvicorn, jinja2, python-multipart.
- `[tool.setuptools.packages.find]` includes `core*`, `plugins*`, `notifications*`, `web*`.
- `[tool.setuptools] py-modules` lists `models`, `logger`, `config`, `utils`, `main`.
- No `package-data`, no `include-package-data`, no `MANIFEST.in`. Only `.py` files ship.

### Observed wheel contents (61 entries)
`web/static` 0, `web/templates` 0, `sounds` 0, `plugins/` 9, `notifications/` 7.

### Observed clean-install import failures
`core.service`, `core.config_schema` break on `pydantic_settings`. `core.orchestrator`,
`core.captcha` break on `requests`. `core.registry` breaks on `nodriver`. `web`, `utils`,
`models` import fine.

### Integration points
- `core/orchestrator.py:814` is where the plugin path is computed today.
- `core/registry.py::_discover_plugins` consumes it.
- `utils.py:13` `SOUNDS_DIR = os.path.join(os.path.dirname(__file__), 'sounds')`.
- `.github/workflows/ci.yml` on master is where the new wheel job lands.
</code_context>

<specifics>
## Specific Ideas

- The CI job's first assertion should be `shoppybot --help`, because that is the exact command
  that fails today and it is cheaper than launching a server.
- `bundled_plugins_dir()` must be asserted to return the same path the current inline expression
  returns, so the refactor is provably behavior-preserving.
</specifics>

<deferred>
## Deferred Ideas

- PR #21's FastAPI 0.141 SSE breakage. Diagnosed and documented on the PR; not this phase's work.
- PR #23 (release-please's 2.1.0 release PR) is BLOCKED because GitHub suppresses
  `pull_request`-triggered checks on PRs opened by `GITHUB_TOKEN`, so the two required test
  contexts never report. Needs a PAT or GitHub App token. Phase 38 scope, already documented in
  the workflow's own header comment.
- Namespace concern: the bundled plugin root lands as a top-level `site-packages/plugins`, which
  any other distribution shipping a top-level `plugins` package would collide with. Works today,
  does not block Phase 43, but Phase 43's multi-root design should own the location rather than
  inherit it.
</deferred>
