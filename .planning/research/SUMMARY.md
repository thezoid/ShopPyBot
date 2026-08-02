# Project Research Summary

**Project:** ShopPyBot, milestone v5.0 Real Release & Plugin Ecosystem, workstream H (SEED-003)
**Domain:** Third-party plugin distribution (install / update / remove from repos the maintainer never reviews) into an existing single-process Python bot that holds 20 secrets, encrypted retailer sessions, a checkout profile, and a live Place Order path
**Researched:** 2026-08-02
**Confidence:** HIGH for codebase claims (spot-verified, see Reconciliations), HIGH for the incident record and the no-in-process-sandbox conclusion, MEDIUM for the liability/disclaimer guidance (comparable practice, not legal advice)

## Executive Summary

Workstream H is not a framework build. `core/registry.py` already auto-discovers `shopbot_plugin_*.py`, isolates import failures, and hands every plugin the config; `RetailerPlugin` already has two abstract methods, a `PLUGIN_API_VERSION` constant, and `difficulty`/`requires_proxy`/`requires_captcha` metadata. SEED-003's own read is correct: thread 3 is mostly done. What is missing is **distribution and provenance**: nothing records where a plugin file came from, nothing pins it, nothing verifies it, and nothing distinguishes code the maintainer wrote from code a stranger wrote. That gap is the whole workstream.

The recommended approach adds zero new PyPI dependencies for the core mechanism. Fetch by 40-character commit SHA over `raw.githubusercontent.com` using the already-vendored `requests`, cross-check the git blob SHA via one Contents API call, record an independently computed SHA-256 of the exact bytes written, and store that plus the repo's **numeric owner ID** in a plaintext `installed.json` next to the file it describes, in a new user-writable root under `data_dir()`. Deliberately rejected: `git clone` (new binary dependency), `pip install git+...` (executes the target repo's build backend, a second and earlier execution surface), archive hash-pinning (GitHub does not guarantee archive byte-stability, which broke spack, easybuild, bazel, and libgit2 in 2023), Sigstore (about ten new transitive dependencies to prove publisher identity, which is the wrong question for an unvetted author), and every form of in-process sandbox.

The dominant risk is not a missing feature, it is **overclaiming**. Import is execution, and nothing in v5.0 changes that. Every in-process containment option surveyed fails: restricted builtins are escaped by object-graph traversal, RestrictedPython's own README disclaims being a sandbox, `sys.addaudithook` says "this is not sandboxing" in PEP 578, pysandbox was abandoned as "broken by design," and `rexec`/`Bastion` were removed from the stdlib for the same reason. The mitigation is to build only the controls that survive scrutiny (SHA and content-hash pinning, load-boundary integrity verification, no auto-update, a byte-level Unicode lint, default-disarmed checkout for third-party plugins, honest provenance in every listing) and to say in writing what each one does not stop. A shipped control that reads as protection and is not is the single most expensive failure available here, because the credibility was the actual control.

## Critical Reconciliations

The four researchers disagreed on three load-bearing points. Each was settled by reading the working tree, not by averaging.

### 1. Is `debug.monitor_only` an enforcement seam against third-party code?

**Verdict: partially, and the boundary is narrower than ARCHITECTURE.md claims. PITFALLS.md is right about the hole. Do not make a containment claim to users.**

Both facts are true and they are not in conflict:

- `core/orchestrator.py:571-578` reads `debug_cfg.monitor_only` and returns **before** `_try_auto_buy`, so control never transfers to `auto_buy`. ARCHITECTURE.md is correct that this is a genuine pre-transfer decision, and correct that pre-transfer is the only place enforcement can ever work in this architecture.
- `core/orchestrator.py:535` calls `plugin.check_availability(link)` unconditionally, as the **first statement** of `_check_and_buy`, long before the monitor_only read at `:571`. Monitor mode requires that. A plugin holding `self.driver` (a live, session-restored, authenticated browser) can complete an entire purchase inside `check_availability`, and monitor_only never sees it. PITFALLS.md is correct.

The honest statement, and the exact sentence the trust documentation should carry:

> Monitor-only stops ShopPyBot from asking a plugin to buy. It does not stop a plugin from buying on its own.

Consequences the roadmap must absorb:

- `debug.test_mode` is weaker still. It is honoured only inside `place_order_guarded()` (`core/plugin_base.py:151-192`), which is an opt-in concrete helper on the ABC. The orchestrator calls `plugin.auto_buy(link)` directly at `core/orchestrator.py:391`. A plugin that never calls the guard is unaffected by `test_mode` and also bypasses the BF-02 write-ahead place-order marker, so it can double-buy. `test_mode` is advisory for third-party code. Say so.
- The control that is actually worth building is not "force monitor_only for third-party plugins." It is a **per-plugin checkout-arming flag consulted at the same pre-transfer gate**, defaulting to disarmed, independent of the global `monitor_only` setting, with a separate typed opt-in to arm. That decouples "I want stock alerts for this retailer" from "I authorise a stranger's code to charge my card," which is the cheapest high-value control in the workstream. It must ship with the same "does not stop a purchase performed inside `check_availability`" sentence attached.
- PROJECT.md's v4.0 Key Decision entry ("one enforcement point honors monitor-only/`test_mode` for all 7 plugins") is true for cooperating in-tree plugins and becomes false the moment H ships. That row needs an amendment, not a deletion.

### 2. Where does the consent/trust gate belong?

**Verdict: the interactive prompt belongs in the CLI (ARCHITECTURE.md is right), and a non-interactive integrity check belongs inside `_discover_plugins` before `exec_module` (PITFALLS.md is right). These were never mutually exclusive, and shipping only the first is the failure PITFALLS.md predicts.**

Verified directly:

- **The `sys.modules` claim is correct.** `core/registry.py:44-48` does `spec_from_file_location(path.stem, path)` then `module_from_spec(spec)` then `exec_module(module)`, with no `sys.modules` assignment. A repo-wide grep of `core/` returns **zero** occurrences of `sys.modules`. Every plugin module body therefore re-executes fresh on every registry construction.
- **The construction-site count is three, not four**, but the practical point stands and PITFALLS.md's list of *surfaces* is accurate. `PluginRegistry(...)` is constructed at `core/orchestrator.py:812` (bot run), `core/service.py:134` (`get_analytics`), and `core/service.py:160` (`list_plugins`). Those three reach **four** user-facing entry points: `shoppybot plugins list`, the dashboard `GET /` (`web/routes/pages.py:26`, which offloads `list_plugins` to a thread and documents the importlib scan in its own docstring), `GET /api/analytics` (`web/routes/api.py`), and the bot run itself. Newly installed third-party code executes on the next dashboard page render, with no bot ever started.

So an install-time-only gate is genuinely bypassed by ordinary read-only usage, exactly as PITFALLS.md argues. But ARCHITECTURE.md's Anti-Pattern 1 objection is also sound and must be preserved in the wording: whoever can drop a `.py` into that directory can write `installed.json` beside it with identical permissions, so the load check is **integrity verification, not authorization**, and must never be described as the latter.

Reconciled design:

| Concern | Where it lives | What it is |
|---|---|---|
| Prompt, typed confirmation, disclosure rendering | `core/cli/plugins.py` | Interaction. Forced there by `tests/test_no_input.py` (AST-scans all of `core/`, including `core/cli/`, and fails on `input()`) and by `core/service.py:6-9` ("never prompts... secrets are collected by the front-end and passed in"). Use the `core/cli/setup.py:51-63` `print()` + `sys.stdin.readline()` idiom. |
| `ConsentRecord` acceptance and refusal-on-absence | `core/plugin_manager.py` | Policy. Refuses to write without a granted record; never asks. |
| Manifest lookup + SHA-256 recompute before `exec_module` | `core/registry.py:_discover_plugins` | Integrity. All three construction sites inherit it for free. |

Scope of the load check, which is where the two documents' concerns are actually resolved:

- **Bundled root** (repo or `site-packages`): no manifest requirement. Drop-in stays drop-in. This preserves the project's stated core value and the developer workflow.
- **User root** (`data_dir()/plugins`, manager-owned): an unmanifested file, or a managed file whose SHA-256 no longer matches, is **refused** and logged, not merely reported as `unmanaged`. It is manager-owned territory; a file nobody installed has no business executing there. Local development into the user root gets `plugins install --local <path>`, which writes both the file and the manifest entry.
- Keep ARCHITECTURE.md's `unmanaged` / `modified` **reporting** in `plugins list` and the dashboard regardless. Visibility is real and cheap.
- The hash check also closes a gap neither document scoped as urgent but which is real: all plugins run in one process with write access to that directory, so one plugin can rewrite a sibling's file between install and load.

**Resolved sub-disagreement on `--yes`.** ARCHITECTURE.md proposes a `--yes` flag recording `consent.mode = "flag"`. PITFALLS.md argues no bypass flag should exist. Adopt the PITFALLS.md position with the mechanism it names: no bare `--yes`; non-interactive install requires `--expect-sha256 <hash>` on the command line, so an automated caller has to have looked at something. Cheap, and strictly better than a habituation-friendly flag.

### 3. Reconciled build order

ARCHITECTURE.md proposed 9 steps ordered by code dependency. PITFALLS.md proposed 5 phases ordered by risk. Neither is usable as-is: ARCHITECTURE.md defers the trust-tier default until after install exists, and PITFALLS.md omits the registry hardening entirely. The reconciled order is seven phases, below in Implications for Roadmap.

**What changed from ARCHITECTURE.md's order and why:**

- Its H4 (manifest) and H5 (run lock) are merged into one phase with the load-boundary verification, because a writable second root that nothing verifies is all of the new risk with none of the new control.
- The trust-tier default (disarm third-party checkout) is pulled from its H6-adjacent position to **before** install ships. Shipping an install path in which a freshly installed stranger's plugin can buy by default, and adding the disarm afterwards, means the dangerous default exists in a released state. PITFALLS.md's "never" verdict on that shortcut is right.
- Its H9 (docs) stays last in sequence but gates **milestone** completion, per its own argument and SEED-003 line 38 ("the precondition that makes thread 1 defensible").
- The `plugins/example_plugin.py` guard fix is pulled all the way forward into phase 1 (see Cross-Workstream Findings for the assignment argument).

**What changed from PITFALLS.md's order and why:**

- A new first phase for registry hardening, absent from its plan. This is the only step independently valuable if all of H is cut, and every later step multiplies the number of non-conforming plugins reaching paths that currently raise `AttributeError`.
- Its "H1" is split three ways. Bundling the second root, the manifest, the load gate, the byte lint, the AST allowlist, and an install smoke test into one phase is a plan-sized phase, not a phase.
- `PLUGIN_API_VERSION` enforcement moves earlier and moves **out of `__init_subclass__`**. PITFALLS.md suggests `__init_subclass__` because failures there are already caught and skipped at `core/registry.py:49-51`. ARCHITECTURE.md's counter-argument wins: `__init_subclass__` fires *after* the module body has executed, so the untrusted code has already run and the check buys nothing security-wise, and it also fires for intermediate abstract bases and test doubles. Put the runtime gate in the class-collection loop at `core/registry.py:53-56`, and the pre-flight gate in an `ast.parse` static read before the file is ever written.
- The stall watchdog (its Pitfall 9) is flagged as an open scoping question rather than placed. It is a reliability control, not a distribution control.

## Key Findings

### Recommended Stack

Zero new PyPI dependencies for fetch, pin, verify, place, or index. `requests` for the fetch, stdlib `hashlib` for the trust anchor, stdlib `json` for the manifest and registry (symmetric read/write, unlike read-only `tomllib`), the already-pinned `pydantic` to validate a fetched manifest as the attacker-controlled input it is, and `core/paths.py`'s existing `platformdirs` wrapper extended with a `user_plugins_dir()` accessor that inherits the `SHOPBOT_DATA_DIR` test hook for free.

**Core technologies:**
- `requests` 2.33.1 (pinned in `requirements.txt`): fetch plugin bytes and the registry index. **Caveat: it is not declared in `pyproject.toml`, which lists only `platformdirs==4.10.0`.** See Cross-Workstream Findings.
- `hashlib` (stdlib): SHA-256 over the exact bytes written. This is the actual trust anchor, independent of GitHub.
- GitHub REST `GET /repos/{owner}/{repo}/commits/{ref}` plus `raw.githubusercontent.com/{owner}/{repo}/{40-char-sha}/{path}`: resolve then fetch, content-addressed. Never fetch at a branch. Unauthenticated limit is 60 requests per hour per IP; handle 403 with `X-RateLimit-Remaining: 0` explicitly and never silently fall back to a cached or alternate source.
- `pydantic` 2.13.3 (pinned): validate the fetched per-plugin manifest and registry entries before they touch disk or a UI, mirroring the existing `get_platform_config()` pattern from CFG-02.
- `platformdirs` 4.10.0 (pinned) via `core/paths.py`: `data_dir()/plugins` as the writable second root.
- Deliberately not used: `git` subprocess, `pip install git+...`, GitHub archive hash-pinning, `sigstore-python`, GitPython/pygit2, RestrictedPython, WASM, TOML, the `packaging` library.
- Held in reserve at zero dependency cost: Ed25519 via the already-pinned `cryptography` for maintainer-signed registry entries, if a curated tier is ever wanted. Explicitly a v2 idea.

### Expected Features

Eight ecosystem precedents were surveyed (pip/pipx, Obsidian, VS Code, HACS, lazy.nvim, Sublime Package Control, oh-my-zsh, `gh extension`). The closest structural analogue, HACS, is also the weakest trust model surveyed and is a cautionary data point rather than a template. The closest shape to what SEED-003 asks for is `gh extension install`, whose entire trust posture is a paragraph in the manual plus a first-class `--pin <tag-or-commit>` flag. **No surveyed system requires a typed confirmation**; Obsidian's Restricted-Mode-on-by-default toggle and VS Code's per-publisher click-through are the strongest precedents. Typed consent and default-on SHA pinning would exceed all eight.

**Must have (table stakes):**
- `plugins install <repo>[@ref]` with commit-SHA pinning as the default, not an opt-in flag
- `plugins list` extended with provenance (source, resolved SHA, bundled vs third-party, managed/unmanaged/modified state)
- `plugins remove <name>` and `plugins update <name>`
- Install-time consent gate surfacing the already-existing `difficulty` / `requires_proxy` / `requires_captcha` metadata **before** the file is written, which is a UX reorder rather than new data
- SECURITY.md extended with third-party-plugin-specific language

**Should have (competitive, and domain-unique):**
- A "this plugin can spend money" tier. No surveyed system manages financial transaction authority; this is genuinely specific to ShopPyBot and is the differentiator that matters most.
- Typed confirmation naming the source repo
- `plugins verify` and `plugins outdated` (reports only, never installs)
- Machine-readable registry replacing the hand-curated wiki table (REG-01, outstanding across two milestones and unlikely to ever be maintained by hand)

**Defer or reject outright:**
- Hosted marketplace, ratings, stars, install counts, telemetry: rejected, not deferred. GlassWorm faked popularity metrics; a gameable signal is worse than no signal, and this project has deliberately avoided a telemetry surface everywhere else.
- Auto-update and `update --all`: rejected. GlassWorm's own analysis names VS Code auto-update as why it spread "silently, widely, and fast," and its v2 cluster shipped sleeper packages that were benign until a later update.
- Maintainer review gate on install: rejected. It reintroduces the PR bottleneck SEED-003 exists to bypass.
- Process isolation: deferred with the reason on the record. It is the only real boundary, and PROJECT.md already lists it as post-v5.0.

### Architecture Approach

Four small new `core/` modules rather than one, and the split is functional rather than aesthetic: `plugin_manifest.py` is on the `plugins list` and dashboard render path and must not drag `requests` into it; `plugin_preflight.py` must be provably import-free so a test can assert it contains no `exec_module` / `__import__` / `eval`; `plugin_source.py` is the only module touching the network and therefore the only one needing offline-test mocking. No new top-level package, so no packaging change, which matters because workstream B is already reshaping that surface.

**Major components:**
1. `core/paths.py` (modified): sole owner of every plugin path. `bundled_plugins_dir()`, `user_plugins_dir()`, `plugin_roots()`. Removes three hardcoded `Path(__file__).parent.parent / "plugins"` sites.
2. `core/registry.py` (modified): multi-root discovery, deterministic iteration, origin tagging, reserved-domain refusal, API-version gate, defensive attribute reads, per-class construction isolation, load-boundary hash verification.
3. `core/plugin_manifest.py` (new): `installed.json` read/write/reconcile, atomically via the `tempfile.mkstemp` + `os.replace` idiom already proven in `core/credentials.py:265-281` and `core/session_store.py:61-72`. Colocated with the directory it describes so provenance dies with the files, which a SQLite row would not.
4. `core/plugin_source.py` (new): the network boundary. Parse spec, resolve ref to SHA, fetch bytes, optional token. Writes nothing, decides nothing about trust.
5. `core/plugin_preflight.py` (new): `ast.parse` only. Never imports the candidate to inspect it, because that performs the exact action consent is meant to authorise.
6. `core/plugin_manager.py` (new) and `core/runlock.py` (new): orchestration, and the cross-process "is a bot running" answer that `BotService.get_status()` cannot give today (`core/cli/status.py:6-9` documents the limitation in its own docstring).

**Precedence rule: bundled wins, shadow refused with a warning, keyed on filename stem.** Not "user wins." A user-root `shopbot_plugin_amazon.py` would inherit the configured `AMZ_EMAIL`/`AMZ_PASSWORD`, the saved `amazon.bin` session cookies, and the CVV that `core/orchestrator.py:821-823` injects by hostname, all with no additional consent. Shadowing is the highest-value move available to a hostile plugin and one line of code removes the class. The cost is that an operator patching a bundled plugin must rename the file, which is a documentation line.

**No hot reload, and write the refusal down.** Plugin instances are constructed once at `core/registry.py:83` and supervised for the life of the run; each active instance owns a live nodriver browser subprocess; CPython cannot unload the code (`importlib.reload` does not rebind existing instances). Hot reload is the most direct route to two plugin instances racing toward the same Place Order click. Every successful `install`/`update`/`remove` prints "Restart the bot for this to take effect," unconditionally.

### Critical Pitfalls

1. **Consent gates install, execution happens elsewhere.** Three registry construction sites, four entry surfaces, no `sys.modules` registration, so plugin bodies re-execute on every dashboard render. Avoid by putting the non-interactive integrity check inside `_discover_plugins` before `exec_module`. See Reconciliation 2.
2. **Pinning to a branch or tag.** tj-actions/changed-files (March 2025) had 350+ existing tags repointed at a malicious commit; 23,000+ repositories affected; SHA-pinned consumers were untouched. Avoid by storing the 40-character SHA plus an independently computed content hash, and re-consenting on either changing.
3. **The repo you vetted is not the repo you update from.** polyfill.io was sold and kept serving from the vetted URL; The Great Suspender and Nano Adblocker were sold; GitHub repojacking has four documented bypasses of namespace-retirement protection. Avoid by keying the manifest on the **numeric owner ID**, not the login string, and treating an owner-ID change as a new install requiring full re-consent.
4. **Consent fatigue.** Böhme and Köpsell (CHI 2010, 80,000 users) measured that consent rates *rise* the more a dialog resembles a EULA. Chrome SSL interstitial telemetry shows roughly half of clickthroughs in 1.7 seconds or less. Avoid by typing the plugin name rather than `y`, showing four to six lines of concrete facts rather than prose, prompting once per install and once per changed update, and shipping no bypass flag.
5. **Sandboxing theatre.** The most likely failure for this team, because an in-process sandbox is easy to build and demos well. Every option is upstream-disclaimed. Avoid by building only controls that survive scrutiny and attaching a written "what this does not stop" sentence to each.
6. **Invisible-Unicode payloads.** GlassWorm (Oct 2025 to Apr 2026) hid logic in variation selectors and Private Use Area characters, rendering as blank space in editors and in GitHub diffs while executing normally. A byte-level lint refusing non-printable codepoints, bidi overrides, variation selectors, and PUA characters outside strings and comments is roughly 30 lines and is the highest value-per-line control in the workstream.
7. **Removal is not revocation.** Nothing rotates after a bad plugin runs. Session cookies grant account access without the password, so a password reset alone does not close it. `plugins remove` must print a rotation checklist, and the commands it references must exist.

## Implications for Roadmap

Seven phases. The roadmap assigns numbers; v5.0 continues from Phase 35. The ordering invariant is: **nothing that can install third-party code ships until the disarm default and the load-boundary verification are already in place.**

### H1: Registry hardening and the guard the template teaches
**Rationale:** The only phase independently valuable if all of H is cut, and a hard prerequisite for everything after it. Every later phase multiplies the number of non-conforming plugins reaching paths that currently raise. Verified crash sites: `core/registry.py:123` and `:152` (`plugin.domain_patterns` unguarded, reachable from bot startup), `core/registry.py:140-142` and `core/service.py:165-167` (the `getattr(..., [])` fallback is dead code because the `isinstance` on the preceding line raises first, crashing the dashboard render and `plugins list`), `core/orchestrator.py:359` (crashes `run_plugin`, which the supervisor treats as a plugin crash and backoff-restarts forever), and `core/registry.py:83` (`[cls(config) for cls in plugin_classes]` is a bare list comprehension, so a third-party `__init__` that raises takes down bot start, the dashboard, and `/api/analytics`; import failure is isolated at `:43-51` but construction is not).
**Delivers:** One defensive `_domain_patterns()` reader used at all five sites, fail-safe semantics (a plugin that cannot say what it handles handles nothing) with a single discovery-time warning rather than a warning in the per-item hot loop; class-attribute defaults `config = None`, `_checkout_profile = None`, `_checkout_stage = ""` on `RetailerPlugin`, which fixes five orchestrator sites without touching the orchestrator; per-class construction try/except; `sorted(iterdir())`; deterministic `_active_plugins` ordering (see Cross-Workstream Findings); `plugins/example_plugin.py` routed through `place_order_guarded()`.
**Avoids:** Pitfalls 6 (partially, the non-determinism half) and 8 (the template teaching the bypass).
**Research flag:** none. Read-the-code work with exact line numbers already established.

### H2: Path centralisation, second root, precedence, API version gate
**Rationale:** Depends on H1 because multi-root discovery is where malformed third-party plugins first arrive. Blocks everything after it: there is nowhere to install to until a writable root exists, and no way to say where a plugin came from. The version gate is folded in here because it lives in the same discovery loop, and doing it separately means editing `_discover_plugins` twice.
**Delivers:** `bundled_plugins_dir()` / `user_plugins_dir()` / `plugin_roots()`; `PluginRegistry.__init__` takes `plugins_dir` as optional (roughly fifteen test call sites pass `plugins_dir=tmp_path`, so the parameter cannot simply be deleted); the three hardcoded paths removed; `PluginOrigin` stamped onto instances via the established `assign_proxy`/`assign_solver` idiom; bundled-wins shadow refusal; **reserved-domain refusal** (a third-party plugin claiming a bundled domain is refused at load, hard, not warned, because the user cannot adjudicate it at runtime); `MIN_SUPPORTED_PLUGIN_API_VERSION` as data plus the runtime gate at `core/registry.py:53-56` with a soft-fail on older-but-supported versions; Source column in `plugins list` and the dashboard, which inherits it for free.
**Uses:** `platformdirs` via the existing `core/paths.py` wrapper.
**Avoids:** Pitfalls 6 (shadowing), 10 (package-internal directory), 16 (version skew).
**Research flag:** **YES.** Blocked on a factual question workstream B must answer first, see Gaps.

### H3: Provenance manifest, load-boundary verification, run lock
**Rationale:** Needs H2's writable root and origin field to join against. Landing before the installer means `plugins list` can already flag hand-dropped files, so the visibility mitigation exists before the thing that creates the risk. The run lock is folded in because it is small, independent, and must precede `remove`; building the installer first ships a `remove` that cannot tell the truth about whether it took effect.
**Delivers:** `installed.json` at `user_plugins_dir()`, atomic-write, plaintext (no secrets, so a text editor answers "where did this come from" when the app will not start), recording stem, source kind and URL, ref, resolved 40-char SHA, **numeric owner ID**, remote path, `content_sha256`, installed timestamp, declared API version, consent record (granted, at, mode, prompt version, source shown), disclaimer text version, trust tier, and schema version; SHA-256 recompute inside `_discover_plugins` before `exec_module`, refusing unmanifested and drifted files in the **user root only**; `unmanaged`/`modified` reporting everywhere; `core/runlock.py` over `data_dir()/run.lock` with advisory-only staleness.
**Avoids:** Pitfalls 1, 2, 3, 5, 10.
**Research flag:** none. Both the atomic-write and sidecar-state patterns already exist in this repo twice each.

### H4: Trust-tier enforcement and capability reduction
**Rationale:** Must ship **before** install exists, so no released state has a default in which a freshly installed stranger's plugin can buy. Depends on H3's `trust` field. Coordinate with workstream G, which is building a `monitor_only` entry guard for the community plugins; these must be one mechanism, not two that can diverge.
**Delivers:** Per-plugin checkout arming consulted at the `core/orchestrator.py:571` pre-transfer gate, defaulting to disarmed for `third_party` regardless of the global `monitor_only`, with a separate typed `plugins trust-checkout <name>` to arm; a scoped per-platform credential accessor so `get_store()` is not the process-global import target it is today (`core/credentials.py:310-320` yields all 20 `SECRET_KEYS` in two lines); a regression test that third-party plugins never receive `_cvv` (true today only by accident, because `core/orchestrator.py:817-823` hardcodes `bestbuy.com` and `amazon.com`).
**Avoids:** Pitfalls 7 and 8.
**Research flag:** none for the arming flag. The scoped-accessor refactor is a design call, not a research question, and its honest framing is "removes the lazy and accidental paths, makes a direct `core.credentials` import a bright greppable signal, does not stop a determined attacker."

### H5: Fetch, pre-flight, install, consent gate
**Rationale:** Needs H2's constants, H3's manifest to write into and run lock to warn from, and H4's disarm default to be already true. The consent prompt lands with the command it gates, never after.
**Delivers:** `core/plugin_source.py` (resolve ref to SHA, fetch at the SHA, owner-ID capture, rate-limit handling); `core/plugin_preflight.py` (`ast.parse` only: parses at all, contains a `RetailerPlugin` subclass, declared `api_version`, statically visible `domain_patterns`, import disclosure); the byte-level Unicode lint as a **refusal**, not a warning; the import allowlist enforcing the no-dependencies decision; `core/plugin_manager.py` refusing to write without a granted `ConsentRecord`; the CLI prompt, four to six lines, facts not prose, leading with `github.com/<owner>/<repo>` and the owner ID rather than the friendly name, requiring the plugin name typed back; `--expect-sha256` for non-interactive use and no bare `--yes`.
**Uses:** `requests`, `hashlib`, `pydantic`, `ast`.
**Avoids:** Pitfalls 4, 5, 14, 15.
**Research flag:** **YES.** The prompt copy is an acceptance criterion, not an implementation detail, and the consent-fatigue evidence should be re-read when it is written.

### H6: `update`, `remove`, `verify`, `outdated`
**Rationale:** `update` is install-with-a-prior-record and cannot exist before install. `remove` needs the manifest to know what it is removing and the run lock to warn honestly.
**Delivers:** `update` re-consenting on any SHA change, showing what changed, and treating an **owner-ID change or a capability escalation as a new install** rather than an update; `outdated` that reports and can never install; no scheduler, timer, or startup hook anywhere near the update path; `verify` re-checking every managed file against its recorded hash; staged-mutation semantics with running-state detection, `remove` refusing by default while a run lock is held and refusing outright while a place-order marker is set; and `remove` printing the **rotation checklist** rather than "Removed."
**Avoids:** Pitfalls 3, 10, 11, 17.
**Research flag:** none.

### H7: Trust documentation, registry, and the vocabulary guard
**Rationale:** No technical dependency, but SEED-003 line 38 is explicit that the disclaimer is "the precondition that makes thread 1 defensible." Gate the **milestone** on this phase, not the phase ordering. The registry is deliberately last because it is the only piece with an external hosting dependency, which makes it the safest thing to cut under pressure, and because a catalogue built before the install path is a catalogue with nothing to install from.
**Delivers:** Two artifacts, not one: a short blunt operational warning at the point of decision (in the prompt and next to every third-party row in `plugins list`), and the formal liability language in SECURITY.md, README, and the LICENSE workstream C is adding; a SECURITY.md amendment stating plainly that the per-platform risk assessment at `SECURITY.md:50-52` applies to **merged** plugins only, that third-party installs receive no review of any kind, and that no revocation mechanism exists; `plugins/PLUGIN_DEV.md` section 9 replacing "planned for a later phase" with the real policy (SEED-003 line 111: this seed is that phase); a CI vocabulary guard alongside the existing credential-leak check; `docs/plugin-registry.yml` as the in-repo source of truth with a CI-generated `registry.json` and markdown table, retiring the never-maintained wiki page; a `[ext:*]` log tag and an issue-template checkbox for third-party reproduction.
**Avoids:** Pitfalls 12, 13, 15, 16.
**Research flag:** none for the engineering. The liability wording carries a MEDIUM confidence flag and is not legal advice.

### Phase Ordering Rationale

- **Hardening precedes exposure.** H1 exists because the installer would otherwise ship a `route()` that raises `AttributeError` at ecosystem scale.
- **The writable root and the thing that verifies it ship together** (H2 then immediately H3). Splitting them further would ship the risk before the control.
- **The dangerous default never exists in a released state.** H4 precedes H5 for exactly one reason, and it is the reason PITFALLS.md marks "third-party plugins can buy by default" as a **never**-acceptable shortcut.
- **Interaction and enforcement live in different modules** because `tests/test_no_input.py` and `core/service.py:6-9` both force it, and because the prompt fires once while the check fires on every registry construction.
- **The externally-dependent piece is last** so it is the cuttable one.

### Research Flags

Phases likely needing `--research-phase` during planning:
- **H2:** blocked on whether `bundled_plugins_dir()` resolves correctly on a wheel install. Factual, and it is a workstream B dependency.
- **H5:** the consent prompt copy is an acceptance criterion backed by measured consent-fatigue research; it deserves a deliberate pass rather than being written inline.

Phases with standard patterns (skip research):
- **H1:** every fix has an exact file and line already verified.
- **H3:** atomic write and sidecar state both have two working precedents in this repo.
- **H4, H6:** design calls, not research questions.
- **H7:** engineering is mechanical; the wording carries its own confidence caveat.

## Cross-Workstream Findings

Four findings that belong to workstreams other than H. Collected so they are not lost when H is planned.

### 1. Non-deterministic domain-shadow routing (workstream G), verified, a live bug today

`PluginRegistry.setup_for_items` builds `needed: set[RetailerPlugin] = set()` at `core/registry.py:182` and then appends to `_active_plugins` by iterating that set at `:188`. Set iteration order over objects follows `id()`-derived hashes, so `_active_plugins` order varies between runs on the same machine. `route()` at `:122-125` returns the **first** match. With two plugins whose `domain_patterns` overlap, **which one wins is non-deterministic across runs**. Note that `plugins_for_items` at `:163-170` already does this correctly, with a list plus an id-keyed `seen` set preserving first-seen order; `setup_for_items` simply does not. This is independent of workstream H and exists today with the 7 bundled plugins. It is a safety-relevant routing bug in a component that spends money, and workstream G is already touching this area. Fix: order-preserving dedup in `setup_for_items`, plus bundled-before-third-party sort once H2 lands.

### 2. `plugins_dir` resolves inside `site-packages` on a wheel install (workstream B), dependency, flag it

All three production sites compute `Path(__file__).parent.parent / "plugins"` (`core/orchestrator.py:802`, `core/service.py:133`, `:159`), and `core/paths.py:29-33` `_repo_root()` does the same. On an installed wheel these resolve to `site-packages/`. Two distinct consequences, and they should not be conflated:

- **Discovery probably works.** `pyproject.toml` `[tool.setuptools.packages.find]` includes `plugins*`, and the plugin files are `.py` modules rather than data files, so they should ship. Workstream B's "the built wheel contains zero data files" finding is about templates, static assets, and sounds. **Still verify against an actual built wheel before H2 lands.** If it fails, `bundled_plugins_dir()` must use `importlib.resources`, which is squarely a workstream B change.
- **Installing there is wrong regardless.** Writing third-party files into `site-packages` needs elevation on some systems, is wiped by `pip install --upgrade`, pollutes the wheel's file list, and mixes trusted with untrusted files in one namespace. This is why H2's second root is a correctness fix and not tidiness.

**Additional workstream B dependency, and this one is not in either research file's dependency list:** `pyproject.toml` declares `dependencies = ["platformdirs==4.10.0"]` and nothing else. `requests` is pinned in `requirements.txt` but is **not** a declared package dependency. Workstream H's fetch path needs it, so B's "truthful dependency declaration" work must include `requests` or H ships a manager that raises `ModuleNotFoundError` on any non-editable install.

### 3. Plugin name reaches notification surfaces unescaped (workstream D)

`_build_event` at `core/orchestrator.py:193-202` sets `platform=plugin.__class__.__name__`, which becomes attacker-controlled the moment third-party plugins can be installed. That value flows into a Discord embed field value (`notifications/discord_notifier.py:33`), an email body (`notifications/email_notifier.py:32`), and an SMS body (`notifications/sms_notifier.py:34`), with no escaping and no length cap anywhere. Workstream D is already fixing empty-`url` embeds on `plugin_parked` and `health_degraded`, which is the same surface and the same code path (`core/orchestrator.py:88` dispatches `plugin_parked` with the class name and empty name/link). Fold escaping and a length cap into that fix rather than opening a second pass over the notifier.

### 4. `plugins/example_plugin.py` teaching the bypass, assign to H, phase H1

Verified: lines 99-103 select and click `#place-order` directly, and line 110 calls `update_item_purchased(url)`. It never calls `place_order_guarded()`, so the canonical template that `plugins/PLUGIN_DEV.md` instructs authors to copy teaches both the `test_mode` bypass and the BF-02 double-buy-marker bypass.

**Assign to H, not G,** for two reasons. First, scope: workstream G is BF-02 marker propagation to the five **shipped community plugins**, a defect in retailer code the maintainer owns and ships. `example_plugin.py` is not a retailer plugin and never runs against a real store; it is documentation in executable form, and its entire consequence is what third-party authors copy, which is H's subject. Second, timing: it belongs in H1, the earliest phase, and it is roughly a five-line change. It is a prerequisite for promoting the project as third-party extensible, so it should not wait behind G's per-plugin work. If phase accounting makes a G assignment more convenient, the fix is identical either way; what matters is that it lands in the first phase of whichever workstream takes it.

## Decisions to Record in PROJECT.md Key Decisions

These are deliberate trades. Record them as decisions, not omissions, per SEED-003 lines 84-85 ("a decision on the record, not a default that happens because nobody raised it").

| Decision | Rationale | Status |
|---|---|---|
| **Plugin-declared dependencies are not supported in v5.0** | STACK.md proposed `pip install --target --no-deps` into a plugin-private vendor dir. Rejected. `--no-deps` does not prevent `pip` from executing a source distribution's `setup.py` during resolution, with full user privileges, before anything is installed. That is a second, earlier execution channel in a workstream whose entire premise is that execution cannot be contained. Shai-Hulud propagated through exactly this surface in npm. A plugin may import the stdlib plus what ShopPyBot already depends on; anything else fails to load with a message naming the missing module, and the user installs it deliberately, outside the tool. If it is ever added, the minimum is `--only-binary=:all:` plus `--require-hashes` plus `--no-deps` with a fully pinned hash list. | Chosen (constrains plugin authors, deliberately) |
| **Disclaimer plus consent plus SHA/content pinning, explicitly not a sandbox** | This is the deliberate stopping point SEED-003 asks the design to choose. No in-process Python sandbox exists: PEP 578 says audit hooks are "not sandboxing," RestrictedPython's README disclaims being one, pysandbox was abandoned as "broken by design," `rexec` and `Bastion` were removed from the stdlib. Process isolation is the only real boundary and stays a post-v5.0 candidate. The deferral is correct **provided v5.0 never describes anything shipped in its place as isolation.** | Chosen (with an explicit non-overclaim condition) |
| **`monitor_only` is not a containment boundary for third-party plugins** | Verified: `check_availability` runs unconditionally at `core/orchestrator.py:535`, before the monitor_only read at `:571`. Monitor mode stops ShopPyBot asking a plugin to buy; it does not stop a plugin buying on its own. `test_mode` is weaker still, being honoured only inside the opt-in `place_order_guarded()`. Amends the v4.0 "one enforcement point for all 7 plugins" entry, which remains true for in-tree plugins. | Recorded (amends a prior decision) |
| **Third-party plugins ship disarmed for checkout by default** | Decouples "I want stock alerts for this retailer" from "I authorise a stranger's code to charge my card." Requires a separate typed opt-in, independent of the global `monitor_only`. | Chosen |
| **Bundled plugins win a filename or domain collision; shadowing is refused** | A shadowing `shopbot_plugin_amazon.py` would inherit configured credentials, saved session cookies, and the hostname-routed CVV with no additional consent. One line of code removes the whole class. Cost: renaming to override a bundled plugin. | Chosen |
| **GitHub-only fetch for v1** | Matches REG-01's existing GitHub-native registry and this repo's own GitHub-native tooling. Generic Git-host support is the point at which a `git` subprocess becomes unavoidable, which is a new environmental precondition on a user base that is not guaranteed to have a dev toolchain. Explicitly deferred, not silently unsupported. | Chosen |
| **No auto-update, no `update --all`, no scheduled path into the update code** | Auto-update converts every trust-transfer incident from catchable to overnight, on a machine holding an encrypted credential store and a live checkout path. GlassWorm's stated spread mechanism. | Chosen |
| **No hot reload after install, update, or remove** | Non-unloadable modules plus live browser subprocesses plus supervised restart logic; the likely outcome is two instances racing toward the same Place Order click. Restart is required and every mutation says so. | Chosen (rejection recorded so it is not re-proposed) |
| **The install manifest informs discovery; it does not authorise** | Whoever can drop a `.py` into the directory can write `installed.json` beside it. The load-boundary check is integrity verification against tampering, drift, and unreviewed drops, not a control against a local attacker. Refusing unmanifested files in the manager-owned user root is still worth doing; describing it as a security boundary is not. | Chosen (framing is the requirement) |
| **The registry is a discovery index, never a trust root** | A maintainer-curated list anyone can open a PR against is not a security boundary. Being listed reads as endorsement no matter what a footer says, so every row carries an unmissable "third-party, not reviewed by this project" column and no install counts or ratings. | Chosen |

## REVIEW.md Criteria (carried forward)

PROJECT.md already flags H for a post-verification REVIEW.md deep pass. That review gets two explicit, non-negotiable criteria:

- **(a)** For every shipped control, one sentence in REVIEW.md naming what it does not stop.
- **(b)** Confirmation that no shipped artifact (code, docstrings, variable names, docs, CLI help, release notes, the registry table) uses "sandbox", "isolated", "curated", "verified", or "safe" about third-party plugins. Wire it as a CI guard alongside the existing credential-leak check, so it is mechanical and durable rather than a one-time grep.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Version claims verified against PyPI JSON metadata; the GitHub archive-instability claim verified against GitHub's own blog post plus LWN plus four downstream project issues. One correction applied: `requests` is in `requirements.txt` but not `pyproject.toml`. One recommendation overridden: plugin dependency installation, see Decisions. |
| Features | MEDIUM-HIGH | Mechanism confirmed via official docs for seven of eight surveyed systems; VS Code's trust-dialog copy could not be sourced verbatim (mechanism HIGH, wording LOW). Two "no disclaimer found" results for HACS and Sublime are searched absences, which is a finding rather than a gap. |
| Architecture | HIGH | Every code claim carries a `file:line`. Five were independently re-verified in this synthesis (`_check_and_buy` ordering, `sys.modules` absence, construction-site count, `example_plugin.py:99-110`, `_repo_root()` resolution) and all five held, with one count correction. |
| Pitfalls | HIGH for incidents and codebase claims, MEDIUM for liability | Every incident is multiply sourced; every codebase claim traces to a verified line. The disclaimer section is drawn from comparable practice and consent research, is not legal advice, and has not been reviewed by a lawyer. |

**Overall confidence:** HIGH for what to build and in what order. MEDIUM for the exact disclaimer wording, which is the one place a non-engineering review would add value.

### Gaps to Address

1. **Does the bundled root survive a wheel install?** `plugins*` is in `packages.find`, so the `.py` files should ship, but workstream B found the wheel missing every data file and that finding has not been re-scoped against plugin modules specifically. **Must be verified against an actual built wheel before H2 lands.** If it fails, `bundled_plugins_dir()` uses `importlib.resources` and it becomes a workstream B change.
2. **`GITHUB_TOKEN` in `SECRET_KEYS` or environment-only?** `core/credentials.py:78-80` warns that widening `SECRET_KEYS` silently changes `migrate_from_env`, `EnvVarBackend.list`, and `KeyringBackend.list`. Environment-only is lower risk; store-backed is the better operator experience. Needs a decision in **H5**, not a guess.
3. **Ship a `sys.addaudithook` detection layer at all, and if so at what scope?** It fires on very high-frequency events and would dominate log volume if always-on. Install-time and first-run only, a narrow event allowlist, or not at all. Needs a measurement, not a design opinion. **H4 or H5.** Whatever ships is labelled detection and forensics, never prevention.
4. **Where the third-party disclaimer text lives, and whether a first-run acknowledgement exists.** SECURITY.md section, a new `docs/PLUGIN_TRUST.md`, or both. SEED-003 lines 57-59 suggest "documentation plus a first-run or install-time acknowledgement"; the install-time half is covered by H5, the first-run half is an unresolved product call. **H7.**
5. **Is the event-loop stall watchdog in workstream H at all?** PITFALLS.md places it in its H3, but it is a reliability control rather than a distribution control, `asyncio.timeout` at `core/orchestrator.py:369` cannot preempt a blocking plugin regardless of where the plugin came from, and the exposure exists today with the 7 bundled plugins. Decide during roadmapping whether it belongs to H, to G, or to a deferred reliability item. Do not let it silently expand H's scope.
6. **The install-time import smoke test.** PITFALLS.md proposes running `exec_module` in a bounded subprocess at install as a stall smoke test. That means **executing the plugin as part of installing it**, which sits awkwardly against the "never import to inspect" rule the same research establishes. If it ships, it must run strictly after consent is granted, never before, and that ordering is an acceptance criterion. **H5.**
7. **Coordination boundary between H4 and workstream G's `monitor_only` entry guard.** Both build a pre-transfer gate at the same orchestrator site. They must be one mechanism. PROJECT.md already flags G and H for a shared post-verification review; this is the specific thing that review checks.

## Sources

### Primary (HIGH confidence)

- This repository, read directly at commit `f883f13` on `chore/v4.0-milestone-close`: `core/registry.py`, `core/orchestrator.py` (`:193-202`, `:322-379`, `:529-606`), `core/service.py` (`:120-175`), `core/paths.py`, `core/plugin_base.py`, `core/credentials.py`, `core/session_store.py`, `core/checkout_profile.py`, `core/cli/plugins.py`, `core/cli/status.py`, `web/routes/pages.py`, `web/routes/api.py`, `plugins/example_plugin.py`, `plugins/PLUGIN_DEV.md`, `notifications/discord_notifier.py`, `notifications/email_notifier.py`, `notifications/sms_notifier.py`, `pyproject.toml`, `requirements.txt`, `SECURITY.md`, `docs/PLUGIN_REGISTRY.md`, `tests/test_no_input.py`
- `.planning/seeds/SEED-003-remote-plugin-manager-and-extensibility-framework.md` and `.planning/PROJECT.md`
- GitHub REST: Contents API, Get-a-commit, blobs, rate limits (60 requests/hour unauthenticated)
- GitHub Engineering blog and LWN on source-archive checksum instability, corroborated by spack#5411, easybuild-easyconfigs#5151, bazel#3722, libgit2#4343
- PEP 578 ("This is not sandboxing"), CPython `sys.addaudithook` docs, cpython#87604, PEP 684 discussion on subinterpreter isolation limits
- Victor Stinner on pysandbox being "broken by design" (python-dev Nov 2013) and LWN's coverage; RestrictedPython README
- CPython `importlib` reload caveats (instances retain the old class definition)
- PyPI JSON metadata for `requests`, `cryptography`, `platformdirs`, `sigstore` (transitive dependency count)
- pip `--target`, `--only-binary`, `--require-hashes` documentation
- Supply-chain incident record, each multiply sourced: event-stream, PyPI `ctx`, polyfill.io, tj-actions/changed-files, xz-utils CVE-2024-3094, Shai-Hulud, Fractureiser, GlassWorm, The Great Suspender, Nano Adblocker, HACS/Home Assistant disclosures, GitHub repojacking (Checkmarx)

### Secondary (MEDIUM-HIGH confidence)

- Ecosystem precedent docs: pip VCS support, pipx, Obsidian community plugins and plugin security, VS Code Marketplace / extension runtime security / Workspace Trust, HACS publish requirements, lazy.nvim lockfile, Sublime Package Control, `gh extension install` manual
- HACS `hacs.json` and Obsidian `manifest.json` / `community-plugins.json` as the two-tier registry precedent
- Böhme and Köpsell, *Trained to Accept? A Field Experiment on Consent Dialogs*, CHI 2010 (80,000 users)
- home-assistant/core#169994 (custom integrations shadowing built-ins described as "a feature, not a bug")

### Tertiary (LOW confidence, needs validation)

- VS Code's per-publisher trust dialog copy: mechanism confirmed, exact wording not sourceable from official docs
- Chrome SSL interstitial clickthrough telemetry (~50% in 1.7s or less), cited across the warning-fatigue literature rather than from a primary dataset
- oh-my-zsh third-party plugin norms: community-sourced, not project-enforced language
- The per-plugin `sys.path` scoping design in STACK.md section 6: a reasoned application of `pip --target`, not an independently verified pattern, and moot given the no-dependencies decision

*Research completed: 2026-08-02*
*Ready for roadmap: yes*
