# Requirements: ShopPyBot v5.0 Real Release & Plugin Ecosystem

**Defined:** 2026-08-02
**Core Value:** A drop-in plugin framework that lets the community add new retail platform integrations by placing a single Python file in `plugins/`, with no core changes required.

**Basis:** A 221-finding full-repo sweep (open PRs, security and quality scans, outstanding UAT debt, seed gaps, defect re-verification) plus an adversarial completeness pass, plus four researchers and a synthesis pass scoped to workstream H. Every requirement below traces to evidence in that sweep or in `.planning/research/`.

## v1 Requirements

### A. Mainline Reconciliation (MAIN)

`master` is 263 commits behind. Every v4.1 and v4.2 artifact exists only on `chore/v4.0-milestone-close`. Nothing else in this milestone is durable until the default branch is real.

- [ ] **MAIN-01**: The branch's `ci.yml` compiles, so the v4.1+v4.2 test suite runs in CI for the first time (`SHOPBOT_DATA_DIR: ${{ runner.temp }}/shopbot` currently sits in job-level `env:` where the `runner` context does not exist, producing 0-job failures)
- [ ] **MAIN-02**: PR #11's two conflicts (`.github/dependabot.yml` add/add, `requirements.txt` content) are resolved without dropping `httpx==0.28.1`
- [ ] **MAIN-03**: The 4 local commits present on the working branch but absent from PR #11's head are triaged and deliberately included or excluded, not swept in as a side effect of conflict resolution
- [ ] **MAIN-04**: PR #11 is merged, so `gitleaks.yml`, `release-please.yml`, and every v4.1/v4.2 artifact exist on the default branch
- [ ] **MAIN-05**: PR #12 (signal handlers registered off the main thread) is merged
- [ ] **MAIN-06**: Stale PR #8 is closed rather than merged (open since 2023, conflicting, superseded because master already carries urllib3 2.7.0)
- [ ] **MAIN-07**: Dependabot PRs #15 through #20 are merged in a conflict-safe order, accounting for #19 and #20 colliding in `ci.yml`

### B. Distributable Artifact (PKG)

The built wheel does not run. This is the precondition for release-please being worth anything.

- [ ] **PKG-01**: An installed wheel contains `web/static/*`, `web/templates/*`, and `sounds/*`, so `create_app()` does not raise `RuntimeError` on the `StaticFiles` mount
- [ ] **PKG-02**: `pyproject.toml` declares every actual runtime dependency, not just `platformdirs==4.10.0`
- [ ] **PKG-03**: `websockets`, `starlette`, `httpx`, and `requests` are each declared in the correct place (all four are imported or required today and none is declared where it is used)
- [ ] **PKG-04**: Dead `selenium` and `webdriver-manager` pins are removed from `requirements.txt`, which also removes a recurring Dependabot noise source
- [ ] **PKG-05**: A CI job installs the built wheel into a clean environment and asserts that `shoppybot web` starts and a sound file resolves
- [ ] **PKG-06**: `bundled_plugins_dir()` is verified to resolve correctly from an installed wheel (blocks EXT-03; if it fails, the fix is `importlib.resources` and belongs to this workstream)

### C. Public-Repo Readiness (PUB)

- [ ] **PUB-01**: A LICENSE file exists, so the public repo carries an actual license grant
- [ ] **PUB-02**: `_deprecated/` (roughly 800 lines documenting a retired `settings.json` config format) is removed from the default branch
- [ ] **PUB-03**: README's Prerequisites and Setup sections describe nodriver, not Selenium and `chromedriver` and `selenium.driver_path`
- [ ] **PUB-04**: `sample.config.yml` covers every section `AppConfig` declares, including `debug.monitor_only`, and no longer advertises `available.short_url` or `available.alert_type`, which nothing reads
- [ ] **PUB-05**: A CODEOWNERS file exists so code-owner review can be required
- [ ] **PUB-06**: CLAUDE.md describes the current architecture rather than the retired v1 one
- [ ] **PUB-07**: SECURITY.md no longer carries the stale "Operator note: PVR must be enabled" blockquote (it is enabled)
- [ ] **PUB-08**: Documented drift is corrected: dashboard section count, `python main.py` named as the web launcher, hardcoded banner hex values, cold-load theme default, MC-3's polling description, and `docs/PLUGIN_REGISTRY.md`'s difficulty value for AmazonPlugin
- [ ] **PUB-09**: SEED-001's destructive history rewrite is formally retired as a recorded decision, on the evidence that gitleaks across 964 commits found exactly one test-fixture false positive

### D. Live Defect Closure (FIX)

- [ ] **FIX-01**: `POST /api/bot/start` reports a real failure instead of returning 200 unconditionally when the bot loop dies
- [ ] **FIX-02**: The stdin listener thread does not busy-spin at EOF, and does not force-fire every manual-intervention gate in a headless or dashboard-driven run
- [ ] **FIX-03**: A stdin listener failure surfaces rather than dying silently when `sys.stdin` is None
- [ ] **FIX-04**: The blocking stdin readline no longer occupies the default executor and stalls `asyncio.run()` teardown for up to 300 seconds
- [ ] **FIX-05**: `POST /api/config` either applies to the running process or reports that it did not, so `test_mode` cannot silently remain at its old value
- [ ] **FIX-06**: `plugin_parked` and `health_degraded` notifications are actually delivered (both currently build a Discord embed with an empty `url`, which the API rejects, so the two alerts that exist only for unattended operation are the two that never arrive)
- [ ] **FIX-07**: The notification `action` vocabulary is documented for all six values it emits, and a parked plugin is visually distinguishable from a successful purchase
- [ ] **FIX-08**: The plugin name is escaped and length-capped before reaching Discord, email, and SMS bodies (attacker-controlled once EXT ships)
- [ ] **FIX-09**: A host without Chrome produces an actionable message rather than every plugin failing silently while the dashboard reports the bot as started
- [ ] **FIX-10**: The Confirmed Orders view refreshes rather than being fetched exactly once per page load
- [ ] **FIX-11**: `test_post_config_allowlisted_key` patches the correct module path and actually asserts the write it claims to test

### E. Scanning to Zero (SCAN)

Depends on A: several of these live on workflows that are not on master yet.

- [ ] **SCAN-01**: All 7 open Dependabot alerts are closed
- [ ] **SCAN-02**: The two high-severity clear-text logging and storage CodeQL alerts in `logger.py` are resolved
- [ ] **SCAN-03**: The 3 production `py/incomplete-url-substring-sanitization` alerts are resolved
- [ ] **SCAN-04**: The 19 test-file url-sanitization alerts are dismissed or suppressed deliberately, so the queue reflects real findings
- [ ] **SCAN-05**: `ci.yml` carries an explicit `permissions` block (CodeQL alert #30)
- [ ] **SCAN-06**: The `disabled_manually` `codeql-analysis.yml` is removed from master, since default setup replaced it
- [ ] **SCAN-07**: gitleaks is a required status check on master
- [ ] **SCAN-08**: Branch protection on master requires at least one review and applies to admins
- [ ] **SCAN-09**: Secret scanning non-provider patterns and validity checks are enabled
- [ ] **SCAN-10**: The 17-month-stale `origin/dev` branch and its 4 rotted workflows are resolved
- [ ] **SCAN-11**: Third-party actions are pinned by commit SHA rather than floating major tags

### F. Quality Floor (QUAL)

No linter, formatter, or typechecker is configured anywhere, so CLAUDE.md's own code standards are entirely unenforced.

- [ ] **QUAL-01**: A linter and formatter are adopted, configured, and enforced in CI
- [ ] **QUAL-02**: Type checking is adopted and enforced in CI
- [ ] **QUAL-03**: Findings from QUAL-01 and QUAL-02 are fixed, or explicitly baselined with the baseline recorded
- [ ] **QUAL-04**: Test coverage is measured in CI
- [ ] **QUAL-05**: The 11 `except Exception: pass` sites either handle or propagate, with no silent swallowing
- [ ] **QUAL-06**: Dead `amazon_bot.py` and `bestbuy_bot.py` are removed
- [ ] **QUAL-07**: The two tests that skip silently when `config.yml` is absent (one of them a plaintext-secrets security check) fail loudly instead
- [ ] **QUAL-08**: The cross-test mock leak producing a never-awaited coroutine warning is fixed
- [ ] **QUAL-09**: The 9 files over 300 lines and 71 functions over 30 lines are either reduced or explicitly accepted with recorded rationale

### G. Community Plugin Parity (PAR)

- [ ] **PAR-01**: All 5 community plugins pass `order_marker_link` to `place_order_guarded`, closing the residual double-buy exposure BF-02 was created to close
- [ ] **PAR-02**: Community plugins have per-step timeouts, so a hung selector cannot block the plugin loop indefinitely
- [ ] **PAR-03**: Community plugins have the `monitor_only` entry guard, implemented as one mechanism with EXT-09 rather than two that can diverge
- [ ] **PAR-04**: Community plugins set `_last_tab` or override `get_active_tab`, so confirmation detection reads the right tab
- [ ] **PAR-05**: Community plugins maintain `_checkout_stage` through the flow, so error logs carry stage context
- [ ] **PAR-06**: Plugin routing is deterministic (`setup_for_items` currently populates `_active_plugins` by iterating a `set`, so with overlapping `domain_patterns` the winner varies by `id()` hash between runs, today, with the 7 bundled plugins)

### H. Plugin Ecosystem (EXT)

SEED-003. Trust model is consent plus SHA and content pinning plus honest provenance, explicitly not a sandbox. See `.planning/research/SUMMARY.md` for the reconciled design and the recorded decisions.

- [ ] **EXT-01**: No plugin can crash bot start, the dashboard render, `plugins list`, or `run_plugin` by omitting an attribute or raising in `__init__`
- [ ] **EXT-02**: `plugins/example_plugin.py` routes its purchase through `place_order_guarded()`, so the canonical template authors copy stops teaching the `test_mode` and BF-02 bypass
- [ ] **EXT-03**: Every plugin path resolves through `core/paths.py`, and a user-writable plugin root exists outside the package
- [ ] **EXT-04**: Bundled plugins win a filename collision, and a third-party plugin claiming a bundled domain is refused at load
- [ ] **EXT-05**: `PLUGIN_API_VERSION` is enforced at load instead of being a decorative constant nothing reads
- [ ] **EXT-06**: Every installed plugin has a provenance record: source, numeric owner ID, resolved commit SHA, content hash, declared API version, and the consent that authorised it
- [ ] **EXT-07**: Plugin file integrity is verified before `exec_module`, not only at install time, because plugin module bodies re-execute on every registry construction including an ordinary dashboard page render
- [ ] **EXT-08**: A run lock lets lifecycle commands tell the truth about whether a bot is running
- [ ] **EXT-09**: Third-party plugins are disarmed for checkout by default, independent of the global `monitor_only` setting, with a separate typed opt-in to arm
- [ ] **EXT-10**: Credential access is scoped per platform, and a third-party plugin never receives the CVV
- [ ] **EXT-11**: `plugins install <repo>[@ref]` fetches by resolved commit SHA and runs static pre-flight checks that never import the candidate
- [ ] **EXT-12**: A byte-level lint refuses plugin files containing invisible codepoints, bidi overrides, variation selectors, or Private Use Area characters outside strings and comments
- [ ] **EXT-13**: Install requires typed consent naming the source repo and owner ID, with no bare bypass flag
- [ ] **EXT-14**: `plugins update`, `remove`, `verify`, and `outdated` exist; update re-consents on any change; remove prints a credential rotation checklist
- [ ] **EXT-15**: A third-party plugin disclaimer appears at the point of decision and in SECURITY.md, README, and PLUGIN_DEV.md, and states plainly that third-party installs receive no review and that no revocation mechanism exists
- [ ] **EXT-16**: A machine-readable plugin registry exists as the in-repo source of truth, retiring the hand-maintained wiki table (REG-01, outstanding across two milestones)
- [ ] **EXT-17**: A CI guard fails the build if any shipped artifact describes third-party plugins as sandboxed, isolated, curated, verified, or safe

### I. Ops Hardening (OPS)

- [ ] **OPS-01**: `price_history` has an index on `item_link`, so per-chart lookups do not scan an append-only table that grows by roughly 15k rows per day for a 5-item watch
- [ ] **OPS-02**: `price_history` has a retention policy

### J. UAT Repair and Triage (UAT)

- [ ] **UAT-01**: 29-HV-5's recipe is rewritten to something physically possible (the `window.EventSource = undefined` plus reload recipe cannot work, because reload restores it)
- [ ] **UAT-02**: 29.1-UAT-2's stall-trigger recipe is corrected to be reliable
- [ ] **UAT-03**: The 8 UAT items that PR #11 and PR #12 unblock are re-run and their verdicts recorded
- [ ] **UAT-04**: The roughly 61 live-environment items are triaged against a stated acceptance bar and consolidated into one operator checklist, rather than being spread across 88 archived artifact files
- [ ] **UAT-05**: The `audit-uat` tooling gap is documented in-repo (it scans `.planning/phases/`, which is empty once milestones are archived, and reported zero outstanding items while 80 sat in `.planning/milestones/`)
- [ ] **UAT-06**: The "CI-green" claim in the v2.0 through v4.2 archives is corrected, since CI had never compiled when those milestones were archived

## v2 Requirements

Acknowledged, deferred, not in this roadmap.

### Plugin Isolation

- **ISO-01**: Process isolation for third-party plugins. The only real containment boundary; everything v5.0 ships is consent and integrity, not isolation. Windows cost specifically was not scoped.

### Community Retailer Parity

- **CRP-01**: Checkout form-fill for Walmart, Target, GameStop, NewEgg, and SquareEnix (v4.0 covers Amazon and BestBuy only)
- **CRP-02**: Order-confirmation detection for the 5 community plugins, which currently always fall through the detector
- **CRP-03**: CVV entry and quantity selection for community plugins
- **CRP-04**: CAPTCHA detection and solve path for community plugins
- **CRP-05**: Resolution of the 25 unverified-selector markers across the community plugins, which is live-retail blocked

### Reliability

- **REL-01**: Event-loop stall watchdog. `asyncio.timeout` cannot preempt a blocking plugin, and the exposure exists today with the 7 bundled plugins. Scope during roadmapping; do not let it silently expand EXT.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Process isolation / in-process sandbox | No in-process Python sandbox is a real boundary. PEP 578 says audit hooks are not sandboxing, RestrictedPython disclaims it, pysandbox was abandoned as broken by design. Shipping one would be theatre. Deferred to v2 as ISO-01 |
| Plugin-declared dependencies | `pip --no-deps` still executes a source distribution's `setup.py` during resolution, which is a second and earlier execution channel in a workstream premised on execution being uncontainable. Plugins may import the stdlib plus what ShopPyBot already depends on |
| Hosted plugin marketplace, ratings, stars, install counts, telemetry | Gameable signals are worse than no signal (GlassWorm faked popularity metrics), and this project has deliberately avoided a telemetry surface everywhere else |
| Auto-update, `update --all`, any scheduled path into the update code | Converts every trust-transfer incident from catchable to overnight, on a machine holding a credential store and a live checkout path |
| Hot reload after install, update, or remove | Non-unloadable modules plus live browser subprocesses plus supervised restart; the likely outcome is two plugin instances racing toward the same Place Order click. Restart is required and every mutation says so |
| Maintainer review gate on plugin install | Reintroduces the PR bottleneck SEED-003 exists to bypass |
| Generic Git-host plugin fetch | The point at which a `git` subprocess becomes unavoidable, which is a new environmental precondition on users without a dev toolchain. GitHub-only for v1, deferred rather than silently unsupported |
| Executing the ~61 live-environment UAT items | Requires live retail checkout, a funded 2captcha balance, live proxies, an Ubuntu host, and a real drop. J triages and repairs the checklist; running it is operator work |
| Destructive public-repo history rewrite | SEED-001's remaining half. gitleaks across 964 commits found one test-fixture false positive, so the rewrite is unjustified. Retired as a decision under PUB-09 rather than carried as debt |
| Request/API-mode hybrid checkout | Per-site reverse engineering and an arms race; unchanged from prior milestones |

## Traceability

Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| MAIN-01..07 | TBD | Pending |
| PKG-01..06 | TBD | Pending |
| PUB-01..09 | TBD | Pending |
| FIX-01..11 | TBD | Pending |
| SCAN-01..11 | TBD | Pending |
| QUAL-01..09 | TBD | Pending |
| PAR-01..06 | TBD | Pending |
| EXT-01..17 | TBD | Pending |
| OPS-01..02 | TBD | Pending |
| UAT-01..06 | TBD | Pending |

**Coverage:**
- v1 requirements: 84 total
- Mapped to phases: 0
- Unmapped: 84 (roadmap not yet created)

## Sequencing Constraints

Hard dependencies the roadmap must respect:

1. **A before E.** Several SCAN requirements target workflows that do not exist on master until PR #11 lands.
2. **B before SEED-002 is worth running.** release-please exists to publish an artifact that currently cannot start.
3. **PKG-06 before EXT-03.** If the bundled plugin root does not survive a wheel install, the fix is `importlib.resources` and belongs to B.
4. **EXT-01 before every other EXT.** Each later step multiplies the number of non-conforming plugins reaching paths that currently raise.
5. **EXT-09 before EXT-11.** The disarm default must already be true when install ships, so no released state has a stranger's freshly installed plugin able to buy by default.
6. **PAR-03 and EXT-09 are one mechanism.** Both build a pre-transfer gate at the same orchestrator site.
7. **EXT-15 gates milestone completion**, not phase ordering. The disclaimer is the precondition that makes the plugin manager defensible.

## Review Criteria

Per RETROSPECTIVE.md lesson 4, workstreams G and H both warrant a post-verification REVIEW.md deep pass: G touches a safety-critical guard, H adds a new unauthenticated input surface. That review carries two non-negotiable criteria:

- For every shipped control, one sentence naming what it does not stop.
- No shipped artifact describes third-party plugins as sandboxed, isolated, curated, verified, or safe. EXT-17 makes this mechanical.

*Requirements defined: 2026-08-02*
*Last updated: 2026-08-02 after initial definition*
