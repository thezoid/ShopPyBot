# ShopPyBot — Roadmap

## Project

**Core Value:** A drop-in plugin framework that lets the community add new retail platform integrations by placing a single Python file in `plugins/` — no core changes required.

---

## Milestones

- ✅ **v1 Open Source Launch** — Phases 1-6 (shipped 2026-06-03)
- ✅ **v2.0 Modular Core + Cross-Platform UX** — Phases 7-11 (shipped 2026-06-06)
- ✅ **v3.0 Resilience + Ecosystem** — Phases 12-17 (shipped 2026-06-10)
- ✅ **v4.0 Win-the-Drop (Acquisition Core + Reliability)** — Phases 18-24 (shipped 2026-06-25)
- ✅ **v4.1 Dashboard & Observability** — Phases 25-29.1 (shipped 2026-06-30)
- ✅ **v4.2 Release Readiness** — Phases 30-35 (shipped 2026-07-03)
- 🔄 **v5.0 Real Release & Plugin Ecosystem** — Phases 36-50 (in progress, started 2026-08-02)

---

## Phases

<details>
<summary>✅ v1 Open Source Launch (Phases 1-6) — SHIPPED 2026-06-03</summary>

- [x] Phase 1: Foundations + Security (5/5 plans) — 2026-06-02
- [x] Phase 2: Plugin Migration (6/6 plans) — 2026-06-03
- [x] Phase 3: Community Documentation (2/2 plans) — 2026-06-03
- [x] Phase 4: Async Orchestrator (5/5 plans) — 2026-06-03
- [x] Phase 5: Notification System (5/5 plans) — 2026-06-03
- [x] Phase 6: Platform Expansion (5/5 plans) — 2026-06-03

Full phase detail archived at `.planning/milestones/v1-phases` (see also `milestones/`).

</details>

<details>
<summary>✅ v2.0 Modular Core + Cross-Platform UX (Phases 7-11) — SHIPPED 2026-06-06</summary>

- [x] Phase 7: Modular Core Service (3/3 plans) — 2026-06-04
- [x] Phase 8: Credential Store (4/4 plans) — 2026-06-04
- [x] Phase 9: CLI Front-End (4/4 plans) — 2026-06-04
- [x] Phase 10: Optional Web UI (4/4 plans) — 2026-06-04
- [x] Phase 11: Cross-Platform Verification (5/5 plans) — 2026-06-05

Full phase detail archived at `.planning/milestones/v2.0-ROADMAP.md`.
Audit: `.planning/milestones/v2.0-MILESTONE-AUDIT.md` (status: passed).

</details>

<details>
<summary>✅ v3.0 Resilience + Ecosystem (Phases 12-17) — SHIPPED 2026-06-10</summary>

- [x] Phase 12: Stability Foundation (4/4 plans) — 2026-06-09
- [x] Phase 13: Anti-Detection Layer 1 — Fingerprint + Proxy (3/3 plans) — 2026-06-09
- [x] Phase 14: Anti-Detection Layer 2 — CAPTCHA Solving (3/3 plans) — 2026-06-09
- [x] Phase 15: Plugin Ecosystem Registry (3/3 plans) — 2026-06-09
- [x] Phase 16: Price Monitoring (4/4 plans) — 2026-06-10
- [x] Phase 17: Test Hardening (4/4 plans) — 2026-06-10

Full phase detail archived at `.planning/milestones/v3.0-ROADMAP.md`.
Audit: `.planning/milestones/v3.0-MILESTONE-AUDIT.md`.

</details>

<details>
<summary>✅ v4.0 Win-the-Drop (Phases 18-24) — SHIPPED 2026-06-25</summary>

- [x] Phase 18: Safety Gate + Config Foundation (4/4 plans) — 2026-06-11
- [x] Phase 19: DB Schema + Confirmation Detection (4/4 plans) — 2026-06-11
- [x] Phase 20: Checkout Profile + Form-Fill (4/4 plans) — 2026-06-11
- [x] Phase 21: Per-Step Timeouts + Unified Retry + Cart-Retry (4/4 plans) — 2026-06-12
- [x] Phase 22: Supervisor + Browser Relaunch + Server Safety (4/4 plans) — 2026-06-12
- [x] Phase 23: Encrypted Session Persistence (4/4 plans) — 2026-06-12
- [x] Phase 24: Health Surface + Server Safety (5/5 plans) — 2026-06-12

Full phase detail archived at `.planning/milestones/v4.0-ROADMAP.md`.
Audit: `.planning/milestones/v4.0-MILESTONE-AUDIT.md` (status: tech_debt — pre-accepted live-UAT debt).

</details>

<details>
<summary>✅ v4.1 Dashboard & Observability (Phases 25-29.1) — SHIPPED 2026-06-30</summary>

- [x] Phase 25: Design System (3/3 plans) — 2026-06-25
- [x] Phase 26: Read-Only API Endpoints (3/3 plans) — 2026-06-27
- [x] Phase 27: SSE Infrastructure (3/3 plans) — 2026-06-27
- [x] Phase 28: Frontend Observability Surfaces (4/4 plans) — 2026-06-27
- [x] Phase 29: SSE Client Wiring (3/3 plans) — 2026-06-28
- [x] Phase 29.1: v4.1 Tech-Debt Cleanup — SSE stall fallback + uPlot load order + log-dup guard (4/4 plans, INSERTED) — 2026-06-30

Full phase detail archived at `.planning/milestones/v4.1-ROADMAP.md`.
Audit: `.planning/milestones/v4.1-MILESTONE-AUDIT.md` (status: tech_debt — 2 low-sev warnings + 16 pre-accepted live-UAT items, no blockers).

</details>

<details>
<summary>✅ v4.2 Release Readiness (Phases 30-35) — SHIPPED 2026-07-03</summary>

- [x] Phase 30: Breakfix Hardening (6/6 plans) — 2026-07-02
- [x] Phase 31: CI & Security Infrastructure (3/3 plans) — 2026-07-02
- [x] Phase 32: Release Automation & Community Readiness (3/3 plans) — 2026-07-02
- [x] Phase 33: Config Refactor (2/2 plans) — 2026-07-02
- [x] Phase 34: Feature Completion (3/3 plans) — 2026-07-03
- [x] Phase 35: Audit-Fixes & Doc-Hygiene Cleanup (3/3 plans) — 2026-07-03

Full phase detail archived at `.planning/milestones/v4.2-ROADMAP.md`.
Audit: `.planning/milestones/v4.2-MILESTONE-AUDIT.md` (status: tech_debt — 20/20 requirements satisfied, no blockers; BF-02 5-plugin propagation gap + operator-gated GitHub Settings items tracked as debt).

</details>

### 🔄 v5.0 Real Release & Plugin Ecosystem (Phases 36-50) — IN PROGRESS

- [x] **Phase 36: Mainline Reconciliation** — `master` becomes the real ShopPyBot and its suite runs in CI for the first time (MAIN-01..07) (completed 2026-08-02)
- [ ] **Phase 37: Distributable Artifact** — the built wheel actually runs, so publishing one is worth doing (PKG-01..06)
- [ ] **Phase 38: Scanning to Zero** — every scanner reports zero real findings and the checks that produce them are required (SCAN-01..11)
- [ ] **Phase 39: Quality Floor** — lint, format, typecheck, and coverage enforced in CI before the milestone's new code lands (QUAL-01..09)
- [ ] **Phase 40: Public-Repo Readiness** — LICENSE, current README, honest sample config, CODEOWNERS, drift corrected (PUB-01..09)
- [ ] **Phase 41: Live Defect Closure** — control commands report the truth, unattended alerts arrive, dashboard data is current (FIX-01..11)
- [ ] **Phase 42: Plugin Registry Hardening** — a malformed plugin cannot take down start, the dashboard, or `plugins list` (EXT-01, EXT-02)
- [ ] **Phase 43: Plugin Roots, Precedence & API Version Gate** — a user-writable second root, bundled-wins collisions, version enforcement (EXT-03..05)
- [ ] **Phase 44: Provenance, Load-Boundary Integrity & Run Lock** — every managed plugin says where it came from and drifted files do not execute (EXT-06..08)
- [ ] **Phase 45: Community Plugin Parity + Pre-Transfer Arming Gate** — 5 community plugins reach the Amazon/BestBuy safety floor; the shared checkout gate is built once (PAR-01..06)
- [ ] **Phase 46: Trust Tiers & Capability Reduction** — third-party plugins ship disarmed for checkout and scoped for credentials (EXT-09, EXT-10)
- [ ] **Phase 47: Fetch, Pre-Flight, Install & Consent** — `plugins install` pinned by commit SHA, refused statically, gated by typed consent (EXT-11..13)
- [ ] **Phase 48: Plugin Lifecycle — update, remove, verify, outdated** — mutations re-consent, removal prints a rotation checklist (EXT-14)
- [ ] **Phase 49: Trust Documentation, Registry & Vocabulary Guard** — nothing shipped calls third-party plugins safe (EXT-15..17)
- [ ] **Phase 50: Ops Hardening & UAT Consolidation** — bounded price history, one honest operator verification checklist (OPS-01..02, UAT-01..06)

---

## Phase Details (v5.0)

### Phase 36: Mainline Reconciliation

**Goal**: `master` is the real ShopPyBot — every v4.1 and v4.2 artifact is on the default branch, and the suite those milestones claimed runs green in CI for the first time.
**Depends on**: Nothing (first phase of the milestone; every other phase is undurable until this lands)
**Requirements**: MAIN-01, MAIN-02, MAIN-03, MAIN-04, MAIN-05, MAIN-06, MAIN-07
**Success Criteria** (what must be TRUE):

  1. A CI run on `master` schedules jobs and reports the full v4.1+v4.2 suite green on both `ubuntu-latest` and `windows-latest` — where today 81 consecutive runs have scheduled zero jobs and produced no logs.
  2. `gitleaks.yml`, `release-please.yml`, the dashboard, and `httpx==0.28.1` are all present on `master` at HEAD.
  3. `gh pr list` shows #8, #11, #12 and #15 through #20 all resolved: #11, #12 and the Dependabot set merged in an order that did not require re-resolving the `ci.yml` collision between #19 and #20; #8 closed unmerged with a recorded reason.
  4. Each of the 4 local commits absent from PR #11's head carries a recorded include-or-exclude decision, and `git log master` matches that decision rather than reflecting a conflict-resolution side effect.

**Plans**: 5 plans (strictly sequential, waves 1 through 5; `strict: true` branch protection makes parallel merges impossible)
Plans:

- [x] 36-01-PLAN.md: rollback tag `pre-v5-mainline`, merge PR #12, close PR #8 with a recorded reason (MAIN-05, MAIN-06)
- [x] 36-02-PLAN.md: absorb PR #11 head divergence without force-push, record MAIN-03 per SHA, union-resolve the two conflicts, full local suite gate (MAIN-02, MAIN-03)
- [x] 36-03-PLAN.md: plain-push, merge PR #11 as a merge commit, verify the union pins, workflow artifacts, SHA ancestry and a real CI run on master (MAIN-01..04)
- [x] 36-04-PLAN.md: resolve the pip Dependabot set #16, #17, #15 with a direction check before each merge (MAIN-07)
- [x] 36-05-PLAN.md: serialize the ci.yml set #18, #19, #20, then the phase gate and Phase 38 handoff (MAIN-01, MAIN-07)

**Planning corrections** (verified live 2026-08-02, these supersede the success criteria above where they conflict):

  - Criterion 1's "81 consecutive zero-job runs" premise is STALE. Master's CI is already green today on `e98ec83` and `4123059`, 755 passed / 2 skipped on both runners. MAIN-01's real remaining question is whether the LARGER merged suite (roughly 939 tests) stays green under a ci.yml already proven correct on the smaller input.
  - Criterion 4's "4 local commits" count is STALE. It was 8 at discuss time, 9 at research time, and 11 at planning time. The plans re-derive the list fresh at execution time and never hardcode a count.
  - `master` ALREADY has branch protection (`CodeQL`, `test (windows-latest)`, `test (ubuntu-latest)`, `strict: true`, `enforce_admins: false`), which CONTEXT.md did not anticipate. The plans work within it and change nothing; Phase 38 still owns protection changes.

**Risk**: Highest-risk phase in the milestone. Small in requirement count, large in blast radius — a 263-commit merge whose CI has never executed, so the first green run is also the first signal that the merge is correct. Plan for verification room, not just merge mechanics.

### Phase 37: Distributable Artifact

**Goal**: An installed wheel is a working ShopPyBot, so release-please publishing one becomes worth doing.
**Depends on**: Phase 36 (the wheel CI job needs a `ci.yml` that compiles)
**Requirements**: PKG-01, PKG-02, PKG-03, PKG-04, PKG-05, PKG-06
**Success Criteria** (what must be TRUE):

  1. A clean-environment install of the built wheel starts `shoppybot web` without a `StaticFiles` `RuntimeError`, and a named sound file resolves from the installed package.
  2. Installing the wheel into an empty virtualenv, with no `requirements.txt` available, produces no `ModuleNotFoundError` for `websockets`, `starlette`, `httpx`, or `requests` on any exercised path.
  3. A CI job performs criteria 1 and 2 on every push and fails the build if either regresses.
  4. `bundled_plugins_dir()` called from an installed wheel returns a directory containing the 7 bundled plugins, and that result is recorded as the input Phase 43 (EXT-03) depends on.
  5. `requirements.txt` pins neither `selenium` nor `webdriver-manager`, and no Dependabot alert references either.

**Plans**: TBD
**Note**: PKG-06 is a hard gate on Phase 43. If the bundled root does not survive a wheel install, the `importlib.resources` fix belongs here, not to workstream H.

### Phase 38: Scanning to Zero

**Goal**: Every security scanner attached to the repo reports zero outstanding real findings, and the checks that produce them are required to merge.
**Depends on**: Phase 36 (several of these target workflows that do not exist on `master` until PR #11 lands)
**Requirements**: SCAN-01, SCAN-02, SCAN-03, SCAN-04, SCAN-05, SCAN-06, SCAN-07, SCAN-08, SCAN-09, SCAN-10, SCAN-11
**Success Criteria** (what must be TRUE):

  1. The Dependabot, CodeQL, and secret-scanning queues each show zero open real findings: the 7 dependency alerts closed, the two `logger.py` clear-text alerts and the 3 production url-sanitization alerts resolved, the 19 test-file url-sanitization alerts showing as deliberately dismissed with a recorded reason, and secret scanning running with non-provider patterns and validity checks enabled.
  2. A pull request against `master` cannot merge without gitleaks, CodeQL, and the test matrix passing, and the rule applies to administrators.
  3. `.github/workflows/` on `master` contains no `disabled_manually` CodeQL workflow, and `origin/dev` with its 4 rotted workflows has a recorded disposition.
  4. Every third-party action in every workflow is referenced by a 40-character commit SHA, and `ci.yml` declares an explicit `permissions` block.

**Plans**: TBD

### Phase 39: Quality Floor

**Goal**: The code standards CLAUDE.md already states are mechanically enforced on every push, before this milestone's remaining eleven phases write new code.
**Depends on**: Phase 36 (CI must compile), Phase 38 (new CI jobs follow the SHA-pinning and permissions conventions established there)
**Requirements**: QUAL-01, QUAL-02, QUAL-03, QUAL-04, QUAL-05, QUAL-06, QUAL-07, QUAL-08, QUAL-09
**Success Criteria** (what must be TRUE):

  1. A push introducing a lint, format, or type error fails CI; pre-existing findings are either fixed or recorded in a checked-in baseline that the build reads.
  2. A CI run reports a coverage number and the starting baseline is recorded in-repo.
  3. No `except Exception: pass` site remains under the production tree — each of the 11 either handles the error or lets it propagate.
  4. The two tests that skip when `config.yml` is absent fail loudly instead, including the plaintext-secrets security check, and a full suite run emits no never-awaited-coroutine warning.
  5. `amazon_bot.py` and `bestbuy_bot.py` no longer exist, and every file over 300 lines and function over 30 lines is either under the limit or listed in a recorded exceptions file with rationale.

**Plans**: TBD

### Phase 40: Public-Repo Readiness

**Goal**: A stranger landing on the repository gets an accurate, licensed, current picture of what ShopPyBot is and how to run it.
**Depends on**: Phase 36 (docs are written against what is on `master`)
**Requirements**: PUB-01, PUB-02, PUB-03, PUB-04, PUB-05, PUB-06, PUB-07, PUB-08, PUB-09
**Success Criteria** (what must be TRUE):

  1. The repository root carries a LICENSE file and GitHub displays the license on the repo page.
  2. Following README's Prerequisites and Setup on a clean machine gets the bot running via nodriver, with no step mentioning `chromedriver` or `selenium.driver_path`.
  3. `sample.config.yml` round-trips through `AppConfig` with every declared section present including `debug.monitor_only`, and advertises no key that nothing reads.
  4. `_deprecated/` is absent from `master`, CODEOWNERS is present so code-owner review can be required, and CLAUDE.md and SECURITY.md describe the current architecture and the already-enabled PVR state.
  5. Every drift item from the 2026-08-01 audit reads correctly (dashboard section count, the web launcher command, banner colour values, cold-load theme default, MC-3's polling description, AmazonPlugin's registry difficulty), and SEED-001's destructive history rewrite is retired as a recorded decision citing the one test-fixture false positive found across 964 commits.

**Plans**: TBD
**Note**: LICENSE (PUB-01) is where Phase 49's formal liability language lands, so this phase precedes it.

### Phase 41: Live Defect Closure

**Goal**: The defects a real run actually hits are gone — control commands report the truth, the alerts that exist only for unattended operation arrive, and the dashboard shows current data.
**Depends on**: Phase 36, Phase 39 (new code lands under the enforced standard)
**Requirements**: FIX-01, FIX-02, FIX-03, FIX-04, FIX-05, FIX-06, FIX-07, FIX-08, FIX-09, FIX-10, FIX-11
**Success Criteria** (what must be TRUE):

  1. Pressing Start on the dashboard when the bot loop cannot survive startup surfaces a real failure in the UI, instead of a 200 over a dead loop.
  2. A headless run with no TTY, and a run where `sys.stdin` is None, neither busy-spins nor force-fires manual-intervention gates; a listener failure is reported rather than dying silently; and shutdown completes in seconds rather than stalling `asyncio.run()` teardown for up to 300.
  3. Saving `test_mode` from the dashboard either changes the running process's behaviour or reports that it did not, and the test covering that write patches the real module path and asserts the write it claims to test.
  4. A `plugin_parked` event and a `health_degraded` event each produce a delivered Discord, email, and SMS message, visually distinguishable from a successful purchase, with all six `action` values documented and the plugin name escaped and length-capped on every surface.
  5. Starting on a host without Chrome prints an actionable diagnosis instead of every plugin failing silently, and the Confirmed Orders view updates without a page reload.

**Plans**: TBD
**UI hint**: yes
**Note**: FIX-08 (escape and cap the plugin name) must land before Phase 47 makes that value attacker-controlled.

### Phase 42: Plugin Registry Hardening

**Goal**: A malformed or hostile plugin cannot take down bot start, the dashboard render, `plugins list`, or `run_plugin`, and the template contributors copy stops teaching the checkout bypass.
**Depends on**: Phase 39 (H1 in `research/SUMMARY.md`; the only H phase independently valuable if the rest of H is cut)
**Requirements**: EXT-01, EXT-02
**Success Criteria** (what must be TRUE):

  1. A plugin that omits `domain_patterns`, or raises inside `__init__`, is skipped with one discovery-time warning while every other plugin still loads — `shoppybot run` starts, the dashboard renders, and `plugins list` prints its table.
  2. `/api/analytics` and `run_plugin` survive that same malformed plugin without the supervisor treating it as a crash and entering a backoff-restart loop.
  3. Two consecutive `plugins list` runs on the same machine discover plugins in the same order.
  4. `plugins/example_plugin.py` places its order through `place_order_guarded()`, so a copy of the canonical template honours `test_mode` and writes the BF-02 place-order marker.

**Plans**: TBD
**Note**: Routing determinism (`route()` picking the same plugin across runs) belongs to PAR-06 in Phase 45; this phase covers discovery-order stability only.

### Phase 43: Plugin Roots, Precedence & API Version Gate

**Goal**: Plugins live in two clearly separated roots, bundled code always wins a collision, and a plugin that does not match the supported API version is refused rather than loaded.
**Depends on**: Phase 42 (multi-root discovery is where malformed third-party plugins first arrive), Phase 37 (PKG-06 answers whether the bundled root survives a wheel install)
**Requirements**: EXT-03, EXT-04, EXT-05
**Success Criteria** (what must be TRUE):

  1. A `.py` file placed in the user plugin directory under `data_dir()` is discovered and loaded, and `SHOPBOT_DATA_DIR` relocates that directory in tests.
  2. A user-root file named after a bundled plugin, or declaring a domain a bundled plugin claims, is refused at load with a message naming the conflict, and the bundled plugin still loads.
  3. `plugins list` and the dashboard show, for every plugin, whether it is bundled or third-party.
  4. A plugin declaring an API version below the supported minimum is refused; one declaring an older-but-supported version loads with a warning.
  5. No production code computes a plugin path outside `core/paths.py`.

**Plans**: TBD
**UI hint**: yes
**Research flag**: Blocked on PKG-06's factual answer. If `bundled_plugins_dir()` does not resolve from an installed wheel, the `importlib.resources` fix is Phase 37 work, not this phase's.

### Phase 44: Provenance, Load-Boundary Integrity & Run Lock

**Goal**: Every plugin in the user root can say where it came from, a file that changed since it was recorded does not execute, and lifecycle commands can tell the truth about whether a bot is running.
**Depends on**: Phase 43 (needs the writable root and the origin field to join against)
**Requirements**: EXT-06, EXT-07, EXT-08
**Success Criteria** (what must be TRUE):

  1. An `installed.json` beside the user-root plugins records, per plugin, the source and URL, the numeric owner ID, the resolved 40-character commit SHA, an independently computed content SHA-256, the declared API version, and the consent that authorised it — and survives an interrupted write without corrupting.
  2. Changing one byte of a managed plugin file causes it to be refused on the next registry construction, including an ordinary dashboard page render rather than only a bot start, and `plugins list` reports it as `modified`.
  3. An unmanifested file dropped into the user root is refused and logged; the same file placed in the bundled root still loads, so drop-in development is unchanged.
  4. `shoppybot status` answers whether a bot is running in another process, and that answer degrades honestly (advisory staleness) when the holding process was killed.

**Plans**: TBD
**Note**: The manifest informs discovery; it does not authorise. No shipped wording may describe the load check as an authorization boundary — whoever can drop a file into that directory can write the manifest beside it.

### Phase 45: Community Plugin Parity + Pre-Transfer Arming Gate

**Goal**: The 5 community plugins reach the same safety floor as Amazon and BestBuy, and the single per-plugin checkout gate that Phase 46 extends to third-party code exists and is proven on plugins the maintainer owns.
**Depends on**: Phase 44 (PAR-06's bundled-before-third-party ordering needs the origin field from Phase 43)
**Requirements**: PAR-01, PAR-02, PAR-03, PAR-04, PAR-05, PAR-06
**Success Criteria** (what must be TRUE):

  1. A place-order-stage timeout on Walmart, Target, GameStop, NewEgg, or SquareEnix latches the item and refuses the retry, exactly as Amazon and BestBuy already do — closing the residual double-buy exposure carried out of v4.2.
  2. A hung selector in a community plugin aborts that step within its own budget instead of blocking the plugin loop, and the resulting error log names the checkout stage it failed in.
  3. With `monitor_only` set, no community plugin reaches its checkout entry point, enforced at the one pre-transfer gate that Phase 46 extends — not at a second gate that can diverge from it.
  4. Confirmation detection reads the correct tab for every community plugin.
  5. With two plugins whose `domain_patterns` overlap, `route()` returns the same plugin on every run on the same machine.

**Plans**: TBD
**Review**: REVIEW.md deep-review pass required (RETROSPECTIVE.md lesson 4 — this phase touches a safety-critical guard). The review must state, for every shipped control, one sentence naming what it does not stop.

### Phase 46: Trust Tiers & Capability Reduction

**Goal**: A third-party plugin cannot spend money or reach a credential it was not scoped to, unless the operator has explicitly armed it.
**Depends on**: Phase 45 (shared arming mechanism), Phase 44 (the manifest's trust field)
**Requirements**: EXT-09, EXT-10
**Success Criteria** (what must be TRUE):

  1. A third-party plugin is refused at the pre-transfer gate even with the global `monitor_only` off, until an explicit typed opt-in arms it; the armed state is recorded in the manifest and survives a restart.
  2. A bundled plugin's behaviour is unchanged by the third-party disarm default.
  3. A plugin requesting credentials receives only its own platform's keys, and a test proves a third-party plugin never receives the CVV.
  4. Every user-facing string describing the arming gate carries the sentence naming what it does not stop — a purchase performed by the plugin inside `check_availability`, which runs before the gate.

**Plans**: TBD
**Note**: This phase must ship before Phase 47 so no released state exists in which a freshly installed stranger's plugin can buy by default.

### Phase 47: Fetch, Pre-Flight, Install & Consent

**Goal**: `plugins install` can bring a stranger's plugin onto the machine — pinned, statically screened, and consented to — without ever importing the candidate to decide whether to install it.
**Depends on**: Phase 46 (the disarm default must already be true), Phase 44 (the manifest to write into and the run lock to warn from)
**Requirements**: EXT-11, EXT-12, EXT-13
**Success Criteria** (what must be TRUE):

  1. `plugins install <owner>/<repo>[@ref]` resolves the ref to a 40-character commit SHA, fetches at that SHA, and records the SHA plus an independently computed content hash; a branch or tag name is never what gets stored.
  2. A candidate that fails to parse, declares no `RetailerPlugin` subclass, imports outside the allowlist, or contains an invisible codepoint, bidi override, variation selector, or Private Use Area character outside strings and comments is refused before any file is written — and nothing about the candidate was imported to reach that verdict.
  3. The install prompt shows `github.com/<owner>/<repo>` and the numeric owner ID in a handful of concrete lines and requires the plugin name typed back; no bare `--yes` exists, and non-interactive install requires `--expect-sha256`.
  4. A successful install prints that a restart is required, and the newly installed plugin is disarmed for checkout.
  5. A rate-limited or unreachable GitHub produces an explicit failure, never a silent fallback to a cache or an alternate source.

**Plans**: TBD
**Review**: REVIEW.md deep-review pass required (RETROSPECTIVE.md lesson 4 — this phase opens the milestone's new unauthenticated input surface). Two non-negotiable criteria: one sentence per shipped control naming what it does not stop, and confirmation that no shipped artifact describes third-party plugins as sandboxed, isolated, curated, verified, or safe.
**Research flag**: The consent prompt copy is an acceptance criterion, not an implementation detail. Re-read the consent-fatigue evidence in `research/SUMMARY.md` before writing it.

### Phase 48: Plugin Lifecycle — update, remove, verify, outdated

**Goal**: An installed plugin can be changed or taken off the machine with the same honesty the install had, and removal tells the operator what it did not undo.
**Depends on**: Phase 47 (update is install-with-a-prior-record and cannot exist before install)
**Requirements**: EXT-14
**Success Criteria** (what must be TRUE):

  1. `plugins update <name>` re-prompts for consent on any SHA or content change, shows what changed, and treats an owner-ID change or a capability escalation as a new install rather than an update.
  2. `plugins outdated` reports and can never install, and no scheduler, timer, or startup hook can reach the update path.
  3. `plugins verify` re-checks every managed file against its recorded hash and names each mismatch.
  4. `plugins remove <name>` refuses by default while a run lock is held and refuses outright while a place-order marker is set, and on success prints a credential and session rotation checklist whose referenced commands all exist.

**Plans**: TBD
**Note**: Covered by Phase 47's REVIEW.md scope — the same input surface. Re-run both REVIEW criteria against `update` and `remove` before closing this phase.

### Phase 49: Trust Documentation, Registry & Vocabulary Guard

**Goal**: Nothing ShopPyBot ships describes third-party plugins as safe, and the disclaimer a user needs is at the point where the decision is made.
**Depends on**: Phase 48, Phase 40 (the LICENSE the liability language lands beside)
**Requirements**: EXT-15, EXT-16, EXT-17
**Success Criteria** (what must be TRUE):

  1. The third-party disclaimer appears at the point of decision — in the install prompt and beside every third-party row in `plugins list` — and in SECURITY.md, README, and PLUGIN_DEV.md, stating plainly that third-party installs receive no review of any kind and that no revocation mechanism exists.
  2. SECURITY.md states that its per-platform risk assessment applies to merged plugins only.
  3. A CI job fails the build when any shipped artifact — code, docstring, variable name, doc, CLI help, release note, or registry row — calls third-party plugins sandboxed, isolated, curated, verified, or safe.
  4. An in-repo machine-readable registry is the source of truth, CI generates the JSON index and the markdown table from it, and the hand-maintained wiki page is retired rather than left to rot (closes REG-01, outstanding across two milestones).

**Plans**: TBD
**Milestone gate**: EXT-15 gates milestone completion. The disclaimer is the precondition that makes the plugin manager defensible; the milestone does not close without it.

### Phase 50: Ops Hardening & UAT Consolidation

**Goal**: The operational data path stays fast and bounded, and the outstanding-verification picture is one honest operator checklist instead of 88 scattered archive files.
**Depends on**: Phase 36 (UAT-03 re-runs the items PR #11 and #12 unblock; UAT-06 corrects a claim only Phase 36 can make true), Phase 49
**Requirements**: OPS-01, OPS-02, UAT-01, UAT-02, UAT-03, UAT-04, UAT-05, UAT-06
**Success Criteria** (what must be TRUE):

  1. A per-item price-history chart loads without a full scan of `price_history`, and the table stops growing without bound under a stated, applied retention policy — against a table carrying weeks of the roughly 15k-rows-per-day a 5-item watch produces.
  2. 29-HV-5 and 29.1-UAT-2 each carry a recipe a person can actually follow to reproduce the condition they test.
  3. The 8 UAT items that PR #11 and PR #12 unblock carry recorded verdicts.
  4. One operator checklist file lists every remaining live-environment item with a stated acceptance bar, and no verdict lives only inside an archived phase artifact.
  5. The `audit-uat` archive blindspot is documented in-repo, and the "CI-green" claim in the v2.0 through v4.2 archives is corrected.

**Plans**: TBD

---

## Progress

| Milestone | Phases | Plans | Status | Shipped |
|-----------|--------|-------|--------|---------|
| v1 Open Source Launch | 1-6 | 28/28 | ✅ Shipped | 2026-06-03 |
| v2.0 Modular Core + Cross-Platform UX | 7-11 | 20/20 | ✅ Shipped | 2026-06-06 |
| v3.0 Resilience + Ecosystem | 12-17 | 21/21 | ✅ Shipped | 2026-06-10 |
| v4.0 Win-the-Drop | 18-24 | 29/29 | ✅ Shipped | 2026-06-25 |
| v4.1 Dashboard & Observability | 25-29.1 | 20/20 | ✅ Shipped | 2026-06-30 |
| v4.2 Release Readiness | 30-35 | 20/20 | ✅ Shipped | 2026-07-03 |
| v5.0 Real Release & Plugin Ecosystem | 36-50 | 0/TBD | 🔄 In progress | — |

All requirements satisfied across v1 (44) + v2.0 (22) + v3.0 (18) + v4.0 (17) + v4.1 (16) + v4.2 (20). Per-milestone requirement detail in `.planning/milestones/v*-REQUIREMENTS.md`. v5.0 carries 84 requirements across 15 phases (36-50); per-requirement mapping in `.planning/REQUIREMENTS.md` → Traceability.

### v5.0 phase-status detail

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 36. Mainline Reconciliation | 5/5 | Complete   | 2026-08-02 |
| 37. Distributable Artifact | 0/TBD | Not started | - |
| 38. Scanning to Zero | 0/TBD | Not started | - |
| 39. Quality Floor | 0/TBD | Not started | - |
| 40. Public-Repo Readiness | 0/TBD | Not started | - |
| 41. Live Defect Closure | 0/TBD | Not started | - |
| 42. Plugin Registry Hardening | 0/TBD | Not started | - |
| 43. Plugin Roots, Precedence & API Version Gate | 0/TBD | Not started | - |
| 44. Provenance, Load-Boundary Integrity & Run Lock | 0/TBD | Not started | - |
| 45. Community Plugin Parity + Pre-Transfer Arming Gate | 0/TBD | Not started | - |
| 46. Trust Tiers & Capability Reduction | 0/TBD | Not started | - |
| 47. Fetch, Pre-Flight, Install & Consent | 0/TBD | Not started | - |
| 48. Plugin Lifecycle — update, remove, verify, outdated | 0/TBD | Not started | - |
| 49. Trust Documentation, Registry & Vocabulary Guard | 0/TBD | Not started | - |
| 50. Ops Hardening & UAT Consolidation | 0/TBD | Not started | - |

---

## v5.0 Sequencing Invariants

These are the seven hard constraints from `REQUIREMENTS.md`, mapped onto phase numbers. Reordering phases without re-checking these breaks the milestone.

| # | Constraint | Satisfied by |
|---|------------|--------------|
| 1 | A before E — SCAN targets workflows not on `master` until PR #11 lands | Phase 36 → Phase 38 |
| 2 | B before release-please is worth running | Phase 37 precedes any release cut |
| 3 | PKG-06 before EXT-03 | Phase 37 → Phase 43 |
| 4 | EXT-01 before every other EXT | Phase 42 is the first EXT phase |
| 5 | EXT-09 before EXT-11 — the disarm default must be true before install ships | Phase 46 → Phase 47 |
| 6 | PAR-03 and EXT-09 are one mechanism | Phase 45 builds the pre-transfer arming gate; adjacent Phase 46 extends it. One gate, not two |
| 7 | EXT-15 gates milestone completion, not phase ordering | Phase 49 is a milestone gate; Phase 50 may still follow it |

**Additional derived orderings (not hard constraints, but deliberate):**

- Phase 39 (Quality Floor) precedes Phases 41-50 so the milestone's new code is written under an enforced standard rather than retrofitted to one.
- Phase 41's FIX-08 (escape and length-cap the plugin name) precedes Phase 47, which is what makes that value attacker-controlled.
- Phase 40's LICENSE precedes Phase 49's liability language, which lands beside it.
- The H workstream's internal order (Phases 42, 43, 44, 46, 47, 48, 49 = H1-H7) is the reconciled order from `research/SUMMARY.md`. It is researched, not re-derived.

---

*Last updated: 2026-08-02 — v5.0 Real Release & Plugin Ecosystem roadmap created (Phases 36-50, 84 requirements mapped, 100% coverage). Next: `/gsd:plan-phase 36`.*
