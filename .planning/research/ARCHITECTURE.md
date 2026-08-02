# Architecture Research

**Domain:** Third-party plugin distribution for an existing single-process Python bot (SEED-003 / v5.0 workstream H)
**Researched:** 2026-08-02
**Confidence:** HIGH for every claim about existing code (each verified by reading the file, cited `file:line`). MEDIUM for the external-registry hosting/rate-limit specifics (verified against current GitHub REST docs). HIGH for the "no in-process sandbox" conclusion.

## Verification Basis

Every existing-code claim below was read, not recalled. Files read in full or in the cited range:

`core/registry.py`, `core/plugin_base.py`, `core/paths.py`, `core/service.py`, `core/credentials.py`, `core/config_schema.py`, `core/checkout_profile.py`, `core/session_store.py`, `core/cli/__init__.py`, `core/cli/plugins.py`, `core/cli/status.py`, `core/orchestrator.py` (lines 290-370, 480-650, 760-849), `models.py`, `web/routes/pages.py`, `web/routes/api.py` (lines 20-26, 168-181), `plugins/example_plugin.py`, `plugins/PLUGIN_DEV.md` (section 9), `docs/PLUGIN_REGISTRY.md`, `tests/test_no_input.py`, `pyproject.toml`, `requirements.txt`.

Two claims from the milestone brief were re-verified and are correct: the plugin directory is hardcoded in exactly three production call sites, and `PLUGIN_API_VERSION` has zero readers. Two further structural holes were found that the brief does not list, and both are worse than anything in it: plugin **construction** is not isolated the way plugin **import** is (`core/registry.py:83`), and the shipped reference plugin teaches authors to bypass the place-order guard (`plugins/example_plugin.py:99-110`).

## Standard Architecture

### System Overview

```
CLI front-end                                Web front-end (optional)
core/cli/plugins.py                          web/routes/pages.py:26
  install / update / remove / list             svc.list_plugins()  <-- executes every plugin file
  search / info                              web/routes/api.py:178
  OWNS all interaction (prompt + consent)      svc.get_analytics()  <-- executes every plugin file
        |                                            |
        |  ConsentRecord (data, not a callback)      |
        v                                            v
+---------------------------------------------------------------------+
| BotService  (core/service.py)   MOD-02: the ONLY seam a front-end    |
|                                 may call                             |
|   get_status()          :73    in-process only, see D3              |
|   list_plugins()        :143   + source / trust / state  [MODIFIED]  |
|   get_analytics()       :120   drop hardcoded path       [MODIFIED]  |
|   is_running_anywhere()        run-lock aware            [NEW]       |
|   plugin_* passthrough         to plugin manager         [NEW]       |
+---------------------------------------------------------------------+
        |                    |                       |
        v                    v                       v
+----------------+  +--------------------+  +----------------------+
| PluginRegistry |  | PluginManager      |  | RunLock              |
| core/registry  |  | core/plugin_manager|  | core/runlock.py [NEW]|
|                |  | .py         [NEW]  |  | data_dir()/run.lock  |
| multi-root     |  |                    |  +----------------------+
| discovery      |  |  +--------------+  |
| origin tagging |  |  | plugin_source|  |  fetch  -> requests
| defensive reads|  |  | .py    [NEW] |  |  resolve-> GitHub API
| api-version    |  |  +--------------+  |
| gate           |  |  | preflight    |  |  AST only, executes NOTHING
+----------------+  |  | .py    [NEW] |  |
        |           |  +--------------+  |
        |           |  | manifest     |  |  installed.json (atomic write)
        |           |  | .py    [NEW] |  |
        |           |  +--------------+  |
        v           +--------------------+
+---------------------------------------------------------------------+
| core/paths.py  [MODIFIED]  single source of truth for WHERE          |
|   bundled_plugins_dir()  -> <repo|site-packages>/plugins  (read-only)|
|   user_plugins_dir()     -> data_dir()/plugins           (writable)  |
|   plugin_roots()         -> [("bundled", ...), ("user", ...)]        |
+---------------------------------------------------------------------+
        |                                    |
        v                                    v
  plugins/                             data_dir()/plugins/
  shopbot_plugin_amazon.py             shopbot_plugin_thirdparty.py
  ... 7 bundled ...                    installed.json   <-- provenance
  example_plugin.py                    (registry ignores non-.py,
                                        core/registry.py:33-34)
```

### Component Responsibilities

| Component | New / Modified | Responsibility | Must NOT do |
|-----------|----------------|----------------|-------------|
| `core/paths.py` | MODIFIED | Own every plugin-directory path. `bundled_plugins_dir()`, `user_plugins_dir()`, `plugin_roots()` | Import registry or manager (it is imported by `logger`, must stay dependency-light) |
| `core/registry.py` | MODIFIED | Multi-root discovery, origin tagging, defensive attribute reads, API-version gate, shadow refusal | Fetch anything, prompt, or write files |
| `core/plugin_manifest.py` | NEW | Read/write/prune `installed.json`; recompute content hashes; report `managed` / `unmanaged` / `modified` | Import `requests`; be on the discovery critical path |
| `core/plugin_source.py` | NEW | Parse a source spec, resolve ref to commit SHA, fetch bytes, optional `GITHUB_TOKEN` | Write to disk; decide anything about trust |
| `core/plugin_preflight.py` | NEW | `ast.parse` only: syntax validity, presence of a `RetailerPlugin` subclass, declared `api_version`, statically-visible `domain_patterns`, flagged imports | Import, exec, or eval the candidate file. Ever. |
| `core/plugin_manager.py` | NEW | Orchestrate install/update/remove; refuse without a `ConsentRecord`; write atomically; update manifest | Call `input()` or `getpass` (forbidden in `core/` by `tests/test_no_input.py:60-66`) |
| `core/runlock.py` | NEW | Write/read/stale-detect `data_dir()/run.lock` | Be treated as a security boundary |
| `core/service.py` | MODIFIED | Expose manager + run-lock through the single seam; enrich `list_plugins()` | Grow interactive behaviour (`core/service.py:6-9` is explicit) |
| `core/cli/plugins.py` | MODIFIED | All interaction: the consent prompt, the typed confirmation, the Source column | Import `core.registry` (`core/cli/plugins.py:4`, MOD-02) |
| `core/orchestrator.py` | MODIFIED | Drop hardcoded path; defensive `domain_patterns`; per-plugin trust effects at the pre-transfer gate | Trust anything a plugin says after control transfers |
| `docs/plugin-registry.yml` + generator | NEW | In-repo source of truth for the registry; CI renders `registry.json` and the human table | Be described as a trust root |

## Recommended Project Structure

```
core/
  paths.py                  [MOD]  + bundled_plugins_dir / user_plugins_dir / plugin_roots
  registry.py               [MOD]  multi-root, origin, hardening, version gate
  plugin_base.py            [MOD]  + api_version, MIN_SUPPORTED_..., class-attr defaults
  runlock.py                [NEW]  cross-process "is a bot running"
  plugin_manifest.py        [NEW]  installed.json read/write/reconcile
  plugin_source.py          [NEW]  network boundary (requests + GitHub API)
  plugin_preflight.py       [NEW]  AST-only static inspection
  plugin_manager.py         [NEW]  install / update / remove orchestration
  service.py                [MOD]  seam methods, drop 2 hardcoded paths
  orchestrator.py           [MOD]  drop 1 hardcoded path, harden, trust effects
  cli/
    __init__.py             [MOD]  install/update/remove/search/info subparsers
    plugins.py              [MOD]  consent prompt (front-end owns interaction)
docs/
  plugin-registry.yml       [NEW]  one entry per registered plugin (PR-reviewable)
  registry.json             [NEW]  CI-generated, machine-readable, committed
  PLUGIN_REGISTRY.md        [MOD]  schema doc + generated table (no longer a wiki spec)
  PLUGIN_TRUST.md           [NEW]  or a section in SECURITY.md: the disclaimer
scripts/
  gen_plugin_registry.py    [NEW]  yml -> json + md
.github/workflows/
  registry.yml              [NEW]  regenerate + verify on PR
tests/
  test_plugin_manifest.py   [NEW]
  test_plugin_preflight.py  [NEW]
  test_plugin_precedence.py [NEW]
  test_registry_hardening.py[NEW]
  test_runlock.py           [NEW]
```

### Structure Rationale

- **Four small new `core/` modules instead of one `plugin_manager.py`.** The split is not aesthetic: `plugin_manifest.py` is read on the `plugins list` path and by `BotService.list_plugins()`, which must not drag `requests` into the dashboard render path; `plugin_preflight.py` must be provably import-free so a test can assert it contains no `exec_module` / `__import__` / `eval` call; `plugin_source.py` is the only module that touches the network, so it is the only one that needs offline-test mocking.
- **No new top-level package.** `pyproject.toml:22-25` already enumerates `core*`, `plugins*`, `notifications*`, `web*`. Adding modules inside `core/` needs zero packaging change, which matters because workstream B is already fixing packaging and H should not add to that surface.
- **`docs/plugin-registry.yml` inside the repo, not the wiki.** Argued in D7.

## Decisions

### D1. Second Import Root

**The three hardcoded call sites (all verified):**

| Site | Line | Context |
|------|------|---------|
| `core/orchestrator.py` | `802` | `plugins_dir = Path(__file__).parent.parent / "plugins"` inside `async_main`, feeding `PluginRegistry(...)` at `:812` |
| `core/service.py` | `133` | inside `get_analytics()`, feeding `PluginRegistry(...)` at `:134` |
| `core/service.py` | `159` | inside `list_plugins()`, feeding `PluginRegistry(...)` at `:160` |

`core/registry.py:80` takes `plugins_dir: Path` as a required positional, and `_discover_plugins(plugins_dir)` at `:19` scans exactly one directory. Roughly fifteen test call sites pass `plugins_dir=tmp_path` (`tests/test_registry.py:22,37,56,69,104,159,198,241`, `tests/test_proxy_wiring.py:160,184,203`, `tests/test_captcha_wiring.py:26`, `tests/test_plugin_base.py:144`, `tests/test_security_md.py:96`), so the parameter cannot simply be deleted.

**Design.**

Add to `core/paths.py`:

```python
def bundled_plugins_dir() -> Path:        # _repo_root() / "plugins"
def user_plugins_dir() -> Path:           # data_dir() / "plugins"
def plugin_roots() -> list[tuple[str, Path]]:
    return [("bundled", bundled_plugins_dir()), ("user", user_plugins_dir())]
```

`bundled_plugins_dir()` reuses `_repo_root()` (`core/paths.py:29-33`), which already honours the `_REPO_ROOT_OVERRIDE` test hook. `user_plugins_dir()` anchors on `data_dir()` (`core/paths.py:36-38`), which already honours `SHOPBOT_DATA_DIR` on every call. That single choice buys the whole test harness for free and keeps one redirection knob rather than two: `models.py:7`, `core/credentials.py:42`, and `core/session_store.py:43` all already anchor there.

Change `PluginRegistry.__init__` to `(self, config, plugins_dir: Path | None = None, proxy_pool=None, captcha_solver=None)` where:
- `plugins_dir` given (tests) means one root, labelled `"bundled"`, exactly as today.
- `plugins_dir` omitted means `paths.plugin_roots()`.

The three production sites then call `PluginRegistry(cfg)` / `PluginRegistry(cfg, proxy_pool=..., captcha_solver=...)` and the hardcoded paths disappear. After this change exactly one module knows where plugins live.

**Precedence rule: bundled wins, shadow is refused and logged, keyed on filename stem.**

Not "user wins," and the reason is specific to this codebase rather than general taste. A user-root file named `shopbot_plugin_amazon.py` would inherit, with no further consent, the operator's already-configured `AMZ_EMAIL` / `AMZ_PASSWORD` (`core/credentials.py:56-58`), the saved `amazon.bin` session cookies (`core/session_store.py:47`), and, if the operator passes `--cvv`, the raw CVV that `core/orchestrator.py:821-823` injects into whatever plugin `registry.route("https://www.amazon.com/")` returns. Shadowing a bundled plugin is the single highest-value move available to a hostile plugin, and bundled-wins removes it for one line of code.

Cost: an operator who wants to patch a bundled plugin must rename the file. That is a documentation line, and it is the right trade.

Secondary hardening in the same change: `core/registry.py:32` iterates `plugins_dir.iterdir()` **unsorted**, so when two plugins have overlapping `domain_patterns` the `route()` winner (`core/registry.py:122-124`, first match wins) is filesystem-order dependent. That is a latent non-determinism today and a security-relevant one the moment a second root exists. Iterate `sorted(...)`, and emit a WARNING at construction when two loaded plugins claim an overlapping pattern, naming both classes and both origin roots.

**Reporting the origin.** `_discover_plugins` currently returns `list[type[RetailerPlugin]]` (`core/registry.py:19`) and discards the path. Change it to return `list[tuple[type, PluginOrigin]]` with a frozen `PluginOrigin(root: str, path: Path)`, then have `PluginRegistry.__init__` stamp `plugin._origin` onto each instance immediately after construction. Stamping state onto plugin instances from the registry is the established idiom here: `assign_proxy` sets `_proxy` / `_pool` / `_proxy_required` (`core/registry.py:99-104`) and `assign_solver` sets `_captcha_solver` (`:113`).

`BotService.list_plugins()` (`core/service.py:161-175`) then adds `source` (`"bundled"` / `"user"`), `origin_path`, and `state` (`"managed"` / `"unmanaged"` / `"modified"`, from D2). `_format_plugins_table` (`core/cli/plugins.py:21-44`) grows Source and State columns. The dashboard already renders `list_plugins()` output (`web/routes/pages.py:26-31`), so it inherits the fields.

One name-collision note, verified: `core/registry.py:44` builds the spec with `path.stem` as the module name but never inserts into `sys.modules`, so two same-stem files in different roots would not collide in `sys.modules` for the module object itself. Imports performed *inside* those modules do register normally. The bundled-wins rule makes same-stem duplicates unreachable anyway, so this stays a footnote rather than a design constraint.

### D2. Provenance Record

**What must be persisted, per installed plugin:**

| Field | Why it is load-bearing |
|-------|------------------------|
| `stem` | Join key to the discovered file; primary key of the record |
| `source_kind` | `github` / `url` / `local`; drives update semantics |
| `source_url` | The exact string the user was shown at consent time |
| `ref` | Branch or tag the user asked for |
| `resolved_sha` | The commit actually installed. SEED-003:78 asks for SHA pinning specifically so an install "cannot silently change later" |
| `remote_path` | Path inside the repo (a repo may host several plugins) |
| `content_sha256` | Hash of the exact bytes written. Independent of git, and the only drift signal available after the fact |
| `installed_at` | ISO-8601 UTC, matching the existing convention (`core/plugin_base.py:187`, `models.py` `confirmed_at`) |
| `declared_api_version` | What the static pre-flight read (D4) before writing anything |
| `consent` | `{granted: true, at: iso, mode: "typed"\|"flag", prompt_version: n, source_shown: str}` |
| `trust` | `bundled` / `third_party`. The field D6's enforceable mitigations key off |
| `schema` | Record-format version, for future migration |

**Where: a single JSON manifest at `user_plugins_dir()/installed.json`.** Not the SQLite DB, not a lockfile, not config.yml.

Arguments, against how this app already stores state:

1. **Colocation is the integrity property.** The record must live and die with the directory it describes. If the operator deletes or moves `data_dir()/plugins/`, the provenance goes with it and nothing is left claiming a plugin is installed. A SQLite row would survive the file's deletion and produce ghost entries, and `models.py:33-95` `initialize_db` is a strictly additive migrator: it adds columns, never drops rows or tables, and has no cascade concept anywhere.

2. **The DB is item-domain state, and it is the hot path.** Every table and column in `models.py` is keyed to a tracked item link (`items`, `price_history`). `get_items_sync` (`models.py:98`) is called once per poll cycle per plugin (`core/orchestrator.py:344`) against a WAL connection with a 5s busy timeout (`models.py:19-23`). Install metadata has a completely different lifecycle, is written at most a few times ever, and is read by nothing in the poll loop. Putting it there mixes two lifecycles for zero benefit.

3. **File-based sidecar state already has precedent here, twice.** `core/session_store.py:43` writes per-platform blobs to `data_dir()/sessions/<platform>.bin`; `core/credentials.py:42` writes `creds.bin` to `data_dir()`. `installed.json` is the same shape and, unlike both, contains **no secrets**, so it can be plaintext and human-readable. That matters: "where did this file come from" must be answerable with a text editor when the app will not start.

4. **Against a lockfile.** A lockfile implies a declarative manifest plus resolve/sync semantics (`plugins.toml` -> `plugins.lock`). There is no dependency graph to resolve: plugins are single files with no inter-plugin dependencies, discovered by filename convention (`core/registry.py:36`). Two files where one suffices. Revisit only if plugins ever depend on each other.

5. **Against config.yml.** `AppConfig` is user-owned and is rewritten wholesale by `shoppybot config set`, whose own help text warns that comments and formatting are destroyed (`core/cli/__init__.py:139-143`). A consent record should not live in a file the tooling rewrites and the user is invited to hand-edit.

**Write discipline:** reuse the atomic-write idiom already proven twice, `tempfile.mkstemp` in the target directory, fd closed inside the `with` block, then `os.replace` outside it (`core/credentials.py:265-281`, `core/session_store.py:61-72`). That ordering is a documented Windows requirement in both places.

**No conflict with discovery:** `core/registry.py:33-34` skips any file whose suffix is not `.py` silently, so `installed.json` sitting in the plugins directory is invisible to the scanner.

**Reconciliation rule, and it is the important part.** Discovery stays the source of truth for *what runs*; the manifest is the source of truth for *what was vouched for*. A `.py` present with no manifest entry is reported `unmanaged`. A manifest entry with no file is stale and is pruned with an INFO log. The manifest must **never gate discovery**, because that would present a hard security boundary the design cannot actually enforce (D5). On `plugins list`, recompute `content_sha256` for managed files and mark drift as `modified`. One `hashlib` read per file, stdlib only, and it is the only honest tamper signal available on a machine where the attacker and the defender are the same user account.

### D3. Lifecycle Semantics

**Restart is required, and the design should say so rather than engineer around it.**

The mechanics, verified:

- Plugin instances are constructed once, at `core/registry.py:83`, from classes obtained by `spec.loader.exec_module` at `core/registry.py:48`. `async_main` builds the registry once (`core/orchestrator.py:812`) and supervises those instances for the life of the run (`core/orchestrator.py:833-839`). Nothing re-scans the directory mid-run.
- After `setup()` (`core/registry.py:190`) each active instance owns a live nodriver Browser subprocess and, potentially, a restored authenticated session (`core/plugin_base.py:326-372`).
- Python cannot unload the code. Per the CPython `importlib` documentation on `reload`: "If a module instantiates instances of a class, reloading the module that defines the class does not affect the method definitions of the instances, they continue to use the old class definition," and "Other references to the old objects... are not rebound to refer to the new objects." Deleting from `sys.modules` does not free a module whose objects are still referenced, and the registry holds exactly such references.
- Import side effects (threads, `atexit` hooks, monkeypatches) are not undone by deleting the file.

**Do not build hot reload.** With live browsers, supervised restart logic (`core/orchestrator.py:167-186`), and non-unloadable modules, a hot reload is the most direct route to two plugin instances concurrently driving a checkout. Say no in writing so a future contributor does not treat it as an obvious missing feature.

**Should the manager refuse while the bot is running?** The two directions fail differently:

- **`remove` while running is the dangerous one.** The running process already holds the imported module and the live instance. Deleting the file changes nothing until restart, but an operator who believes the removal took effect now thinks a plugin is disabled while it is still driving a browser toward a Place Order click. That is a false-safety belief about a money-spending component. `remove` therefore **refuses by default when a run-lock is present**, and requires `--force`.
- **`install` / `update` while running is subtler than it looks, and the intuition is wrong.** The running orchestrator will not pick the file up, true. But `core/service.py:133` and `:159` each construct a *fresh* `PluginRegistry` per call, so the newly written file is imported (that is, executed) by the very next dashboard page render (`web/routes/pages.py:26`, which explicitly notes it is "a filesystem scan + importlib per plugin file") or the next `/api/analytics` fetch (`web/routes/api.py:178`). Newly installed third-party code executes in the **web process**, promptly, without any bot run. These two commands therefore **warn** rather than refuse, but the warning must say this rather than the reassuring falsehood.

Every successful `install` / `update` / `remove` prints `Restart the bot for this to take effect.` unconditionally.

**What does `BotService` expose to answer "is it running"? Today: nothing usable, and the codebase already admits it.**

`BotService.get_status()` returns `{"running": self._running, ...}` (`core/service.py:73-85`), but `_running` is per-object in-process state, and `core/service.py:312` constructs a brand new `BotService()` for every CLI dispatch. `core/cli/status.py:6-9` states the consequence in its own module docstring: "invoking `shoppybot status` in a separate process from the running bot shows running=False because BotService is instantiated fresh in main()." A grep of `core/` and `web/` for pid / lock / flock / msvcrt returns only two `threading.Lock` hits in `core/credentials.py`. There is no PID file, no lock file, no socket.

So the design must add the seam:

- New `core/runlock.py`: `acquire()` / `release()` / `read()` over `data_dir()/run.lock` holding `{"pid": int, "started_at": iso}`.
- `BotService.start()` acquires in the body (`core/service.py:203`) and releases in the existing `finally` blocks (`core/service.py:224-227` and `:231-234`); `run()` does the same around `core/service.py:266-269`.
- New `BotService.is_running_anywhere() -> dict` returning `{"in_process": bool, "lock": {...} | None, "stale": bool}`. The CLI must read it through `BotService`, not by importing `core.runlock` directly, because `core/cli/plugins.py:4` states the MOD-02 constraint that the handler "imports only json and BotService, never core.registry."
- Staleness is **advisory only**. A PID that no longer exists means the lock is reported stale and the command proceeds with a warning. Never make a safety-critical decision out of cross-platform PID liveness; `--force` always exists.

One further contention worth recording: `core/orchestrator.py:830` starts a stdin listener for the running bot. An interactive consent prompt (D5) issued while a bot runs in the same terminal would fight it. Another reason for the manager to warn and for the prompt to live in a separate CLI invocation.

### D4. API Version Enforcement

**Verified:** `PLUGIN_API_VERSION = 2` is defined at `core/plugin_base.py:15`. A repo-wide grep finds it only in that definition, in docstring comments within the same file (`:77,101,137,147,157,206,244,293,339,383`), and in planning documents. Zero readers. It is decorative exactly as the brief says.

**What a plugin declares:** a class attribute `api_version` on the subclass, defaulted on the ABC:

```python
# core/plugin_base.py
PLUGIN_API_VERSION = 2
MIN_SUPPORTED_PLUGIN_API_VERSION = 2   # NEW: policy as data, not as branching

class RetailerPlugin(ABC):
    api_version: int = PLUGIN_API_VERSION   # NEW: subclasses inherit; nothing breaks
```

A class attribute, not a module-level constant in the plugin file, because discovery already collects classes via `inspect.getmembers(module, inspect.isclass)` (`core/registry.py:53`), so the class attribute is what the gate already has in hand. Defaulting it on the ABC keeps all 7 bundled plugins and `plugins/example_plugin.py` working with zero edits.

Note a deliberate distinction against the v1 threat model. `01-02-PLAN.md:131` made `PLUGIN_API_VERSION` module-level specifically so "a subclass cannot shadow it." That reasoning applies to the *core's* number. The plugin's *claim* is a different value, and it is supposed to be settable by the plugin. They are compared, never conflated.

**Where the gate belongs: discovery for the runtime gate, install-time static parse for the pre-flight gate, and explicitly not `__init_subclass__`.**

- **Not `__init_subclass__`** (`core/plugin_base.py:82-92`). It is tempting because a raise there is already caught and skipped by `core/registry.py:49-51`. It is the wrong place for two reasons. First, it fires *after* the module body has executed, so the untrusted code already ran and a version check buys nothing security-wise. Second, it fires for intermediate abstract bases and test doubles, adding failure modes with no compensating benefit. (Verified-safe footnote: an unhashable `difficulty` value at `core/plugin_base.py:88` raises `TypeError` rather than `ValueError`, but discovery catches bare `Exception`, so that path is already isolated.)

- **Discovery is the runtime gate**, in the class-collection loop at `core/registry.py:53-56`. Compare `getattr(obj, "api_version", MIN_SUPPORTED)` against the two constants.
  - `declared > PLUGIN_API_VERSION`: skip, WARNING naming the file, both versions, and "upgrade ShopPyBot."
  - `declared < MIN_SUPPORTED_PLUGIN_API_VERSION`: skip, WARNING naming the file and "plugin targets an unsupported API version."
  - `MIN_SUPPORTED <= declared <= PLUGIN_API_VERSION`: load. If `declared < PLUGIN_API_VERSION`, log INFO, do not skip.

  The soft-fail on older-but-supported versions is the deliberate call. This codebase's entire v3/v4 history is a list of "PLUGIN_API_VERSION stays 2, additive" comments across ten sites in `core/plugin_base.py`. Additive minor change is the realistic future; hard-failing older plugins would break the ecosystem this milestone exists to create. Encoding the floor as `MIN_SUPPORTED_PLUGIN_API_VERSION` makes a genuine future major bump a one-line data change.

- **Install time is a pre-flight gate, and it must not import to check.** Reading `api_version` by importing the downloaded file *is* the arbitrary code execution the consent gate is supposed to gate, and doing it before consent inverts the whole design. Instead `core/plugin_preflight.py` uses `ast.parse` (executes nothing) to find a top-level or class-body `api_version = <int>` assignment, and the registry index (D7) carries a declared value for registry-sourced plugins. If the static read finds an incompatible version, refuse **before writing the file** and say why. If it finds nothing, install and let the discovery gate handle it.

The ordering rule to hold: **static check before write, runtime check at discovery, never an import in order to "check."**

### D5. Consent Gate Placement

**Flow, with the gate before the write:**

```
shoppybot plugins install <source>
  1. core/plugin_source.py    parse source spec
  2. core/plugin_source.py    resolve ref -> commit SHA
                              GET /repos/{owner}/{repo}/commits/{ref}
  3. core/plugin_source.py    fetch bytes at the pinned SHA
                              raw.githubusercontent.com/{o}/{r}/{sha}/{path}
  4. core/plugin_preflight.py ast.parse ONLY:
                                - parses at all?
                                - contains a RetailerPlugin subclass?
                                - declared api_version
                                - statically-visible domain_patterns
                                - flagged imports (core.credentials, os.environ,
                                  subprocess, socket, ctypes, eval/exec)
  5. core/plugin_manager.py   shadow check against bundled stems (D1)
  6. core/plugin_manager.py   compute content_sha256
  ---------------- nothing has been written and nothing has been executed ----
  7. core/cli/plugins.py      RENDER CONSENT: source URL, full SHA, sha256,
                              target filename, api_version, shadow result,
                              flagged-import summary, third-party disclaimer
  8. core/cli/plugins.py      require typed confirmation (the plugin name,
                              not "y")
  ---------------- consent obtained ----------------------------------------
  9. core/plugin_manager.py   atomic write into user_plugins_dir()
 10. core/plugin_manifest.py  append record incl. ConsentRecord
 11. core/cli/plugins.py      "Restart the bot for this to take effect."
```

**Interaction lives in the CLI, not in core.** Two hard constraints force this and they agree. `tests/test_no_input.py:60-66` AST-scans all of `core/` (recursively, so `core/cli/` included) and fails on any `input()` call. And `core/service.py:6-9` states the seam rule: "this module never prompts for secrets or interactive input, secrets are collected by the front-end and passed in." So `core/plugin_manager.install()` takes a `ConsentRecord` as a parameter and **refuses when it is absent or not granted**; it never asks. The prompt itself reuses the established visible-prompt idiom at `core/cli/setup.py:51-63`, which uses `print()` plus `sys.stdin.readline()` and documents "no input() builtin."

Typed confirmation rather than `y/N` is deliberate: it forces the operator to read the thing being consented to. `--yes` exists for automation and records `consent.mode = "flag"` so the manifest is honest about how consent was obtained.

**Now the part that must be said plainly: the gate cannot be made unbypassable, and file-drop remains possible.**

`_discover_plugins` (`core/registry.py:32-57`) iterates the directory and executes every file matching `shopbot_plugin_*.py`. It consults nothing else. Anything running as the operator's user can copy a file into `user_plugins_dir()` and have it executed at the next registry construction, which per D3 is the next dashboard page load or `/api/analytics` fetch, not necessarily the next bot run.

Making the manifest authoritative does not fix this. Whoever can write a `.py` into that directory can write `installed.json` beside it with the same permissions. Signing the manifest needs a key that lives on the same disk under the same account. There is no local root of trust to build on.

So state the design position rather than dressing it up: **the consent gate is a speed bump against the operator's own carelessness and against a malicious install source. It is not a control against a local attacker.** Its three real jobs are (1) make the trust decision explicit and legible at the moment it is made, (2) leave a durable record that it was made, (3) pin the artifact by SHA and content hash so it cannot silently change afterwards. All three are achievable.

What remains worth building is **visibility, not enforcement**: `plugins list` marks unmanifested files `unmanaged` and hash-drifted managed files `modified`, in both CLI and dashboard. An operator who sees `unmanaged` next to a plugin they never installed has exactly the signal they need, and that signal is real.

### D6. Capability Limiting Seam

**What a third-party plugin can reach today, all verified:**

| Reachable via | Yields |
|---------------|--------|
| `from core.credentials import get_store` (`core/credentials.py:310-320`, module-level singleton) | All 20 `SECRET_KEYS` (`:47-77`): every retailer email/password, the Discord webhook, SMTP password, Twilio triple, the 2captcha key |
| `from core.checkout_profile import load_checkout_profile` (`core/checkout_profile.py:57`, which itself calls `get_store()` at `:77`) | Full legal name, street address, city/state/zip/country, phone |
| `from core.session_store import build_session_store` (`core/session_store.py:101-108`) | `.restore("amazon")` returns decrypted cookies for **any** platform. The passphrase comes from `_resolve_passphrase()` reading `SHOPBOT_STORE_PASSPHRASE` from the environment (`core/credentials.py:331`), not from a per-plugin capability |
| `self.config`, handed to every plugin at construction (`core/registry.py:83` -> `core/plugin_base.py:95`) | The entire `AppConfig`, including `proxy.urls`, which `core/config_schema.py:344-347` documents may embed `user:pass@` credentials |
| `self._cvv` | Raw CVV, injected by `core/orchestrator.py:820,823` |
| `self.driver` | A live, authenticated browser session on the retailer |
| `os.environ`, `open()`, `socket`, `subprocess`, `ctypes` | Plain Python. Nothing intercepts any of it |

**Is capability limiting achievable in-process? No. Say so.**

Python has no capability model. Module-level singletons are reachable by any code in the same interpreter. There is no supported in-process Python sandbox: `rexec` and `Bastion` were removed from the standard library precisely because they could not be made safe, and every subsequent attempt has been broken by `sys._getframe`, `gc.get_objects()`, or `ctypes`. Any "capability gate" that lives in the same process as the plugin it gates is theatre, and the quality bar for this document says to name that rather than propose it.

**The narrowest seams that do exist, ranked:**

1. **`core/credentials.py:get_store()` is the single chokepoint for every secret in the system.** All 20 `SECRET_KEYS` and, transitively, all 9 `CHECKOUT_PROFILE_KEYS` flow through this one function. If anything were gateable, it would be this one. It is also the cheapest place to hang an audit hook or caller attribution. It is *not* enforceable, for the reason above.

2. **`core/plugin_base.py:95` (`self.config = config`) is the config hand-off, one line.** A third-party plugin could be handed a reduced `AppConfig` carrying only its own `platforms.<key>` section plus `debug`, with `proxy` and `credentials` blanked. This does not stop a determined plugin from doing `from core.config_schema import AppConfig; AppConfig()`, but it does close the lazy and accidental paths, and it makes intent legible in the manifest.

3. **`place_order_guarded()` is not a gate, and this is the finding that changes the design.**

   `core/plugin_base.py:151-192` is a concrete helper on the ABC. Nothing invokes it on the plugin's behalf. The orchestrator calls `plugin.auto_buy(link)` directly (`core/orchestrator.py:391`), and a third-party `auto_buy` can click Place Order without ever touching the guard. `.planning/PROJECT.md:225` records the v4.0 decision as "one enforcement point honors monitor-only/test_mode for all 7 plugins," which is true for cooperating in-tree plugins and false for third-party code.

   The proof is shipped in the repo: `plugins/example_plugin.py`, the reference implementation `plugins/PLUGIN_DEV.md` instructs authors to copy verbatim, clicks `#place-order` directly at `:99-103` and calls `update_item_purchased(url)` at `:110`. It never calls `place_order_guarded()`, and it bypasses the confirmed-order idempotency anchor. The canonical template teaches the bypass. **Fixing `plugins/example_plugin.py` is a prerequisite for promoting the project as third-party extensible**, and it is a small, high-value item.

   The consequence for the trust model: **`debug.test_mode` is not enforceable against a third-party plugin, because it is only honoured inside the opt-in guard. `debug.monitor_only` IS enforceable, because `core/orchestrator.py:571-578` checks it and skips calling `auto_buy` entirely.** That check happens *before control transfers to plugin code*, which is the only place enforcement can ever work.

**Partial mitigations worth building** (all achievable, none a sandbox):

- **Per-plugin trust effects enforced at the pre-transfer gate.** Use the manifest's `trust` field at `core/orchestrator.py:571`: force `monitor_only` for a `third_party` plugin until the operator explicitly clears it. This is a genuine control precisely because it never transfers control.
- **Keep third-party plugins out of the CVV injection.** `core/orchestrator.py:817-823` is already hardcoded to route `bestbuy.com` and `amazon.com` URLs only, so third-party plugins never receive `_cvv` today. That is good and accidental. Add a regression test so it stays true, and note that a shadowing plugin would have received it, which is a second argument for D1's bundled-wins rule.
- **`sys.addaudithook` (PEP 578) installed before `_discover_plugins` runs.** Not a sandbox, and it must not be sold as one, but audit hooks cannot be removed once installed and they fire on `open`, `socket.connect`, `subprocess.Popen`, `import`, `exec`. Attribute events to third-party plugin frames and log them. This is forensics and detection, not prevention. Scope it to a small event allowlist or to install-time and first-run only, or it will dominate the log volume.
- **Static AST pre-flight surfacing flagged imports in the consent prompt** (D5 step 4). Trivially evaded by `__import__("cor" + "e.credentials")`, so present it as "what this plugin openly does," never as a verdict.
- **Document the real fix as deferred.** Process isolation plus IPC. `.planning/PROJECT.md:93` already lists it as a post-v5.0 candidate and calls it "by far the most expensive." That is the correct call, and recording it as a decision (SEED-003:84 asks for exactly that: "a decision on the record, not a default that happens because nobody raised it") is part of the deliverable.

### D7. Machine-Readable Registry

**The current state.** `docs/PLUGIN_REGISTRY.md` is a specification *for a GitHub wiki table*, not data. It defines nine required columns (`:20-30`), a population process performed by hand (`:41-52`), and states at `:9-12` that "the live registry page is maintained separately on the GitHub wiki by a project maintainer. The wiki is not part of this repository and cannot be updated via a pull request." REG-01, the actual wiki page, is still outstanding across two milestones. Manual wiki curation has not happened, and the design should assume it will not.

**Design: invert the direction. The repo becomes the source of truth; the wiki becomes a rendering, or is retired.**

- `docs/plugin-registry.yml` holds one entry per registered plugin: the nine spec'd columns plus what a *manager* needs and a wiki table does not have (`source_repo`, `source_path`, `pinned_ref`, `api_version`, `filename_stem`). A community submission becomes a PR touching one YAML file, which routes it through `.github/PULL_REQUEST_TEMPLATE.md` (which already collects plugin metadata) and through the `SECURITY.md:50-52` per-platform risk-assessment requirement that SEED-003:115-117 correctly identifies as the gate a third-party plugin otherwise bypasses entirely.
- A generator (`scripts/gen_plugin_registry.py`) emits two artifacts: `docs/registry.json` (machine-readable) and the rendered markdown table appended into `docs/PLUGIN_REGISTRY.md`. A CI job regenerates and fails the PR if the committed output is stale, which is the same shape as the existing doc guards in `tests/test_docs.py`.
- **Hosting: commit `docs/registry.json` and serve it from `raw.githubusercontent.com` at a tag.** Simplest possible option, zero hosting setup, no extra workflow, and it is already versioned. GitHub Pages is the upgrade path if cache headers become a problem; do not start there.
- **Wiki sync: recommend retiring the wiki page rather than syncing it.** A workflow *can* push rendered markdown to `<repo>.wiki.git` with a token, and that is the only reliable sync mechanism, but it costs a credential and a sync path to maintain the very artifact that has gone un-maintained for two milestones. Point the README at `docs/PLUGIN_REGISTRY.md` instead. If the wiki is kept for other reasons, its registry page should carry a single line linking to the generated file.
- `docs/PLUGIN_REGISTRY.md` changes role: from "spec a human follows when editing a wiki" to "schema documentation for the YAML, plus the generated table." A test validates every YAML entry against a pydantic model and asserts the nine required fields are non-empty.

**How the manager consumes it.**

`shoppybot plugins search <term>` and `shoppybot plugins info <name>` fetch `registry.json` with `requests` (already in `requirements.txt` at `requests==2.33.1`, so no new dependency), cache it under `data_dir()/registry-cache.json` with the ETag, and resolve `name -> source_repo + source_path + pinned_ref`. `shoppybot plugins install <name>` uses that resolution. `shoppybot plugins install <url>` stays available for unregistered plugins, with a louder consent prompt: "this plugin is not in the ShopPyBot registry."

**The registry is a discovery index and a convenience, not a trust root.** Say it in the docs. A maintainer-curated list that anyone can open a PR against is not a security boundary; what makes it marginally better than an arbitrary URL is the `SECURITY.md:50-52` risk-assessment requirement attached to merging an entry.

**Rate-limit note (verified against current GitHub REST documentation).** Resolving a ref to a SHA uses `GET /repos/{owner}/{repo}/commits/{ref}`, where ref "can be a commit SHA, branch name (heads/BRANCH_NAME), or tag name (tags/TAG_NAME)". Unauthenticated primary rate limit is **60 requests per hour per IP**. Fine for install-time use, but the manager must handle a 403 with `X-RateLimit-Remaining: 0` with a clear message and support an optional token. Adding `GITHUB_TOKEN` to `SECRET_KEYS` (`core/credentials.py:47`) has a documented side effect the file itself warns about at `:78-80`: `migrate_from_env`, `EnvVarBackend.list`, and `KeyringBackend.list` all iterate `SECRET_KEYS`, so widening it silently changes their behaviour. Make that a deliberate, tested change or read the token from `os.environ` only.

### D8. `route()` Hardening and Other Unguarded Reads

Verified crash sites reachable from a non-conforming third-party plugin. `domain_patterns` is a **bare annotation with no assigned default** at `core/plugin_base.py:74`, so a subclass that omits it genuinely has no attribute and every direct read raises `AttributeError`.

| Site | Read | Blast radius |
|------|------|--------------|
| `core/registry.py:123` | `plugin.domain_patterns` in `route()` | `AttributeError` out of routing. Called from `core/orchestrator.py:818,821` at startup |
| `core/registry.py:152` | same, in `_route_all()` | Crashes `plugins_for_items` (`:166`) and `setup_for_items` (`:185`), i.e. **bot startup** |
| `core/registry.py:140` | `isinstance(plugin.domain_patterns, str)` in `platform_of()` | The `getattr(..., [])` fallback on the next line (`:142`) is **dead code**: the `isinstance` on `:140` raises first. `platform_of` is documented "never raises" at `:135-137`, is called from the write-queue drain inside a `try` (`core/orchestrator.py:622`) but from `get_analytics` **without** one (`core/service.py:141`) |
| `core/service.py:165-166` | `isinstance(plugin.domain_patterns, str)` in `list_plugins()` | Identical dead-`getattr` bug at `:167`. Crashes the dashboard render (`web/routes/pages.py:26`) and `shoppybot plugins list` |
| `core/orchestrator.py:359` | `plugin.domain_patterns` in the poll loop | Crashes `run_plugin`, which `supervise` treats as a plugin crash and backoff-restarts (`:145-186`), producing an infinite restart loop instead of a clean skip |
| **`core/registry.py:83`** | `[cls(config) for cls in plugin_classes]` | **Not isolated.** `_discover_plugins` isolates *import* failure at `:43-51`, but *construction* is a bare list comprehension. A third-party `__init__` that raises takes down bot start, the dashboard render, and `/api/analytics`. This is the largest single-plugin-kills-everything hole and it is not in the 16-gap list |
| `core/registry.py:32` | unsorted `plugins_dir.iterdir()` | Not a crash. Route winner on overlapping patterns is filesystem-order dependent, which becomes security-relevant with a second root |
| `core/orchestrator.py:572` | `getattr(plugin.config, "debug", None) if plugin.config is not None` | `plugin.config is not None` itself raises if the attribute is absent (a subclass that overrides `__init__` without `super()`). **This is the monitor-only check**, the one control D6 identified as actually enforceable. Highest priority of the `config` reads |
| `core/orchestrator.py:486` | `getattr(plugin.config, "checkout", None)` | Same root cause, raises inside `_try_auto_buy` |
| `core/orchestrator.py:500,517,522` | `plugin._checkout_stage` | Set only in `__init__` (`core/plugin_base.py:103`); absent if `super().__init__` skipped |
| `core/orchestrator.py:400` | `plugin.get_active_tab()` | Concrete default exists (`core/plugin_base.py:142-149`), but a subclass override can still raise |
| `core/orchestrator.py:310` | `plugin.config.platforms` | **Already safe**: wrapped by the `try/except Exception` at `:306-319` |
| `core/plugin_base.py:88` | `cls.difficulty not in _VALID_DIFFICULTY` | **Already safe**: an unhashable value raises `TypeError`, caught by discovery's bare `except Exception` at `:49` |

**Two fixes cover almost all of it.**

*Fix A, a single defensive reader in `core/registry.py`, called from all five `domain_patterns` sites:*

```python
def _domain_patterns(plugin) -> list[str]:
    """Never raises. Missing or malformed patterns mean 'matches nothing'."""
    raw = getattr(plugin, "domain_patterns", None)
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    try:
        return [str(p) for p in raw]
    except TypeError:
        return []
```

Fail-safe semantics: a plugin that cannot say what it handles handles nothing. It still loads, still appears in `plugins list`, and routes zero items. Warn **once at discovery** naming the class, not inside `_domain_patterns` itself, which sits in a per-item hot loop (`core/orchestrator.py:359`).

Keep the bare annotation at `core/plugin_base.py:74` rather than giving `domain_patterns` a class-level `[]`. A class-level default would make the core safe but would also silently erase the "the author forgot" signal. The helper makes the core safe; the discovery warning preserves the signal.

*Fix B, class-attribute defaults mirroring the instance defaults, on `RetailerPlugin`:*

```python
class RetailerPlugin(ABC):
    config = None
    _checkout_profile = None
    _checkout_stage: str = ""
```

One line each, zero behaviour change for conforming plugins, and it fixes `core/orchestrator.py:486`, `:500`, `:517`, `:522`, and `:572` **without touching the orchestrator at all**. Highest leverage change in the entire workstream. Unlike `domain_patterns` these carry no author-error signal, so a default is purely upside.

*Plus two small ones:* wrap `cls(config)` at `core/registry.py:83` in a per-class `try/except Exception` mirroring `:49-51` (log the class name, skip that plugin, keep the rest), and iterate `sorted(plugins_dir.iterdir())` at `:32`.

## Data Flow

### Install

```
CLI  ->  BotService.plugin_install(spec, consent=None, dry_run=True)
             -> plugin_source.resolve()      ref -> SHA          [network]
             -> plugin_source.fetch()        bytes at SHA        [network]
             -> plugin_preflight.inspect()   ast.parse only      [no exec]
             -> plugin_manager.shadow_check() vs bundled stems
             <- InstallPreview {sha, sha256, api_version, flags, shadow, target}
CLI  ->  render consent + typed confirm     (core/cli/plugins.py, stdin.readline)
CLI  ->  BotService.plugin_install(spec, consent=ConsentRecord(...))
             -> plugin_manager.write()       mkstemp + os.replace into user root
             -> plugin_manifest.upsert()     installed.json, atomic
             <- InstallResult
CLI  ->  print "Restart the bot for this to take effect."
```

The preview and the commit are the same call with and without a `ConsentRecord`. The manager refuses the write when the record is absent. Nothing between resolve and write ever imports the candidate file.

### Discovery (per registry construction, unchanged in shape, hardened in detail)

```
paths.plugin_roots()            [("bundled", ...), ("user", ...)]
  -> for each root, sorted(iterdir())
       skip non-.py                               registry.py:33
       skip non shopbot_plugin_*  + WARNING       registry.py:36-41
       stem already claimed by an earlier root?  -> SKIP + WARNING (shadow refused)
       exec_module in try/except                  registry.py:43-51
       for each RetailerPlugin subclass:
           api_version gate                       [NEW]
           collect (cls, PluginOrigin(root, path))
  -> construct each, per-class try/except         [NEW, fixes registry.py:83]
  -> stamp plugin._origin                         [NEW]
  -> warn on overlapping domain_patterns          [NEW]
```

### Remove

```
CLI -> BotService.is_running_anywhere()
         lock present and not stale? -> refuse unless --force
CLI -> BotService.plugin_remove(stem)
         plugin_manager: refuse if origin root is "bundled"
         unlink file; plugin_manifest.remove(stem)
CLI -> print "Removed. The running process, if any, still holds this
              plugin in memory. Restart to fully unload."
```

That last sentence is the whole point of D3 and must not be softened.

## Load and Concurrency Considerations

This is a single-operator desktop tool; there are no user-scale tiers. What matters is repeated execution and contention.

| Concern | Reality today | Consequence for H |
|---------|---------------|-------------------|
| Plugin modules re-executed per registry construction | 3 sites build a fresh `PluginRegistry`: `core/orchestrator.py:812` (once per run), `core/service.py:134` (every `/api/analytics` fetch, `web/routes/api.py:178`), `core/service.py:160` (every dashboard render, `web/routes/pages.py:26`) | Untrusted code runs far more often than "once at bot start." This is the core reason install must warn even when no bot is running |
| Plugin count grows with a manager | 7 bundled today, unbounded after | Discovery cost is linear in file count and is on the dashboard render path. If it becomes visible, cache the discovery result on `BotService` with a directory-mtime key. Do **not** cache the module objects, that is hot reload by the back door (D3) |
| `installed.json` writers | Only the manager, only from a CLI invocation | Atomic replace is sufficient. No lock needed. Note it explicitly so nobody adds one |
| Registry index fetch | Install and search only | Unauthenticated GitHub limit 60/hr/IP. ETag-cache the JSON under `data_dir()` |
| stdin contention | `core/orchestrator.py:830` starts a stdin listener while running | Interactive consent while a bot runs in the same terminal fights it. Another reason to warn |

## Anti-Patterns

### Anti-Pattern 1: Making the manifest authoritative for discovery

**What people do:** refuse to load any plugin without a matching `installed.json` entry, and call it enforcement.
**Why it is wrong:** whoever can drop a `.py` into the directory can write the JSON beside it with identical permissions. It presents a boundary that does not exist, which is worse than presenting none, because the operator now trusts a control that is not there.
**Do this instead:** manifest informs, discovery decides. Report `unmanaged` loudly in `plugins list` and on the dashboard. Visibility is real; the boundary is not.

### Anti-Pattern 2: Importing the candidate file to inspect it

**What people do:** "just import it to read `api_version` / `domain_patterns` before installing."
**Why it is wrong:** import is execution (`plugins/PLUGIN_DEV.md:214`, and `core/registry.py:48` is literally `spec.loader.exec_module`). Inspecting before consent by importing performs the exact action consent is supposed to authorise.
**Do this instead:** `ast.parse` in `core/plugin_preflight.py`, which executes nothing, plus the registry index. Accept that a dynamically computed `domain_patterns` is simply invisible to pre-flight, and say so in the prompt.

### Anti-Pattern 3: Hot reload after install or update

**What people do:** re-scan the directory and swap plugin instances in the running process.
**Why it is wrong:** the old module and its instances persist (CPython `importlib.reload` documentation: reloading "does not affect the method definitions of the instances"), the old instance still owns a live browser and a supervised task (`core/registry.py:190`, `core/orchestrator.py:833-839`), and the most likely outcome is two instances racing toward the same Place Order click.
**Do this instead:** require a restart, print it every time, and write the refusal into the design docs so it is not re-proposed.

### Anti-Pattern 4: Treating `place_order_guarded()` as the safety boundary for third-party code

**What people do:** assume `test_mode` protects the operator because `core/plugin_base.py:151` exists.
**Why it is wrong:** the guard is opt-in and nothing invokes it for the plugin. The shipped reference implementation `plugins/example_plugin.py:99-110` clicks `#place-order` directly and never calls it, so the template itself teaches the bypass.
**Do this instead:** enforce at the pre-transfer gate, `core/orchestrator.py:571-578`, where the decision is made before control reaches plugin code. Force `monitor_only` for `third_party` plugins. Fix `example_plugin.py`. State in the docs that `test_mode` is advisory for third-party plugins.

### Anti-Pattern 5: Shadowing allowed by default

**What people do:** let the user directory override the bundled one, "because user config usually wins."
**Why it is wrong:** the highest-value shadow target is `shopbot_plugin_amazon.py`, which inherits configured credentials (`core/credentials.py:56-58`), the saved session (`core/session_store.py:47`), and the CVV routed by hostname at `core/orchestrator.py:821-823`, all with no additional consent.
**Do this instead:** bundled wins, shadow refused with a WARNING naming both paths, rename to override. One line of code, and it removes the whole class.

### Anti-Pattern 6: Shipping an in-process "sandbox"

**What people do:** strip `__builtins__`, install import hooks, wrap `get_store()`, and describe the result as capability limiting.
**Why it is wrong:** all of it is defeated by `sys._getframe`, `gc.get_objects()`, or `ctypes` in the same interpreter. It converts an honest "we do not sandbox" into a false "we do."
**Do this instead:** ship consent, pinning, provenance, visibility, and the pre-transfer `monitor_only` control. Use `sys.addaudithook` for detection and label it detection. Defer process isolation and record the deferral as a decision.

## Integration Points

### Modified, by file and function

| Integration point | Change |
|-------------------|--------|
| `core/paths.py` (module level) | Add `bundled_plugins_dir()`, `user_plugins_dir()`, `plugin_roots()` |
| `core/registry.py:_discover_plugins` (`:19`) | Multi-root, `sorted(iterdir())`, shadow refusal, api-version gate, return `(cls, PluginOrigin)` |
| `core/registry.py:PluginRegistry.__init__` (`:80-86`) | `plugins_dir` becomes optional; per-class construction try/except at `:83`; stamp `_origin`; warn on pattern overlap |
| `core/registry.py:route` (`:115`), `_route_all` (`:148`), `platform_of` (`:127`) | Use `_domain_patterns()` at `:123`, `:140`, `:152` |
| `core/plugin_base.py` (module level, `:15`) | Add `MIN_SUPPORTED_PLUGIN_API_VERSION` |
| `core/plugin_base.py:RetailerPlugin` (class body, `:67-103`) | Add `api_version = PLUGIN_API_VERSION`; add class defaults `config = None`, `_checkout_profile = None`, `_checkout_stage = ""` |
| `core/service.py:get_analytics` (`:120`) | Drop `plugins_dir` at `:133`; call `PluginRegistry(self._cfg)` |
| `core/service.py:list_plugins` (`:143`) | Drop `plugins_dir` at `:159`; fix `domain_patterns` read at `:165-167`; add `source`, `origin_path`, `state`, `trust` |
| `core/service.py:start` (`:193`) / `run` (`:259`) | Acquire/release the run lock |
| `core/service.py` (new methods) | `is_running_anywhere()`, `plugin_install()`, `plugin_update()`, `plugin_remove()`, `plugin_search()`, `plugin_info()` |
| `core/orchestrator.py:async_main` (`:798`) | Drop `plugins_dir` at `:802` |
| `core/orchestrator.py:run_plugin` (`:322`) | `_domain_patterns()` at `:359` |
| `core/orchestrator.py:_check_and_buy` (`:529`) | Trust-aware `monitor_only` at `:571-578` |
| `core/cli/__init__.py:build_parser` (`:152-166`) | Add `install`, `update`, `remove`, `search`, `info` under the existing `plugins` group |
| `core/cli/plugins.py` | Consent prompt via the `core/cli/setup.py:51-63` idiom; new handlers; Source/State columns in `_format_plugins_table` (`:21`) |
| `plugins/example_plugin.py:99-110` | Route the place-order click through `place_order_guarded()`; stop calling `update_item_purchased` directly |
| `plugins/PLUGIN_DEV.md` section 9 (`:212-217`) | Replace "planned for a later phase" with the real policy. This seed is that phase (SEED-003:111) |
| `docs/PLUGIN_REGISTRY.md` | Becomes schema doc plus generated table |
| `pyproject.toml:9` | Declare `requests` (overlaps workstream B) |

### New

| Module | Depends on | Depended on by |
|--------|------------|----------------|
| `core/runlock.py` | `core/paths.py` | `core/service.py` |
| `core/plugin_manifest.py` | `core/paths.py` | `core/service.py:list_plugins`, `core/plugin_manager.py` |
| `core/plugin_preflight.py` | stdlib `ast` only | `core/plugin_manager.py` |
| `core/plugin_source.py` | `requests`, `core/credentials.py` (optional token) | `core/plugin_manager.py` |
| `core/plugin_manager.py` | the three above, `core/paths.py`, `core/plugin_base.py` | `core/service.py` |
| `scripts/gen_plugin_registry.py` | `pyyaml` (already a dependency) | CI only |

### External

| Service | Pattern | Gotchas |
|---------|---------|---------|
| GitHub REST `GET /repos/{owner}/{repo}/commits/{ref}` | Resolve branch/tag to a commit SHA before fetching | 60 req/hr/IP unauthenticated (verified). Handle 403 + `X-RateLimit-Remaining: 0` explicitly |
| `raw.githubusercontent.com/{owner}/{repo}/{sha}/{path}` | Fetch the file at the pinned SHA, never at a branch | Fetching at a branch defeats pinning entirely |
| `docs/registry.json` via raw or Pages | ETag-cached under `data_dir()/registry-cache.json` | Never treat registry membership as a safety verdict |

## Suggested Build Order

Ordered by dependency, not convenience. Each step names what forces it to precede the next.

**H1. Defensive reads and construction isolation.** `core/plugin_base.py` class defaults (Fix B), `core/registry.py` `_domain_patterns` (Fix A) applied at `:123`/`:140`/`:152`, per-class try/except at `:83`, `sorted(iterdir())` at `:32`, `core/orchestrator.py:359`.
*Why first:* every later step increases the number of non-conforming plugins that reach these paths. Shipping an installer on top of a `route()` that raises `AttributeError` ships the bug at scale. Also the only step that is independently valuable if all of H is cut.

**H2. Path centralisation, second root, origin reporting.** `core/paths.py`, `core/registry.py` multi-root plus shadow refusal, the three hardcoded sites, `list_plugins()` fields, CLI Source column.
*Why here:* depends on H1, because multi-root discovery is where malformed third-party plugins first arrive. Blocks everything after it, since there is nowhere to install to until a writable root exists and no way to say where a plugin came from.

**H3. API version gate.** `core/plugin_base.py` constants plus `api_version`; the gate in `core/registry.py:53-56`.
*Why here:* it lives in the same discovery loop H2 rewrites, so doing it after H2 avoids editing `_discover_plugins` twice. Must precede install, because install's static pre-flight compares against these constants.

**H4. Manifest and provenance.** `core/plugin_manifest.py`; `state` and `trust` in `list_plugins()`.
*Why here:* needs `user_plugins_dir()` and the origin field from H2 to join against. Landing before the installer means `plugins list` can already flag hand-dropped files as `unmanaged`, which is the D5 visibility mitigation, delivered before the thing that creates the risk.

**H5. Run lock and `is_running_anywhere()`.** `core/runlock.py`, `BotService.start`/`run`/`is_running_anywhere`.
*Why here:* independent of H1-H4, but must precede H6/H7. Building the installer first means shipping a `remove` that cannot tell the truth about whether it took effect, which is the exact false-safety failure D3 identifies.

**H6. Pre-flight, fetch, `install`, consent gate.** `core/plugin_preflight.py`, `core/plugin_source.py`, `core/plugin_manager.py`, CLI handler and prompt.
*Why here:* needs H3's constants, H4's manifest to write into, H5's running check to warn from. The consent prompt lands with the command it gates, never after.

**H7. `update` and `remove`.** Same modules plus CLI.
*Why here:* `update` is install-with-a-prior-record and cannot exist before install. `remove` needs the manifest to know what it is removing and the run lock to warn honestly.

**H8. Machine-readable registry.** `docs/plugin-registry.yml`, generator, CI, `plugins search` / `info`, `docs/PLUGIN_REGISTRY.md` rewrite.
*Why last:* the registry is an index into the install path, so building it first produces a catalogue with nothing to install from. Deliberately last because it is the only piece with an external hosting dependency, which makes it the safest thing to cut under pressure.

**H9. Trust documentation and disclaimer.** `SECURITY.md`, `CONTRIBUTING.md`, `plugins/PLUGIN_DEV.md` section 9, README, plus the `plugins/example_plugin.py` guard fix.
*Why:* no technical dependency, but SEED-003:39-40 is explicit that the disclaimer is "the precondition that makes thread 1 defensible." Gate the **milestone** on it, not a phase ordering. The `example_plugin.py` fix can move earlier and is cheap; it is grouped here because it is fundamentally a "what we teach authors" change.

**Deliberately not built:** hot reload; an in-process capability sandbox; a manifest-authoritative loader. Each is named as a rejected option in the anti-patterns section so the rejection is on the record rather than rediscovered.

## Open Questions

1. **Does the bundled root survive a wheel install?** `pyproject.toml:22-25` includes `plugins*` in `packages.find` and `plugins/__init__.py` exists, so the package should install, but workstream B's finding that "the built wheel contains zero data files" (`.planning/PROJECT.md:68`) means this needs verification against an actual built wheel. `bundled_plugins_dir()` derives from `_repo_root()` = `Path(core/paths.py).parent.parent` (`core/paths.py:33`), which resolves to `site-packages/` on an installed wheel; that is correct only if `site-packages/plugins/` actually contains the `.py` files. **Verify before H2 lands.** If it does not, `bundled_plugins_dir()` should use `importlib.resources` instead, and that is a workstream B dependency.
2. **`GITHUB_TOKEN` in `SECRET_KEYS` or environment-only?** `core/credentials.py:78-80` warns that widening `SECRET_KEYS` silently changes `migrate_from_env`, `EnvVarBackend.list`, and `KeyringBackend.list`. Environment-only is the lower-risk default; store-backed is the better operator experience. Needs a decision, not a guess.
3. **Audit-hook scope.** `sys.addaudithook` fires on very high-frequency events. Whether it is scoped to install-time and first-run, or always-on with a narrow event allowlist, is a tuning question that needs a measurement, not a design opinion.
4. **Where the third-party disclaimer text lives.** `SECURITY.md` section, a new `docs/PLUGIN_TRUST.md`, or both plus a first-run acknowledgement. SEED-003:57-59 suggests "documentation plus a first-run or install-time acknowledgement"; the install-time half is covered by D5, and the first-run half is an unresolved product call.
5. **Whether `plugins/example_plugin.py` belongs to workstream G or H.** It is a community-plugin-parity defect by shape (G) and a third-party-trust defect by consequence (H). Assigning it matters only for phase accounting, not for the fix.

## Sources

- Existing codebase, read directly. Every `file:line` citation above was verified against the working tree at commit `f883f13` on branch `chore/v4.0-milestone-close`. HIGH confidence.
- `.planning/seeds/SEED-003-remote-plugin-manager-and-extensibility-framework.md` (breadcrumbs re-verified: `core/registry.py:19-41`, `core/plugin_base.py:15,78-80,82,123-129,269`, `plugins/PLUGIN_DEV.md:212-217`, `docs/PLUGIN_REGISTRY.md`, `SECURITY.md:50-52`). All confirmed accurate.
- `.planning/PROJECT.md` (milestone scope, key decisions, deferred items). HIGH confidence.
- CPython `importlib` documentation, `importlib.reload` caveats: instances retain the old class definition; external references are not rebound. https://docs.python.org/3/library/importlib.html . HIGH confidence.
- GitHub REST API, "Get a commit": `GET /repos/{owner}/{repo}/commits/{ref}`, ref accepts a SHA, `heads/BRANCH`, or `tags/TAG`. https://docs.github.com/en/rest/commits/commits . HIGH confidence.
- GitHub REST API rate limits: "The primary rate limit for unauthenticated requests is 60 requests per hour." https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api . HIGH confidence.
- PEP 578 audit hooks as an observability (not isolation) primitive. MEDIUM confidence, standard-library behaviour not re-verified against a running interpreter in this pass.
- The "no supported in-process Python sandbox" conclusion rests on the removal of `rexec`/`Bastion` from the standard library and the general reachability of `sys._getframe` / `gc` / `ctypes`. HIGH confidence in the conclusion; treat any counter-proposal as requiring proof, not the reverse.

*Architecture research for: third-party plugin distribution over an existing single-process plugin framework*
*Researched: 2026-08-02*
