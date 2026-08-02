# Phase 37: Empirical Wheel Baseline (pre-planning scout)

**Produced:** 2026-08-02, immediately after Phase 36 closed.
**Method:** built an actual wheel from the current tree, installed it with the `[web]` extra into
a fresh Python 3.13 virtualenv with no `requirements.txt` available, and probed it. Nothing here
is inferred from reading `pyproject.toml`; every line is an observed result.

Artifacts (scratch, not committed): wheel `shoppybot-2.0.0-py3-none-any.whl`, clean venv, probe
scripts under the session scratchpad.

## Headline

**The built wheel is not degraded. It is completely non-functional.** The installed `shoppybot`
console script fails on every invocation including `shoppybot --help`, dying at import time
before any command dispatch:

```
File "...\site-packages\core\service.py", line 19, in <module>
    from core.config_schema import AppConfig
File "...\site-packages\core\config_schema.py", line 12, in <module>
ModuleNotFoundError: No module named 'pydantic_settings'
```

This is earlier and simpler than PKG-01 and PKG-05 assume. Those are written around
`shoppybot web` starting and then hitting a `StaticFiles` `RuntimeError`. Execution never gets
that far. Any CI assertion should therefore start with `shoppybot --help` exiting 0, which is a
cheaper and stricter canary than launching the web server.

## PKG-06: the Phase 43 gate, ANSWERED

**Result: the bundled plugin root DOES survive a wheel install. No `importlib.resources` rewrite
is needed. Phase 43 (EXT-03) is unblocked.**

```
core package dir     : ...\site-packages\core
resolved plugins_dir : ...\site-packages\plugins
exists               : True
bundled plugin files : 7
    shopbot_plugin_amazon.py      shopbot_plugin_newegg.py
    shopbot_plugin_bestbuy.py     shopbot_plugin_squareenix.py
    shopbot_plugin_gamestop.py    shopbot_plugin_target.py
    shopbot_plugin_walmart.py
```

Two corrections to how PKG-06 is written:

1. **`bundled_plugins_dir()` does not exist in the codebase.** PKG-06 names it as though it does.
   `grep -rn "def bundled_plugins_dir"` returns nothing. The real mechanism is a bare expression
   at `core/orchestrator.py:814`:
   `plugins_dir = Path(__file__).parent.parent / "plugins"`,
   consumed by `core/registry.py::_discover_plugins`. PKG-06 should either be reworded against
   the real code, or Phase 37 should introduce `bundled_plugins_dir()` as the named accessor the
   later EXT phases can depend on. The latter is probably better, since workstream H needs a
   stable seam for multi-root discovery, but it is a scope decision.

2. **The resolution works, but it works by landing `plugins/` as a top-level entry in
   `site-packages`.** That is namespace pollution: any other distribution shipping a top-level
   `plugins` package would collide. It resolves correctly today and does not block Phase 43, but
   Phase 43's multi-root design should treat the bundled root's location as something it owns
   rather than something it inherits.

## PKG-01: data files are entirely absent from the wheel

Wheel contains 61 entries. Data directories:

| Path | Entries in wheel |
|------|------------------|
| `web/static` | **0** |
| `web/templates` | **0** |
| `sounds` | **0** |
| `plugins/` | 9 (7 plugins plus `__init__.py` and `example_plugin.py`) |
| `notifications/` | 7 |

Root cause: `pyproject.toml` has no `[tool.setuptools.package-data]`, no
`include-package-data = true`, and there is no `MANIFEST.in`. Only `.py` files ship.

**Structural problem with `sounds/`, worth deciding before planning.** `utils.py` resolves sounds
as `SOUNDS_DIR = os.path.join(os.path.dirname(__file__), 'sounds')`. `utils` is a top-level
module (declared in `[tool.setuptools] py-modules`), so on an installed wheel that resolves to
`site-packages/sounds`, which does not exist and cannot be package data of any package because
`sounds` is not a package. Confirmed observed: `sounds dir exists=False`.

Fixing this needs a real decision, not just a config line. Options:
- Move `sounds/` inside a package (for example `core/sounds/` or a new `shoppybot/` package) and
  resolve via `importlib.resources`. Cleanest, but touches `utils.py`'s public path constant.
- Declare a top-level `sounds` package with an `__init__.py` and ship it as package data. Least
  invasive, keeps `SOUNDS_DIR` working, but adds a junk package to `site-packages`.
- Ship sounds as data files to a platformdirs location at first run. Most correct for a real
  distribution, most work.

The same question applies to `web/static` and `web/templates`, though those are already inside
the `web` package so they only need `package-data` plus `include-package-data`.

## PKG-02 and PKG-03: declared dependencies versus reality

`pyproject.toml` currently declares:

```
dependencies = ["platformdirs==4.10.0"]
[project.optional-dependencies]
web = ["fastapi==0.115.8", "uvicorn[standard]==0.30.6", "jinja2==3.1.6", "python-multipart==0.0.32"]
```

Clean install of `wheel[web]` produced these importable-module failures. Five of the eight core
modules are unimportable:

| Module | Clean-install import | Missing |
|--------|---------------------|---------|
| `core.service` | **BREAK** | `pydantic_settings` (this is the console-script entry point) |
| `core.config_schema` | **BREAK** | `pydantic_settings` |
| `core.orchestrator` | **BREAK** | `requests` |
| `core.captcha` | **BREAK** | `requests` |
| `core.registry` | **BREAK** | `nodriver` |
| `web` | OK | |
| `utils` | OK | logs "pygame not installed, sound notifications disabled" and degrades gracefully |
| `models` | OK | |

Undeclared runtime imports observed missing: `pydantic_settings`, `requests`, `nodriver`,
`keyring`, `cryptography`, `pygame`, `httpx`.

**Refinement to PKG-03.** PKG-03 names `websockets`, `starlette`, `httpx` and `requests`. The
observed situation differs:

- `websockets==17.0.1` and `starlette==0.45.3` **are** present after a clean install, arriving
  transitively via `uvicorn[standard]` and `fastapi` respectively. They are undeclared but not
  currently broken. Declaring them is still correct (relying on a transitive is fragile), but
  they are not the failure cause.
- `requests` is genuinely missing and genuinely breaks two modules.
- `httpx` is missing. It did not surface in these probes because nothing on the exercised paths
  imported it, but it is a hard top-level import for starlette's `TestClient`, so it is a test
  dependency rather than a runtime one. That distinction matters for where it gets declared.
- **`pydantic_settings` is the highest-impact omission and PKG-03 does not mention it.** It is
  what breaks the console script.
- `nodriver`, `keyring`, `cryptography`, `pygame` are also undeclared. `pygame` degrades
  gracefully by design; the other three do not.

## PKG-04: dead pins

`requirements.txt` on master still pins `selenium==4.43.0` and `webdriver-manager==4.0.2`. The
codebase uses `nodriver`. Neither appeared as an import failure in any probe because nothing
imports them. Removing them is safe and removes recurring Dependabot noise, which is exactly what
PKG-04 claims.

Interaction to be aware of: **PR #21 (currently open, deferred) proposes upgrading both**
`selenium` 4.43.0 to 4.46.0 and `webdriver-manager` 4.0.2 to 4.1.2. If PKG-04 removes them first,
those two lines of PR #21 become moot. Sequencing PKG-04 before any action on PR #21 reduces that
PR's surface.

## PKG-05: what the CI job should actually assert

Based on the observed failure order, the cheapest assertions that would have caught every defect
above, in the order they fail:

1. `shoppybot --help` exits 0. Catches every undeclared-dependency break at once, including the
   `pydantic_settings` one, without starting a server.
2. Import each of `core.service`, `core.orchestrator`, `core.registry`, `core.config_schema`,
   `core.captcha`, `web`, `utils`, `models` in the clean env. Pinpoints which dependency regressed.
3. Assert the wheel contains at least one entry under each of `web/static/`, `web/templates/`,
   and wherever `sounds` lands after the PKG-01 decision.
4. Resolve `Path(core.__file__).parent.parent / "plugins"` and assert 7 `shopbot_plugin_*.py`
   files. Protects the PKG-06 result from silently regressing.
5. `shoppybot web` starts. The expensive one, and last, because by then it is unlikely to be the
   first thing that breaks.

Note the install must be done **without** `requirements.txt` present, or the test proves nothing.
The current `ci.yml` installs from `requirements.txt` first (deliberately, per a comment on
master), which is correct for the test job and wrong for the wheel job. They need separate steps.

## Reproduction

```
python -m build --wheel --outdir <tmp>/dist
py -3.13 -m venv <tmp>/cleanenv
<tmp>/cleanenv/Scripts/python -m pip install "<tmp>/dist/shoppybot-2.0.0-py3-none-any.whl[web]"
<tmp>/cleanenv/Scripts/shoppybot --help     # observe ModuleNotFoundError: pydantic_settings
```

## Open decisions for the discuss step

1. Where `sounds/` lives after the fix, and whether `SOUNDS_DIR` stays a module-level constant.
2. Whether Phase 37 introduces a real `bundled_plugins_dir()` accessor (recommended, since
   workstream H needs the seam) or PKG-06 is reworded to match the existing bare expression.
3. Whether undeclared-but-transitively-present packages (`websockets`, `starlette`) get pinned
   explicitly or declared with floors.
4. Whether `httpx` is declared as a test dependency or a runtime one.
5. Whether the version stays `2.0.0` in `pyproject.toml`, given release-please is meant to own
   versioning and is currently blocked on a repo setting.
