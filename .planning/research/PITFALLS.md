# Pitfalls Research: v5.0 Workstream H — Third-Party Plugin Distribution

**Domain:** Adding a remote plugin install channel (install / update / remove from
arbitrary third-party repositories) to an existing single-process Python application that
holds retailer credentials, a 2captcha API key, proxy credentials, encrypted authenticated
retailer sessions, a shipping/billing checkout profile, and a live checkout path that types
a CVV and clicks Place Order.

**Researched:** 2026-08-02
**Confidence:** HIGH for the incident record (all cited, multiple independent sources per
incident). HIGH for the codebase-specific hazards (every claim traced to a file and line in
this repo, read directly). HIGH for the in-process-sandbox analysis (CPython upstream
statements, not third-party opinion). MEDIUM for the liability/disclaimer section (drawn
from comparable projects' published policies and consent-habituation research, not legal
advice; **not reviewed by a lawyer**).

**Supersedes:** the v4.1 PITFALLS.md at this path for v5.0 scope. Prior-milestone pitfalls
(double-buy idempotency, CVV logging, the asyncio write-queue, the SSE cross-loop race)
remain in force and are not repeated here.

---

## 0. Blast Radius — Verified Against This Codebase

Every pitfall below assumes this reach. Each line was read, not inferred.

| Asset | How a plugin reaches it | Verified at |
|-------|------------------------|-------------|
| All 20 retailer/notification/2captcha secrets | `from core.credentials import get_store; get_store().list()` then `.get(k)` per key. Process-global singleton, no caller identity, no audit. | `core/credentials.py:47-77`, `:310-320` |
| Shipping + billing address (9 fields) | `core.checkout_profile` reads `CHECKOUT_PROFILE_KEYS` out of the same store | `core/checkout_profile.py:20`, `:78` |
| Authenticated retailer sessions (cookies) | `from core.session_store import build_session_store; build_session_store().restore("amazon")` returns decrypted cookie dicts. Account takeover without ever needing the password. | `core/plugin_base.py:344-345`, `core/session_store.py:74` |
| Place Order | `place_order_guarded()` is a **concrete helper on the ABC, not an enforced gate**. A plugin's own `auto_buy` can click whatever it wants. | `core/plugin_base.py:151-192` |
| The whole event loop | One plugin coroutine that blocks (sync I/O, `time.sleep`, `input()`) stalls every other plugin, the health heartbeat, and the SSE bridge. `asyncio.timeout` cannot preempt it. | `core/orchestrator.py:369` |
| Arbitrary code, at any time | `spec.loader.exec_module(module)` on every discovered file. No sandbox, no allowlist, no hash check. | `core/registry.py:44-48` |

`plugins/PLUGIN_DEV.md:212-217` already states the core fact — "Loading a plugin file is
equivalent to executing it." The gap is that nothing in the codebase acts on it.

---

## Critical Pitfalls

### Pitfall 1: Consent Gates the Install; Execution Happens Somewhere Else

**What goes wrong:**
The team ships a well-designed install-time consent prompt, considers the trust problem
solved, and never notices that plugin code executes on paths that never touch the installer.
In this codebase, `PluginRegistry.__init__` calls `_discover_plugins`, which calls
`exec_module` on every matching file. `PluginRegistry` is constructed in **four** places, and
two of them are ordinary read-only user surfaces:

- `core/service.py:143-160` → `list_plugins()` → `shoppybot plugins list` (`core/cli/plugins.py:49`)
  **and** the dashboard root page `GET /` (`web/routes/pages.py:26`)
- `core/service.py:120-134` → `get_analytics()` → `GET /api/analytics` (`web/routes/api.py:171-178`)
- `core/orchestrator.py:812` → the actual bot run

Two consequences. First, "let me just list what's installed before I decide" executes the
thing you were deciding about. Second, `importlib.util.module_from_spec` + `exec_module`
without a `sys.modules` entry means the module body is re-executed **fresh on every call** —
so a plugin gets a new execution on every dashboard page load and every analytics poll, and
can behave differently on the Nth run.

**Why it happens:**
"Install" and "load" feel like the same event when a plugin is a single file you copy into a
directory. They are not. Discovery is decoupled from installation by design (that is what
makes the drop-in framework nice), and that decoupling is exactly what the consent gate has
to survive.

**How to avoid:**
Enforce the trust decision at the **load** boundary, inside `_discover_plugins`, before
`exec_module` — not at the install boundary. Concretely: `_discover_plugins` consults an
install manifest (see Pitfall 2) and refuses to `exec_module` any file that is not (a) a
bundled first-party plugin, or (b) listed in the manifest with a matching content hash and a
recorded consent record. Every construction site inherits the gate for free.

**Warning signs:**
- Consent logic living in `core/cli/plugins.py` rather than `core/registry.py`
- A test that installs a plugin and asserts a prompt, with no test that asserts an
  unmanifested file in `plugins/` is refused
- `shoppybot plugins list` documented as "safe to run first"

**Phase to address:** H1 (install substrate + load-time gate). This is the load-bearing
requirement — everything else in H depends on the gate being at the right boundary.

---

### Pitfall 2: Pinning to a Branch or Tag Instead of an Immutable Reference

**What goes wrong:**
`shoppybot plugins install github.com/someone/shoppybot-plugin-foo` resolves to
`refs/heads/main` (or `v1`). The user reviews the code and consents. Later, the ref moves.
Nothing re-prompts, because from the manager's point of view nothing changed — it is still
"main".

Three real incidents make the case:

- **tj-actions/changed-files (March 2025).** A compromised PAT was used to repoint **350+
  existing git tags** — `v35`, `v44.5.1`, and others — at a malicious commit that dumped CI
  runner secrets into build logs. 23,000+ repositories affected. Repos that pinned to a
  40-character commit SHA were unaffected; repos pinned to tags were compromised without any
  action on their part. *A git tag is mutable. This is the single cleanest proof.*
- **polyfill.io (Feb–June 2024).** The domain and GitHub repo were sold to Funnull. The
  service kept serving from the same URL every site had already vetted, then began injecting
  mobile redirect malware. Reported at 100k+ sites; cside's follow-up count was 490k+. No
  consumer changed a single line of their own code.
- **event-stream (Sept–Nov 2018).** The original author handed npm publish rights to a
  volunteer, `right9ctrl`, who added a malicious transitive dependency in 3.3.6. The payload
  targeted Copay's build specifically and stole wallet keys. Undetected for 2.5 months.

**Why it happens:**
Branch names are the ergonomic default: `install <repo>` reads better than
`install <repo>@a1b2c3d…`. And "pin to a SHA" feels like premature rigor for a hobby tool
until you notice the pinned thing can spend money.

**How to avoid:**
Two independent mechanisms, both required:
1. **Resolve to an immutable ref at install time.** Store the full 40-char commit SHA in the
   install manifest, never a branch or tag. `update` fetches the *new* SHA and shows a diff
   of what changed before re-consent.
2. **Record a content hash of the installed file** (SHA-256 of the exact bytes written to
   disk) and verify it in `_discover_plugins` before `exec_module`. This defends against the
   file being modified on disk after install, which SHA pinning alone does not cover.

**Warning signs:**
- The install manifest schema has a `ref` or `version` string field and no `commit` field
- `update` is implemented as "re-fetch and overwrite" with no diff and no re-consent
- No test that mutating a plugin file on disk causes the loader to refuse it

**Phase to address:** H1 (manifest schema, SHA + content hash), H2 (re-consent on update).

---

### Pitfall 3: Assuming the Repo You Vetted Is the Repo You Update From

**What goes wrong:**
Trust is granted to a *source*, but sources change hands, and the identifier survives the
transfer. Beyond polyfill.io and event-stream (above):

- **The Great Suspender (2020–2021).** Sold by its author to an unidentified buyer in June
  2020; 2M+ users. The new owner shipped tracking plus remote code execution. Google
  force-uninstalled it in Feb 2021.
- **Nano Adblocker / Nano Defender (Oct 2020).** Rights sold; the new owner injected code
  that harvested data from every site the user visited.
- **xz-utils / CVE-2024-3094 (2021–2024).** "Jia Tan" spent ~2 years making legitimate
  contributions, with sockpuppet accounts pressuring the original maintainer, before being
  made co-maintainer and landing an SSH backdoor in 5.6.0. CVSS 10.0. Found by accident.
- **GitHub repojacking.** When a GitHub account is renamed, repo URLs redirect — but the old
  *username* becomes claimable. Checkmarx documented four separate bypasses of GitHub's
  "popular repository namespace retirement" protection, putting 4,000+ packages at risk.
  **`github.com/user/repo` is not a stable identity.**

**Why it happens:**
A URL looks like an identity. It is a lease. Every one of these victims had done the
"review the source before you install" step correctly.

**How to avoid:**
- Store, at install time: the resolved commit SHA, the **repository owner's numeric GitHub
  ID** (not the login string — the ID survives renames, the login does not), the timestamp,
  and the consent record.
- On `update`, if the owner ID has changed, treat it as a **new install**, not an update:
  full re-consent, with the ownership change stated explicitly in the prompt.
- Never auto-update. Ever. See Pitfall 11.
- Say plainly in the disclaimer that the project has no way to detect a repo changing hands
  between updates, so the user is the control.

**Warning signs:**
- The manifest keys installs by URL string
- `update --all` exists
- Any language in the docs implying an installed plugin "stays" trusted

**Phase to address:** H1 (manifest records owner ID), H2 (ownership-change → re-consent).

---

### Pitfall 4: Consent Fatigue — the Prompt That Is Always Accepted

**What goes wrong:**
The prompt ships, it works, and it is meaningless because everyone types `yes` reflexively.
This is measured, not folklore:

- Böhme & Köpsell, *Trained to Accept? A Field Experiment on Consent Dialogs* (CHI 2010,
  80,000 users): consent rates rose the more the dialog **resembled a EULA**. Users are
  habituated by ubiquitous license agreements into blind acceptance. The nicer and more
  formal your legal prose, the less it is read.
- Chrome SSL warning telemetry: ~50% of users who hit an SSL interstitial clicked through in
  **1.7 seconds or less** — consistent with warning fatigue, not with reading.

Making the prompt *scarier* does not fix this; making it *more like a EULA* actively makes it
worse.

**Why it happens:**
The team measures "did we ask?" instead of "did the answer carry information?"

**How to avoid:**
Design for *effortful, specific* consent rather than volume:
- **Type the plugin name, not `y`.** A typed literal (`amazon-clone-plugin`) cannot be
  muscle-memoried the way `y<Enter>` can.
- **Show facts, not prose.** Source repo + owner + commit SHA + file size + line count +
  the specific `core.*` modules the file imports (see Pitfall 12's static scan) + the
  domain_patterns it claims. Three short concrete lines beat three paragraphs of legalese.
- **Prompt rarely.** One consent per install and one per *changed* update. Never per run,
  never per start. A prompt the user sees daily is a prompt they have stopped reading — which
  is precisely why the gate in Pitfall 1 must be a manifest check at load time, not a prompt
  at load time.
- **No `--yes` / `--force` flag on install.** If a CI-friendly non-interactive mode is
  needed, make it require the expected content hash on the command line, so the caller has to
  have looked.

**Warning signs:**
- The prompt accepts `y`, `Y`, or empty-as-yes
- An `--assume-yes` flag appears "for scripting"
- The prompt text is longer than 10 lines
- The prompt fires on every bot start

**Phase to address:** H2 (consent design). Write the exact prompt text as an acceptance
criterion, not as an implementation detail.

---

### Pitfall 5: TOCTOU Between "The User Reviewed It" and "The Code Ran"

**What goes wrong:**
Three distinct gaps, all of which have been exploited in the wild:

1. **Review-then-fetch.** The user reads the file on GitHub's web UI, then runs `install`,
   which fetches whatever the ref points at *now*. Closed by SHA pinning (Pitfall 2).
2. **Fetch-then-load.** The file sits in `plugins/` between install and next start. Anything
   with write access to that directory — including another plugin, since they all run in the
   same process with the same privileges — can rewrite it. Closed by the content-hash check
   at load (Pitfall 2), and by directory permissions (Pitfall 10).
3. **Human review does not see what the interpreter sees.** **GlassWorm** (Oct 2025,
   OpenVSX; resurgent Dec 2025 with 24 extensions; ~73 cloned extensions flagged in April
   2026) hid its payload in Unicode variation selectors (U+FE00–U+FE0F) and Private Use Area
   characters. The malicious logic rendered as *blank space* in editors and in GitHub's diff
   view, while executing normally. Reviewers looking directly at the malicious commit saw
   nothing.

**Why it happens:**
"Review the source" is the intuitive control and it is the one every ecosystem reaches for
first. It is also the one that has failed most often, because it assumes the reviewer's
rendering of the bytes equals the interpreter's.

**How to avoid:**
- Content hash pinned at install, verified at load, before `exec_module`. Non-negotiable.
- At install time, run a **byte-level lint** on the fetched file and refuse (not warn) on:
  any codepoint outside printable ASCII + common whitespace unless it is inside a string
  literal or comment, bidirectional-override characters, variation selectors, and PUA
  characters. This is cheap, deterministic, and catches the exact GlassWorm technique.
- Show the user the **hash and the byte count**, and print a `plugins verify` command that
  re-checks every installed file against its manifest hash so the user can confirm on demand.
- Be honest in the docs that reviewing the source is a weak control and say why.

**Warning signs:**
- No `verify` subcommand
- Install writes the file and never records what it wrote
- Documentation that says "just read the code before you install it" as if that were
  sufficient

**Phase to address:** H1 (hash + byte lint at install/load). The byte lint is ~30 lines and
is the highest value-per-line control in this entire workstream.

---

### Pitfall 6: Name and Domain Shadowing — a Third-Party Plugin Silently Intercepts a Real Retailer

**What goes wrong:**
A third-party plugin declares `domain_patterns = ["amazon.com"]`. It now has a claim on
every Amazon item the user is tracking — with the user's real Amazon session, real checkout
profile, and real CVV prompt flowing through it.

The routing does not defend against this, and the failure is worse than "the wrong plugin
wins": it is **non-deterministic which one wins**.

- `PluginRegistry.route()` returns the **first** match in `self._active_plugins`
  (`core/registry.py:122-125`). First-match wins, no conflict detection.
- `_active_plugins` is appended in iteration order of a **`set`**
  (`core/registry.py:182-191`: `needed: set[RetailerPlugin]`, then `for plugin in needed`).
  Set iteration order over objects follows `id()`-derived hashes, so with two plugins
  claiming `amazon.com` the winner can differ between runs on the same machine.
- `_discover_plugins` iterates `plugins_dir.iterdir()` (`core/registry.py:32`) — filesystem
  order, not a defined precedence, so a filename can influence discovery order too.

There is an exact precedent. In Home Assistant, a HACS custom integration sharing a name with
a built-in **overrides the built-in**, and the maintainers' documented position
(`home-assistant/core#169994`) is that this is *a feature, not a bug*: "users consciously
decide whether to accept risks from third-party code." For a home dashboard that position is
defensible. For a component that logs into a retail account and spends money, it is not.

**Why it happens:**
`domain_patterns` is a plain, unvalidated class attribute, and the ABC was designed on the
assumption that every plugin in the tree had been through a PR review.

**How to avoid:**
- **Reserve the bundled domains.** Maintain an explicit set of first-party
  `domain_patterns` (the 7 in-tree platforms). A third-party plugin whose patterns overlap a
  reserved domain is **refused at load**, with a log line naming the file and the collision.
  This is a hard refusal, not a warning — the user cannot meaningfully adjudicate it at
  runtime.
- **Detect and refuse third-party-vs-third-party collisions** too, with a message telling the
  user to remove one. Never silently pick.
- **Make first-party precedence explicit anyway:** sort `_active_plugins` so bundled plugins
  precede third-party ones, and replace the `set` in `setup_for_items` with an
  order-preserving structure so routing stops being id-dependent. (This is a genuine latent
  bug today, independent of workstream H.)
- **Reserve the filename namespace.** `shopbot_plugin_amazon.py` from a third party must not
  be installable; the manager should namespace third-party files, e.g.
  `shopbot_plugin_ext_<owner>_<name>.py`, so a plugin can never occupy a bundled plugin's
  filename or shadow it via iteration order.

**Warning signs:**
- Two plugins in `plugins list` with overlapping domain patterns and no warning
- Any log line of the form "routing <amazon url> to <unexpected class>"
- `setup_for_items` still building a `set`

**Phase to address:** H3 (capability limits — domain reservation is a capability limit).
The `set`-ordering fix belongs with it. Cross-check with workstream G, which is already
touching the community plugins.

---

### Pitfall 7: Credential Reads at Import Time, Before Any Runtime Gate Could Fire

**What goes wrong:**
A plugin does its work in the module body, not in a method:

```python
# module level -- runs during exec_module, before any object exists
from core.credentials import get_store
from core.session_store import build_session_store
_s = get_store()
_dump = {k: _s.get(k) for k in _s.list()}
_dump["amazon_cookies"] = build_session_store().restore("amazon")
# exfiltrate
```

Every runtime control the team might design — a capability object passed to `__init__`, a
permissions check in `setup()`, an audit hook installed by the orchestrator — is already too
late. `exec_module` has run. This is precisely how **ctx** on PyPI worked (May 2022): the
package collected `os.environ.items()` and base64'd it to a Heroku endpoint, and the
compromise happened because the maintainer's **domain expired** and the attacker
re-registered it to take the account. Same shape: a package everyone already trusted, doing
its harvesting at the earliest possible moment.

For this app the harvest is not "maybe some AWS keys are in the environment." It is a
specific, enumerable list of 20 named secrets plus a shipping address plus live retailer
session cookies.

**Why it happens:**
Python has no notion of "load this module but do not let it do anything yet." Import-time
side effects are a language feature. Teams design their permission model around the object
lifecycle and forget the module lifecycle sits underneath it.

**How to avoid:**
Accept that runtime capability checks cannot defend the import boundary, and put the defense
at the two places that can:
1. **The load gate** (Pitfall 1) — nothing unmanifested executes at all.
2. **Stop making the secrets a process-global import target.** `core.credentials.get_store()`
   returning a full store to any caller is the single biggest lever available at reasonable
   cost. Options, in increasing order of work:
   - **Scoped accessor:** a plugin receives only the secrets for the platform key it declared
     — `AMZ_EMAIL`/`AMZ_PASSWORD` for the Amazon plugin, nothing else. `get_store()` stays
     internal to core. This does not stop a determined attacker (they can still import
     `core.credentials` directly), but it removes the *accidental* and *lazy* paths and makes
     any direct import of `core.credentials` from a third-party file a bright, greppable
     signal.
   - **Static import scan at install** (Pitfall 12) flags direct `core.credentials`,
     `core.session_store`, `core.checkout_profile`, `os.environ`, `subprocess`, `socket`,
     `ctypes`, `eval`/`exec`/`compile`, and `__import__` usage, and surfaces the list in the
     consent prompt. A plugin that needs `core.credentials` directly is a plugin the user
     should be told about by name.
   - **Process isolation** — the real fix, correctly deferred (PROJECT.md already lists it
     as a post-v5.0 candidate). See Pitfall 12.
3. **Document the honest limit** in the disclaimer: on the current architecture, a plugin can
   read every stored secret, and no v5.0 control prevents that.

**Warning signs:**
- Any design document describing "plugin permissions" that does not name `exec_module`
- A capability object passed to `RetailerPlugin.__init__` presented as the security boundary
- `get_store()` still importable from `plugins/`

**Phase to address:** H3 (capability limits). The scoped-accessor refactor is the concrete
deliverable; the static scan feeding the prompt is H1/H2.

---

### Pitfall 8: `place_order_guarded` and `monitor_only` Are Cooperative, Not Enforced

**What goes wrong:**
Two separate holes, both currently open:

1. **`place_order_guarded` is opt-in.** It is a concrete method on the ABC
   (`core/plugin_base.py:151-192`) that a plugin *chooses* to call. Nothing forces
   `auto_buy` to route its final click through it. A third-party plugin's `auto_buy` can call
   `await element.click()` directly, and both `test_mode` and `monitor_only` are irrelevant.
   The v4.0 decision that made this "one enforcement point for all 7 plugins" was correct
   *for in-tree plugins that go through PR review*. It is not an enforcement point for code
   the maintainer never sees.
2. **`monitor_only` only gates the orchestrator's call to `auto_buy`.**
   `core/orchestrator.py:571-580` checks `debug_cfg.monitor_only` and skips `auto_buy`. But
   `check_availability` still runs — it has to, that is the whole point of monitor mode — and
   nothing prevents a plugin from performing the entire purchase inside
   `check_availability`. A user in `monitor_only` believes they are safe from spending money.
   They are not, against a hostile plugin.

Also note the marker interaction: because `place_order_guarded` is where the write-ahead
place-order marker is written (CR-01), a plugin that bypasses the guard also bypasses the
BF-02 double-buy protection. A hostile or merely sloppy plugin can double-buy.

**Why it happens:**
An ABC's concrete methods are conveniences. They read like a framework guarantee because
they live on the base class, but Python has no `final` and no way to force a subclass through
a chokepoint.

**How to avoid:**
- **Move the guard from the callee to the caller.** The orchestrator, not the plugin, owns
  the safety decision. Keep `place_order_guarded` for in-tree use, but add an
  orchestrator-level entry guard that refuses to invoke a **third-party** plugin's `auto_buy`
  at all when `monitor_only` is set — which workstream G is already building for the
  community plugins. Extend it to cover third-party installs by default.
- **Refuse `auto_buy` for third-party plugins unless separately opted in.** Installing a
  plugin and *arming it to spend money* should be two decisions, not one. Default a
  third-party plugin to monitor-only regardless of the global `monitor_only` setting, and
  require an explicit `shoppybot plugins trust-checkout <name>` (typed name, same pattern as
  Pitfall 4) to enable purchases. This is the single highest-leverage control in the whole
  workstream: it decouples "I want stock alerts for this retailer" from "I authorize this
  stranger's code to charge my card."
- **State in the disclaimer** that a third-party plugin can bypass `monitor_only` from within
  `check_availability`, so users do not treat monitor-only as a containment boundary.
- **Test it:** a test plugin whose `check_availability` attempts a purchase, asserting the
  per-plugin checkout flag blocks it.

**Warning signs:**
- The per-plugin checkout permission defaults to enabled
- Any documentation that describes `monitor_only` as "safe"
- `plugins install` and "this plugin may buy things" are the same prompt

**Phase to address:** H3 (capability limits), coordinated with workstream G's
`monitor_only` entry guard so the two guards are one mechanism, not two that can diverge.
PROJECT.md's sequencing note already flags G and H for a shared post-verification review;
this is the specific thing that review should check.

---

### Pitfall 9: The Plugin That Never Returns — an Event-Loop Stall Takes Down Everything

**What goes wrong:**
`core/orchestrator.py:369` wraps each item check in `async with asyncio.timeout(item_timeout)`.
That is a **cooperative** cancellation: it can only fire when the coroutine yields control.
A plugin that does any of the following stalls the entire process, and the timeout never
fires:

- `time.sleep(...)` inside an `async def`
- a synchronous `requests.get(...)` / `urllib` call
- `input()` (the legacy Amazon flow already uses blocking `input()` for OTP — a plugin author
  copying that pattern reproduces the hazard by accident, not malice)
- a tight CPU loop
- `while True: pass` with no `await`

Consequences on this specific architecture: every *other* plugin's poll coroutine stops, the
health heartbeat stops updating (so `/api/status` reports "running" on a dead loop, or the
supervisor restarts things that are not broken), the SSE `_poll_loop` producer stalls so the
dashboard freezes, the write-queue drain stops, and SIGTERM teardown cannot run — orphaning
Chrome processes, which v4.0 explicitly fixed.

The same code can also stall the process at the *other* end: `exec_module` at discovery time
is fully synchronous. A plugin whose module body blocks stalls `GET /` (via `list_plugins`)
and `/api/analytics` — both offloaded to `asyncio.to_thread`, so the effect is thread-pool
exhaustion rather than a loop stall, which is quieter and harder to diagnose.

**Why it happens:**
`async def` looks like it makes code cancellable. It does not. The distinction between
"awaitable" and "preemptible" is not obvious, and no lint the project currently runs would
catch it (workstream F is only now adopting a linter).

**How to avoid:**
- **A hard wall-clock watchdog independent of the event loop.** A monitor thread that records
  the last heartbeat per plugin and, on exceeding a hard ceiling (e.g. 3× `item_timeout_secs`),
  logs loudly, parks the plugin, and — since a stalled loop cannot cooperate — takes the
  process-level action the operator configured (alert + exit is honest; silent hang is not).
  The existing health surface already tracks per-plugin heartbeats; this is an extension, not
  a new subsystem.
- **Bound the import itself.** Run `exec_module` for third-party plugins in a subprocess or a
  dedicated thread with a hard timeout at *install* time, as a smoke test, and refuse to
  install a plugin whose module body does not return in a couple of seconds. This catches
  both the accident and the trivially-hostile case before it ever reaches a run.
- **Add a lint rule / documented ban** in PLUGIN_DEV.md on `time.sleep`, `requests`,
  `input()`, and any sync I/O inside plugin coroutines, with the async replacements named.
- **Park, do not restart, on repeated timeouts.** A plugin that times out N times in a row
  should be parked with a `plugin_parked` notification (the mechanism already exists) rather
  than restarted forever.

**Warning signs:**
- Health heartbeats flat while the process is alive
- Dashboard SSE shows "Reconnecting" while the CLI shows the bot running
- `item timeout` warnings appearing for *every* plugin at once (a genuine per-plugin timeout
  affects one plugin; a loop stall affects all of them)
- Chrome processes surviving a `Ctrl-C`

**Phase to address:** H3 (runtime containment) plus the install-time smoke test in H1. Reuse
the existing health/heartbeat surface rather than inventing a second one.

---

### Pitfall 10: Mutating the Plugin Set While a Browser Session Is Live

**What goes wrong:**
`shoppybot plugins remove foo` or `plugins update foo` runs while the bot is mid-run:

- **Remove while live.** Deleting the `.py` file does nothing to the already-imported module
  object, the constructed plugin instance in `_all_plugins`, its running poll coroutine, or
  its Chrome subprocess. The user believes the plugin is gone. It is still polling, still
  holding an authenticated session, still able to buy. "Uninstalled" is a lie until the
  process restarts.
- **Update while live.** New bytes on disk, old code in memory. Then some *other* surface —
  `GET /`, `/api/analytics` — constructs a fresh `PluginRegistry` and `exec_module`s the
  **new** file. Now two versions of the plugin exist in one process, with two Chrome
  instances, two claims on the same domain, and a non-deterministic winner (Pitfall 6). This
  is a plausible route to a genuine double-buy.
- **Remove while the checkout is mid-flight.** Between the write-ahead place-order marker and
  the confirmation capture, a removal that kills the browser leaves the item permanently
  latched as `_PossiblyPlaced` with no confirmation — exactly the state BF-02 was built to
  make recoverable, now triggered by an ordinary user action.
- **Where the files live.** `plugins_dir` is `Path(__file__).parent.parent / "plugins"`
  (`core/orchestrator.py:802`, `core/service.py:133`, `:159`) — i.e. **inside the installed
  package**. Installing into it means writing into `site-packages`: needs elevation on some
  systems, gets wiped on `pip install --upgrade`, and pollutes the wheel's own file list.
  SEED-003 already flags "user-writable plugin directory" as a gap; this is why it is a
  correctness issue and not just tidiness.

**Why it happens:**
`install`/`update`/`remove` are modeled on package managers, which assume the target is not
running. This target is always running.

**How to avoid:**
- **Mutations are staged, not live.** `install`/`update`/`remove` write to the manifest and
  the staging area, then report: *"Applied. Restart the bot for this to take effect."* If the
  bot is running, say so explicitly and name the running plugin.
- **Refuse destructive mutation of an active plugin outright** unless `--force` is given, and
  make `--force` say what it will do (kill browser, abandon session).
- **Hard-block mutation during a checkout attempt.** The `_PossiblyPlaced` / place-order
  marker state already exists in the DB; check it and refuse.
- **Two directories, not one.** Bundled first-party plugins stay in the package. Third-party
  plugins live in a user-writable directory under `core.paths.data_dir()` (which already
  honours `SHOPBOT_DATA_DIR`), alongside the manifest. `_discover_plugins` scans both, applies
  the trust gate only to the second, and gives the first precedence in routing (Pitfall 6).
- **Lock down the third-party directory's permissions** at creation (owner-only write) and
  warn if they are wider. A world-writable plugin directory is arbitrary code execution for
  anything on the box.

**Warning signs:**
- `remove` reports success with no restart notice
- No check of `BotService` running state in the plugins CLI
- The installer writes anywhere under `site-packages`

**Phase to address:** H1 (two-directory layout, permissions, manifest location), H5
(CLI semantics: staged mutation, running-state checks, restart messaging).

---

### Pitfall 11: Auto-Update — Handing Over the Only Control That Was Working

**What goes wrong:**
An `update --all` or a background update check turns every one of the incidents above from
"a thing the user could have caught" into "a thing that happened to the user overnight."
GlassWorm's own analysis names this: VS Code extensions auto-update by default, which is
precisely why the worm spread "silently, widely, and fast." The GlassWorm v2 cluster went
further and shipped **sleeper packages** — 73 cloned extensions, only 6 initially malicious,
the rest benign until a later update. A clean review at install time is not evidence about
the next version.

**Why it happens:**
Auto-update is unambiguously correct for *security patches* in software you control. It gets
copied into ecosystems where the thing being updated is the untrusted part.

**How to avoid:**
- **No auto-update. No background update check that can install.** A `plugins outdated`
  command that only *reports* is fine and useful.
- **`update` re-consents** whenever the commit SHA changes, showing what changed
  (files touched, line delta, new imports flagged by the static scan, and any change in the
  claimed `domain_patterns` or checkout capability).
- **A capability escalation forces a fresh full consent**, not an update prompt: if the new
  version imports `core.credentials` and the old one did not, that is a new install
  decision.

**Warning signs:**
- A scheduler, timer, or startup hook that calls the update path
- `update` with no diff output
- Any code path where a plugin's bytes change without a user keystroke

**Phase to address:** H2 (update = re-consent), H5 (CLI: `outdated` reports, never installs).

---

### Pitfall 12: Sandboxing Theatre — Shipping a Control That Reads as Protection and Is Not

This is the pitfall most likely to actually happen to this team, because the in-process
Python sandbox is easy to build, demos well, and is worthless.

**What does not work, and why. All of it is upstream-documented, not opinion:**

| "Control" | Why it fails | Source |
|-----------|--------------|--------|
| Restricted `__builtins__` / a curated globals dict passed to `exec` | Object-graph traversal reaches everything. `().__class__.__base__.__subclasses__()` enumerates every loaded class, including `subprocess.Popen` and file-opening types, by numeric index — no `import`, no `open`, no blocked keyword ever appears in the payload. Any function object leaks a real `__globals__` via `__func__.__globals__`. | Documented escape technique, multiple independent write-ups; also one of the fundamental breaks Victor Stinner cites |
| `RestrictedPython` | Its own README states it "is **not** a sandbox system or a secured environment"; it is for defining a trusted environment. Attribute instrumentation (`_getattr_`) is bypassable via `__func__.__globals__`. | RestrictedPython README (zopefoundation) |
| A hand-rolled sandbox (the pysandbox path) | Victor Stinner spent 3 years on pysandbox and concluded it is **"broken by design."** The repo's own headline now reads: *"WARNING: pysandbox is BROKEN BY DESIGN, please move to a new sandboxing solution (run python in a sandbox, not the opposite!)."* Named breaks include mutating `__builtins__`, `compile()` reaching arbitrary files, and unwinding a traceback object's frames to reach globals. CPython's `rexec` and `Bastion` were removed from the stdlib for the same reason. | python-dev, Nov 2013; LWN "The failure of pysandbox" |
| `sys.addaudithook` (PEP 578) | PEP 578 says it directly: *"This is not sandboxing, as this proposal does not attempt to prevent malicious behavior."* CPython's `sys` docs add that security-sensitive hooks must be installed via the **C API** `PySys_AddAuditHook()` *before interpreter init*, and that "any modules allowing arbitrary memory modification (such as `ctypes`) should be completely removed or closely monitored." A pure-Python hook installed after startup is advisory. | PEP 578; `docs.python.org/3/library/sys.html` |
| Import hooks / a custom meta-path finder | Plugin code runs in the same interpreter with the same rights, and can mutate `sys.meta_path`, `sys.modules`, and `builtins` — the very structures the hook depends on. PEP 578 makes the general form of this point: an attacker able to shadow `sys` is already running arbitrary code. | PEP 578 |
| AST scanning at install to prove safety | Catches lazy attacks, proves nothing. Defeated by `getattr(__import__("o"+"s"), "system")`, base64/marshal, and — as GlassWorm demonstrated in production — payloads encoded in invisible Unicode that neither the reviewer nor a naive tokenizer sees. | GlassWorm analyses (Truesec, Endor Labs) |

**The rule:** run Python in a sandbox, never a sandbox in Python.

**What genuinely helps, at costs this project can actually pay:**

Ordered by value per unit of effort. The first four are cheap and belong in v5.0.

1. **The load-time trust gate (Pitfall 1) + content hash (Pitfall 2).** This is not a
   sandbox and does not pretend to be. It is provenance: you know exactly which bytes ran,
   and nothing runs that the user did not choose. It defeats every incident in the evidence
   table that relied on *substitution* rather than on the user's own bad choice. Cost: small.
2. **The byte-level Unicode lint (Pitfall 5).** Deterministic, no false-negative claims
   needed, directly counters a technique in active use. Cost: ~30 lines.
3. **Capability *reduction* rather than capability *enforcement* (Pitfalls 7, 8).** Stop
   exporting the credential store as a process global; default third-party plugins to no
   checkout. Be explicit that this raises the bar against carelessness and opportunism, not
   against a determined attacker. Cost: a focused refactor.
4. **An AST import scan whose output feeds the *consent prompt*, not a pass/fail gate.**
   Framed as "this plugin imports `subprocess`, `socket`, and `core.credentials`" it is
   honest and useful. Framed as "scanned — safe" it is theatre and actively harmful. Cost:
   small. **The framing is the requirement.**
5. **Refuse to install plugin dependencies.** See Pitfall 14.
6. **Process isolation** — a subprocess per plugin with a narrow RPC surface, running under a
   reduced-privilege account, plus OS containment (a separate user + `bubblewrap`/`firejail`
   on Linux, a restricted token / Job object on Windows). This is the only thing on the list
   that is a real security boundary, and cross-platform it is expensive: every plugin call
   becomes IPC, the shared `nodriver` browser model has to be rethought, and debuggability
   drops. PROJECT.md already lists it as a post-v5.0 candidate. **That deferral is correct —
   provided v5.0 does not describe anything shipped in its place as isolation.**
7. **Running the whole app as a low-privilege user in a container** is the cheapest real
   containment available today and requires zero code. It should be a *documented deployment
   recommendation* in H4, because it is the only advice in the disclaimer that actually
   reduces blast radius.

**Warning signs of theatre:**
- Any variable, function, or docstring in the delivered code containing the word "sandbox"
- A permissions/capability model whose enforcement point runs after `exec_module`
- Release notes claiming plugins are "scanned", "isolated", "restricted", or "safe"
- A control whose test suite only proves it stops the naive case

**Phase to address:** H3 (build only the controls that survive scrutiny), H4 (documentation
must not overclaim). Add an explicit review criterion: *for each shipped control, state in
one sentence what it does not stop.*

---

### Pitfall 13: The Disclaimer That Does Not Do Its Job

**What goes wrong:**
The disclaimer exists and fails anyway, in five distinguishable ways:

1. **Buried.** It lives in `SECURITY.md` or a `docs/` page. The user who ran
   `plugins install` never opened it. Note this project's specific version of this problem:
   `SECURITY.md:50-52` requires a documented per-platform risk assessment *before a plugin is
   merged* — a real gate, applied at PR time. A third-party install **bypasses it entirely**.
   The security policy currently describes a control that will not exist for the majority of
   plugins the moment workstream H ships, and SECURITY.md does not say so.
2. **No acknowledgement captured.** Nothing records that the user saw it, when, or for
   which plugin. There is no artifact to point at afterward, which is most of the point.
3. **Contradicted by the surrounding language.** The moment the project says "curated",
   "verified", "trusted", "official registry", or "community-approved" anywhere — README,
   wiki, the registry page, a release note — the disclaimer is arguing with the marketing and
   losing. This is a live risk here: `docs/PLUGIN_REGISTRY.md` is a 9-column registry with a
   status column, and REG-01 renders it to a wiki page. A table on the project's own wiki
   listing a third-party plugin **reads as endorsement** regardless of what the footer says.
4. **Endorsement by inclusion.** Being *listed* is a signal. Obsidian handles this by
   pairing a curated list with unusually blunt copy — plugins "can access files on your
   computer", "can connect to internet", "can install additional programs", and *"we
   recommend that you perform an independent security audit"* — and by shipping
   **Restricted Mode on by default**, so third-party code is off until the user turns it on.
   The default posture carries the message that the prose cannot.
5. **Written as a EULA.** Per Böhme & Köpsell (Pitfall 4), the more it reads like a license
   agreement, the more reliably it is accepted unread. A wall of legal prose is a *worse*
   disclaimer than four blunt sentences.

**Why it happens:**
Disclaimers are written to protect the maintainer and are then assumed to also inform the
user. Those are different documents with different constraints.

**How to avoid:**
- **Two artifacts, not one.** (a) A short, blunt, non-legal *operational warning* at the
  point of decision — 4 to 6 lines, in the install prompt and in `plugins list` output next
  to every third-party entry. (b) The formal liability language in `SECURITY.md`, README, and
  LICENSE (workstream C is adding a LICENSE; its warranty disclaimer is part of this story).
- **Capture the acknowledgement.** Store in the install manifest: plugin name, source repo,
  owner ID, commit SHA, content hash, the disclaimer text **version**, and an ISO timestamp.
  Bump the version string when the wording changes, and re-prompt on a version bump. This is
  the artifact that makes the disclaimer a decision on the record rather than a file in the
  repo.
- **Amend `SECURITY.md` explicitly.** Add a section stating that the per-platform risk
  assessment applies to *merged* plugins only, that third-party installs receive no review of
  any kind, and that the project has no mechanism to revoke a plugin already installed on a
  user's machine. Naming the gap is the whole point of thread 2 of SEED-003.
- **Audit the vocabulary.** Grep the repo and wiki for `curated`, `verified`, `trusted`,
  `approved`, `official`, `safe` in any plugin context and fix each hit. Add it to the CI
  guard set the project already uses for credential leaks — a cheap, mechanical, durable
  control.
- **Mark provenance in every listing.** `plugins list` must visually distinguish bundled
  from third-party. The registry table needs an unmissable per-row "third-party — not
  reviewed by this project" column, not a footnote.
- **Default posture carries the message.** Third-party plugins default to monitor-only
  (Pitfall 8). That default communicates the risk more effectively than any paragraph.

**Warning signs:**
- The word "curated" anywhere near the registry
- An install flow with no persisted acknowledgement record
- `SECURITY.md` unchanged after workstream H ships
- The disclaimer is longer than the install prompt

**Phase to address:** H4 (disclaimer, SECURITY.md amendment, registry provenance columns,
vocabulary CI guard). H2 records the acknowledgement.

**Confidence note:** MEDIUM. This is drawn from comparable projects' published practice and
consent research, not legal advice. If the goal is genuine liability protection rather than
honest user communication, get the LICENSE and disclaimer wording reviewed by someone
qualified. The *engineering* recommendations above stand on their own either way.

---

### Pitfall 14: Installing the Plugin's Dependencies Is a Second, Unmodelled Execution Channel

**What goes wrong:**
A plugin declares `requests`, or `some-obscure-scraper`, and the manager helpfully
`pip install`s it. Everything the workstream built about pinning, hashing, and consent now
applies to one file and not to the transitive tree that file pulls in.

Worse, `pip` on a **source distribution executes `setup.py` during resolution** — before
anything is installed, with the user's full privileges. That is the mechanism behind a long
list of PyPI incidents, and it is why "we only install one small file" stops being true the
moment dependency installation is added.

The scale of what this opens: the **Shai-Hulud** npm worm (Sept 2025, ~500 packages;
resurgent Nov 2025 at 700+ packages and 25,000+ malicious repos) propagated entirely through
install-time lifecycle scripts, ran **TruffleHog** on the victim machine to find secrets, and
republished itself using the victim's own publish token. Python's equivalent execution
surface is `setup.py`.

**Why it happens:**
"Plugins need dependencies" is a genuine ergonomic pressure, and every mature plugin
ecosystem eventually gives in to it.

**How to avoid:**
- **v5.0 position: the manager does not install dependencies. At all.** A plugin may import
  only the standard library plus what ShopPyBot already depends on. If a plugin needs
  something else, it fails to load with a message naming the missing module, and the *user*
  installs it deliberately, outside the tool. This is a real constraint on plugin authors and
  it is the right trade at this stage — record it as an explicit decision in PROJECT.md, not
  as an omission.
- **Enforce it at install:** the AST scan (Pitfall 12, item 4) already extracts the import
  list; refuse any top-level import outside the allowed set, and show the list in the prompt.
- **If dependency installation is ever added:** `--only-binary=:all:` (no sdists, so no
  `setup.py` execution) **plus** `--require-hashes` **plus** `--no-deps` with an explicit
  fully-pinned hash list in the plugin manifest. Anything less re-opens the whole channel.

**Warning signs:**
- A `requirements` or `dependencies` key appearing in the plugin manifest schema
- Any `pip`/`subprocess` call in the install path
- A plugin doc that says "add your deps to requirements.txt"

**Phase to address:** H1 (import allowlist at install), H4 (document the constraint and the
reason in PLUGIN_DEV.md).

---

## Moderate Pitfalls

### Pitfall 15: Typosquatting and Homoglyph Plugin Names

**What goes wrong:**
`shopbot-plugin-bestbuy` vs `shopbot-plugin-best-buy` vs `shopbot-plugin-bestbuy-official`;
Cyrillic `а` in `аmazon`. The npm/PyPI record here is long — jeIlyfish (capital I for l),
python3-dateutil, `colourama` — and the VS Code marketplace variant adds **inflated install
counts**: the GlassWorm clones faked popularity metrics so they surfaced *next to* the
legitimate extension in search, which is where most installs actually come from. The
"73 cloned extensions" cluster of April 2026 was near-exact clones of real ones.

**Why it happens:**
A registry sorts and searches by name, and names are the only affordance users have.

**How to avoid:**
- **Registry keys on `owner_id/repo`, never on a display name.** Two entries may share a
  display name; they can never share the key.
- **The consent prompt leads with the source** (`github.com/<owner>/<repo>` and the owner ID),
  not the friendly name.
- **Reject non-ASCII in plugin names and filenames** outright. Same lint as Pitfall 5.
- **Flag near-collisions at registry-add time** — Levenshtein distance ≤ 2 against any
  existing entry or any bundled platform name gets a manual look before the row is merged.
- **Do not display an install or popularity count.** The project cannot measure it honestly
  and, per GlassWorm, a fakeable popularity signal is worse than no signal.

**Warning signs:**
- Registry rows keyed on name
- Non-ASCII accepted anywhere in a plugin identifier
- A "downloads" or "stars" column in the registry table

**Phase to address:** H4 (registry schema + review checklist), H2 (prompt leads with source).

---

### Pitfall 16: Version Skew, and Who Gets the Bug Report

**What goes wrong:**
Core changes. Third-party plugins written against the old contract break. The user does not
know the plugin is third-party — from their seat it is "ShopPyBot broke" — and the issue
lands in this repo's tracker. With one maintainer, that queue is the thing that kills the
ecosystem, not any security incident.

The mechanism is already primed here: `PLUGIN_API_VERSION = 2` exists at
`core/plugin_base.py:15` and **is enforced nowhere**. The only reference outside docstrings is
a test asserting the constant equals 2 (`tests/test_plugin_base.py:31`). A v1-era plugin loads
today and fails at some arbitrary later moment with an `AttributeError` deep in a checkout
flow — the worst possible place and time.

**Why it happens:**
The API version was introduced as documentation of intent during in-tree development, where
everything is updated together. Third-party distribution is what turns it into a runtime
contract.

**How to avoid:**
- **Enforce the version at load, refuse on mismatch.** Require every plugin to declare
  `plugin_api_version` as a class attribute; `__init_subclass__` already exists at
  `core/plugin_base.py:82-92` as the natural hook (it validates `difficulty` there today).
  A mismatch raises at import, which `_discover_plugins` already catches, logs, and skips
  (`core/registry.py:49-51`) — so the failure mode is "plugin declines to load with a clear
  message", which is exactly right. **Bundled plugins must declare it too**, or the rule will
  rot.
- **Tag every log line with plugin provenance.** The `[plugin]` log tag shipped in v4.2
  (FC-01); extend it so third-party plugins are visibly marked (e.g. `[ext:foo]`) in logs, in
  the dashboard filter, and in the health cards. A user pasting a log into an issue then
  hands the maintainer the answer for free.
- **A support policy, stated once and applied mechanically.** Home Assistant's is the model:
  core logs a startup warning naming each custom integration as untested, and triage asks for
  them to be disabled before a bug is accepted. Adopt the same two moves: (a) a startup
  WARNING per third-party plugin naming it; (b) a required checkbox in
  `.github/ISSUE_TEMPLATE` — *"I have reproduced this with all third-party plugins removed"* —
  and a saved reply that closes reports that skip it.
- **`shoppybot plugins list` prints the API version each plugin declares** next to the core's
  current value, so skew is visible before it bites.
- **Diagnostics output includes the third-party manifest**, so the first ask in any issue is
  one command.

**Warning signs:**
- Issues arriving with stack traces through `shopbot_plugin_*` files nobody recognises
- No third-party marker in the log tag
- `PLUGIN_API_VERSION` still enforced only by an equality assertion in a test

**Phase to address:** H2 (`PLUGIN_API_VERSION` enforcement — SEED-003 already names this as a
gap), H4 (support policy, issue template, provenance in logs).

---

### Pitfall 17: Removal Is Not Revocation

**What goes wrong:**
The user notices something wrong, runs `plugins remove evil`, and believes it is over. It is
not. Whatever the plugin read is gone: retailer passwords, the 2captcha key, proxy
credentials, the shipping and billing address, and the session cookies — which grant account
access **without** the password, so a password reset alone does not close it. Nothing in the
uninstall path rotates or invalidates anything. Compare the standard incident guidance from
ctx and Shai-Hulud: every affected party was told to *rotate credentials*, because removing
the package was never the remediation.

**Why it happens:**
Uninstall is modeled as the inverse of install. Compromise is not reversible by inverting the
install.

**How to avoid:**
- **`plugins remove` prints a remediation checklist**, not a success message: rotate every
  retailer password, rotate the 2captcha key, rotate proxy credentials, log out all sessions
  at each retailer, delete the local session store, review recent orders and payment methods
  on each account.
- **Ship the tooling that makes the checklist actionable:** a session-store purge command and
  a `credentials` listing that names exactly which keys a given plugin's platform touched.
- **Say it in the disclaimer up front** — the point at which the user decides is the only
  point where knowing "removal will not undo this" changes behaviour.

**Warning signs:**
- `remove` prints "Removed." and nothing else
- No session-purge command exists
- The disclaimer does not mention revocation

**Phase to address:** H5 (CLI remediation output), H4 (disclaimer wording), tooling in H3.

---

## Real-Incident Evidence: What Each Control Would and Would Not Have Stopped

Every incident below is real and cited. "Control" columns refer to the controls proposed in
this document.

| Incident | What the attack actually was | SHA + hash pinning | Load-time trust gate | Static/Unicode scan | Per-plugin checkout gate | Process isolation |
|---|---|---|---|---|---|---|
| **event-stream** (npm, Sept–Nov 2018) | Original author granted publish rights to a volunteer; malicious transitive dep added in 3.3.6; targeted Copay's build; stole BTC wallet keys | **Yes** — a pinned SHA never advances to 3.3.6 | Partial — gate fires on update | Partial — payload was obfuscated; flagged as suspicious, not proven malicious | No | Partial |
| **ctx** (PyPI, May 2022) | Maintainer's **domain expired** → account takeover → replaced package harvested `os.environ` at object construction and exfiltrated to Heroku | **Yes** | **Yes** | **Yes** — a bare `os.environ` sweep is a trivially detectable pattern | No — it stole secrets, not money | **Yes** |
| **polyfill.io** (Feb–June 2024) | Domain + GitHub repo **sold to Funnull**; same URL began serving mobile redirect malware; 100k–490k sites | **Yes** — content hash mismatch on every fetch | **Yes** — owner-ID change forces re-consent | Partial — payload was generated dynamically server-side | No | No — it ran in the victim's browser |
| **tj-actions/changed-files** (March 2025) | Compromised PAT repointed **350+ existing tags** at a malicious commit; dumped CI secrets to logs; 23,000+ repos | **Yes** — the definitive proof for SHA pinning | **Yes** | Partial | No | Partial |
| **xz-utils / CVE-2024-3094** (2021–2024) | Two-year social-engineering campaign; "Jia Tan" became co-maintainer, landed an SSH backdoor in 5.6.0; CVSS 10.0 | No — the malicious commit *is* the pinned SHA | No — consent was legitimately given | No — payload hid in binary test fixtures, invisible to source review | No | No |
| **Shai-Hulud** (npm, Sept + Nov 2025) | Self-propagating worm via install-lifecycle scripts; ran TruffleHog to harvest secrets; republished itself with the victim's token; 700+ packages, 25,000+ malicious repos | Partial | Partial | Partial | No | **Yes** for the local machine |
| **Fractureiser** (Minecraft/CurseForge + BukkitDev, June 2023) | Compromised uploader accounts injected a stage-0 loader into mods; **self-propagated into every `.jar` on the filesystem**; stole browser cookies and launcher credentials; hijacked clipboard crypto addresses | **Yes** for the initial install | **Yes** | Partial | No | **Yes** — filesystem-wide self-propagation is exactly what isolation blocks |
| **GlassWorm** (OpenVSX/VS Code, Oct 2025 → Apr 2026) | Payload hidden in **invisible Unicode** (variation selectors, PUA) — invisible in editors and GitHub diffs; harvested npm/GitHub/OpenVSX credentials, drained wallets; spread via **auto-update**; later waves used **sleeper** clones and **faked install counts** | Partial — sleepers weaponise on update | **Yes** — no auto-update means no silent weaponisation | **Yes** — the byte-level lint is the direct counter | No | **Yes** |
| **The Great Suspender** (Chrome, 2020–2021) | Extension with 2M+ users **sold**; new owner added tracking + remote code execution; force-uninstalled by Google | **Yes** | **Yes** — owner change → re-consent | Partial | No | Partial |
| **Nano Adblocker/Defender** (Chrome, Oct 2020) | Rights **sold**; new owner injected data-harvesting into every visited page | **Yes** | **Yes** | Partial | No | Partial |
| **HACS + custom integrations** (Home Assistant, Jan 2021) | Directory traversal via an **unauthenticated** webview in HACS and other custom integrations; read any file the HA process could — "including any credential that you might have stored" | No | No | No | No | **Yes** |
| **Repojacking** (GitHub, ongoing) | Renamed account frees the old username; attacker claims it and serves a different repo at the previously-trusted path; four documented bypasses of GitHub's namespace-retirement protection; 4,000+ packages at risk | **Yes** — SHA + hash catch the substitution | **Yes** — owner ID is not the login string | Partial | No | No |

**The honest reading of this table:** SHA + content-hash pinning and the load-time gate stop
most of it, cost little, and belong in v5.0. They do **not** stop a genuinely malicious author
(xz) or a compromise of the code you actually consented to. Nothing short of process
isolation does, and process isolation would not have stopped xz either — it would only have
bounded the damage. This is the case for the disclaimer being a real, acknowledged decision
rather than a formality.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Consent at install only, not at load | Simple; one code path in the CLI | Every non-install surface (`GET /`, `/api/analytics`, `plugins list`) executes plugin code ungated. Retrofitting means touching the registry and all four construction sites anyway. | **Never** — build the gate in `_discover_plugins` from day one |
| Pin to branch, "SHA later" | `install <repo>` is a nicer command | The manifest schema has to change, existing installs need migration, and until then every install is a tj-actions waiting to happen | **Never** — the schema is the cheap part; do it once |
| Install into the existing `plugins/` dir inside the package | Zero new path handling | Breaks on `pip install --upgrade`, needs elevation on some systems, mixes trusted and untrusted files in one namespace with one precedence, pollutes the wheel manifest | **Never** — workstream B is already fixing package data; land the split with it |
| AST scan presented as a safety verdict | Feels like real security; demos well | Users stop reading the disclaimer because "it was scanned". First bypass is a credibility event, and the credibility was the actual control. | Only if its output is framed as *disclosure* ("imports: subprocess, socket") and never as a verdict |
| Third-party plugins can buy by default | One fewer command; matches bundled-plugin behaviour | The gap between "I wanted stock alerts" and "a stranger's code charged my card" collapses to a single `y` keypress | **Never** — this is the single cheapest high-value control in the workstream |
| `update --all` for convenience | Nice CLI ergonomics | Converts every trust-transfer incident from catchable to overnight; GlassWorm's stated spread mechanism | **Never** |
| Ship a plugin manager without touching `SECURITY.md` | Faster to ship | `SECURITY.md:50-52` actively describes a review gate that most plugins will now bypass. A stale security policy is worse than none. | **Never** — it is one paragraph |
| Defer `PLUGIN_API_VERSION` enforcement | It has not caused a problem in-tree | Version skew surfaces as an `AttributeError` mid-checkout instead of a clear refusal at load; support burden lands on one maintainer | Only while every plugin is in-tree. Third-party distribution ends that condition. |
| Defer process isolation | Enormous saving; correctly scoped out | The credential store and checkout path stay reachable from any plugin. Acceptable **only** if v5.0 never describes anything as isolation and the disclaimer says this plainly. | **Yes** — this is the right call, on the record (SEED-003 asks for exactly this) |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| GitHub as the plugin source | Keying installs on `owner/repo` strings | Key on the **numeric owner ID** + repo ID; a rename or transfer changes the ID relationship and must force re-consent (repojacking) |
| GitHub raw fetch | `raw.githubusercontent.com/<owner>/<repo>/main/<file>` | `.../<40-char-sha>/<file>`; verify SHA-256 of the received bytes against what the manifest recorded |
| GitHub API rate limits | Unauthenticated fetch works in dev, 403s under load | Handle 403/429 explicitly with an actionable message; never silently fall back to a cached or alternate source |
| The machine-readable registry (REG-01 successor) | Fetching it over the network at runtime, or treating it as a trust root | Registry is **discovery only**, never authorization. A listed plugin gets no more trust than an unlisted one. Ship it as a static JSON file with a documented schema; if fetched, cache and never auto-act on it. |
| `pip` for plugin dependencies | `pip install <dep>` from the manager | Do not install dependencies (Pitfall 14). If ever added: `--only-binary=:all: --require-hashes --no-deps` with fully pinned hashes |
| `importlib` | `spec.loader.exec_module()` with no `sys.modules` registration → silent re-execution per call | Register in `sys.modules` under a namespaced key so re-import is explicit and observable, or cache the discovered classes on the service; either way, know how many times plugin code runs |
| `nodriver` / Chrome | Assuming `remove` reclaims the browser | An active plugin owns a Chrome subprocess and an authenticated session; mutation must be staged for restart or explicitly forced with teardown |
| Discord / notification fan-out | Plugin-controlled strings reaching a webhook unescaped | Third-party plugin names and messages are untrusted input to the notifier; escape and length-cap them. v5.0 workstream D is already fixing empty-`url` embeds on `plugin_parked` — same surface |
| The dashboard | Treating `GET /` and `/api/analytics` as read-only | Both trigger a full plugin re-import today. Either make discovery a cached, explicit operation, or accept and document that any HTTP hit re-executes plugin code |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| `get_store()` importable from `plugins/` | Any plugin dumps all 20 secrets in 2 lines, at import time | Scoped per-platform credential accessor; keep `get_store()` internal to core; flag direct `core.credentials` imports in the consent prompt |
| `build_session_store().restore(key)` reachable from a plugin | Authenticated retailer sessions exfiltrated — account takeover with no password needed, unaffected by a password reset | Same scoping; add session-purge tooling to the removal remediation path |
| World-writable / package-internal plugin directory | Anything on the box that can write a file gets code execution on next start | Owner-only permissions on the user plugin dir at creation; warn on wider modes; keep it out of `site-packages` |
| No content-hash verification at load | The reviewed file and the executed file can differ (TOCTOU) | SHA-256 recorded at install, verified before `exec_module`, plus a `plugins verify` command |
| Non-ASCII accepted in plugin source | GlassWorm-style invisible payloads survive human review and GitHub diffs | Byte-level lint refusing variation selectors, PUA, and bidi overrides outside strings/comments |
| Auto-update | Silent weaponisation of a sleeper plugin | No auto-update; `outdated` reports only; SHA change forces re-consent |
| Third-party plugin armed for checkout by default | A stranger's code clicks Place Order with a saved payment method | Separate, explicitly-typed opt-in per plugin; default deny regardless of the global `monitor_only` |
| `place_order_guarded` treated as an enforcement boundary | Every safety property (monitor-only, test-mode, BF-02 marker) is bypassed by a plugin that just clicks | Move the guard to the orchestrator (caller-side); keep the ABC helper for in-tree convenience only |
| Plugin dependency installation | `setup.py` executes with user privileges before anything is installed | No dependency installation in v5.0; enforce a stdlib+core import allowlist at install |
| CVV / payment data reaching plugin code | The one thing the project has never persisted becomes readable by third-party code | Confirm the CVV path never passes through a third-party plugin's reachable state; add it to the AST scan's flagged-symbol list and to the existing credential-leak CI guard |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| A long, formal, EULA-shaped consent prompt | Measurably *increases* blind acceptance (Böhme & Köpsell, 80k users) | 4-6 blunt lines of concrete facts: source, owner, SHA, flagged imports, claimed domains |
| `y/N` confirmation | Muscle memory; ~1.7s clickthrough behaviour | Require typing the plugin name |
| Prompting on every run | Guarantees habituation, and the answer stops carrying information | One consent per install, one per changed update; enforcement afterwards is a silent manifest check |
| `remove` printing "Removed." | User believes the risk is closed; credentials and sessions stay compromised | Print the remediation checklist and the commands that execute it |
| No visual difference between bundled and third-party in `plugins list` | Users cannot tell which code the maintainer wrote | Explicit provenance column plus a distinct log tag (`[ext:foo]`) |
| A wiki registry table that looks like an app store | Listing reads as endorsement no matter what the footer says | Per-row "third-party — not reviewed" column; blunt header copy; no install counts or ratings |
| Silent shadowing of a bundled retailer | User thinks they are talking to the Amazon plugin; they are not | Hard refusal on reserved-domain collision, with the offending file named |
| No indication that a plugin change needs a restart | Stale code keeps running; user assumes otherwise | Explicit "restart required" message plus running-state detection in the CLI |

---

## "Looks Done But Isn't" Checklist

- [ ] **Consent gate:** verify it blocks `shoppybot plugins list`, `GET /`, and
      `GET /api/analytics` — not just `plugins install`. Test each of the four
      `PluginRegistry` construction sites.
- [ ] **SHA pinning:** verify the manifest stores a 40-char commit SHA **and** a content
      hash, and that `update` re-prompts on SHA change. A pinned SHA without a content hash
      does not detect on-disk tampering.
- [ ] **Owner identity:** verify the manifest stores the numeric owner ID, not the login
      string, and that an ownership change is treated as a new install.
- [ ] **Byte lint:** verify a file containing U+FE0F outside a string literal is refused, not
      warned about.
- [ ] **Domain reservation:** verify a third-party plugin declaring `amazon.com` is refused
      at load. Then verify the *non-deterministic* case is gone: two plugins claiming the same
      third-party domain must produce a deterministic refusal, not a `set`-order coin flip.
- [ ] **Checkout capability:** verify a third-party plugin cannot buy without the separate
      typed opt-in, **including from inside `check_availability`** — not only via `auto_buy`.
- [ ] **`PLUGIN_API_VERSION`:** verify a plugin declaring version 1 is refused at load with a
      clear message, and that all 7 bundled plugins declare version 2 explicitly.
- [ ] **Stall containment:** verify a plugin with `time.sleep(600)` inside `check_availability`
      is detected and parked. `asyncio.timeout` alone will not do it — if the test passes
      without a watchdog, the test is wrong.
- [ ] **Live mutation:** verify `remove` on a plugin with an active browser refuses (or forces
      teardown), and that it refuses outright while a place-order marker is set.
- [ ] **Dependencies:** verify a plugin importing a non-allowlisted module fails to install
      with a message naming the module, and that no `pip` invocation exists in the install path.
- [ ] **Acknowledgement record:** verify the manifest stores the disclaimer text version and
      timestamp, and that bumping the version re-prompts.
- [ ] **`SECURITY.md`:** verify it now states that third-party installs bypass the
      per-platform risk assessment at `SECURITY.md:50-52` and that no revocation mechanism
      exists.
- [ ] **Vocabulary:** grep README, wiki, registry docs, CLI help, and release notes for
      `curated`, `verified`, `trusted`, `approved`, `official`, `safe`, `sandbox`, `isolated`
      in any plugin context. Wire it as a CI guard alongside the existing credential-leak check.
- [ ] **Removal remediation:** verify `remove` prints the rotation checklist and that the
      commands it references actually exist.
- [ ] **Support policy:** verify the issue template has the "reproduced with third-party
      plugins removed" checkbox and that third-party plugins produce a distinct log tag.
- [ ] **No auto-update:** grep for any scheduled, timed, or startup-triggered call into the
      update path.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Malicious plugin installed and run | **HIGH** | Kill the process; delete the plugin file and its manifest entry; **rotate every credential in `SECRET_KEYS`** (20 keys: retailer + 2captcha + proxy + notification); log out all sessions at every retailer; delete the encrypted session store; review recent orders and stored payment methods on every account; check for persistence outside the app (Fractureiser self-propagated to unrelated files on disk, so a targeted file scan is warranted) |
| Consent gate built at the install boundary instead of the load boundary | MEDIUM | Move the check into `_discover_plugins`; all four construction sites inherit it. Cheap **only** if the manifest schema already carries the hash — otherwise a schema migration comes with it. Build it right the first time. |
| Branch-pinned installs already in the field | MEDIUM | Add SHA + hash to the manifest schema with a migration that re-resolves each install to its current SHA and re-prompts once, treating the migration as a fresh consent |
| Shadowed bundled retailer discovered after the fact | MEDIUM-HIGH | Same as "malicious plugin run" for the shadowed platform specifically: the plugin held that retailer's live session and checkout path |
| A shipped control turns out to be theatre | HIGH (reputational) | Retract the claim explicitly in a release note, downgrade the language everywhere, keep the control if it has residual value but stop describing it as protection. Far more expensive than getting the wording right initially, which is why Pitfall 12's review criterion is mandatory. |
| Support queue swamped by third-party breakage | MEDIUM | Retro-fit the `[ext:*]` log tag, the issue-template checkbox, and the saved reply. Adding the tag after the fact means old logs are unattributable, so land it with the first release |
| Auto-update shipped and a plugin was weaponised | HIGH | Same as "malicious plugin run" for every user who updated. There is no revocation channel — the project cannot reach installed copies. This is why Pitfall 11 is absolute. |

---

## Pitfall-to-Phase Mapping

Phase topics are proposed for workstream H; the roadmap assigns numbers (v5.0 continues from
Phase 35). Dependencies: **H1 → H2 → H3**; H4 and H5 can run in parallel after H1.

| # | Pitfall | Prevention Phase | Verification |
|---|---------|------------------|--------------|
| 1 | Consent gates install, not execution | **H1** | Test each of the 4 `PluginRegistry` sites refuses an unmanifested file |
| 2 | Branch/tag pinning | **H1** (schema, hash), **H2** (re-consent) | Mutate a file on disk → loader refuses; move a tag → update detects |
| 3 | Repo transferred/sold | **H1** (owner ID), **H2** (re-consent) | Simulated owner-ID change forces full re-consent |
| 4 | Consent fatigue | **H2** | Prompt text is an acceptance criterion; no `--yes` flag exists |
| 5 | TOCTOU review→load; invisible Unicode | **H1** | U+FE0F fixture refused; `plugins verify` detects tampering |
| 6 | Domain/name shadowing | **H3** (+ registry `set` fix) | Third-party `amazon.com` refused; collision resolution deterministic across 100 runs |
| 7 | Import-time credential read | **H3** (scoping), **H1/H2** (scan → prompt) | `get_store()` not reachable from `plugins/`; scan output appears in the prompt |
| 8 | `place_order_guarded` / `monitor_only` bypass | **H3**, coordinated with **workstream G** | Test plugin buying from `check_availability` is blocked by the per-plugin gate |
| 9 | Never-returning plugin stalls the loop | **H3** (watchdog), **H1** (install smoke test) | `time.sleep(600)` plugin is parked, not hung; other plugins keep heartbeating |
| 10 | Live mutation / package-internal dir | **H1** (two dirs, permissions), **H5** (CLI semantics) | `remove` on an active plugin refuses; nothing writes to `site-packages` |
| 11 | Auto-update | **H2**, **H5** | No scheduled path into update; `outdated` cannot install |
| 12 | Sandboxing theatre | **H3** (build), **H4** (document) | Every shipped control has a written "what this does not stop" sentence in REVIEW.md |
| 13 | Disclaimer failure modes | **H4**, **H2** (acknowledgement record) | `SECURITY.md` amended; vocabulary CI guard green; manifest stores disclaimer version |
| 14 | Dependency install channel | **H1** (import allowlist), **H4** (document) | No `pip`/`subprocess` in the install path; disallowed import refused at install |
| 15 | Typosquatting / homoglyphs | **H4** (registry), **H2** (prompt leads with source) | Registry keyed on owner ID; non-ASCII names refused; no install counts displayed |
| 16 | Version skew / support load | **H2** (`PLUGIN_API_VERSION`), **H4** (policy) | v1 plugin refused at load; `[ext:*]` tag present; issue template has the checkbox |
| 17 | Removal ≠ revocation | **H5** (CLI), **H3** (tooling), **H4** (disclaimer) | `remove` prints the checklist; every referenced command exists |

**Proposed phase topics:**

- **H1 — Install substrate and load-time trust gate.** User-writable plugin directory under
  `data_dir()`, install manifest (owner ID, commit SHA, content hash, consent record,
  disclaimer version), gate inside `_discover_plugins` before `exec_module`, byte-level
  Unicode lint, AST import allowlist, install-time import smoke test.
- **H2 — Consent, update, and version enforcement.** Typed consent prompt, re-consent on SHA
  or ownership change, no auto-update, `PLUGIN_API_VERSION` enforced via `__init_subclass__`,
  acknowledgement persisted.
- **H3 — Capability limits and runtime containment.** Scoped credential access, third-party
  checkout opt-in wired into the orchestrator-side guard (with workstream G), reserved-domain
  refusal + deterministic routing, stall watchdog over the existing health surface.
- **H4 — Liability, registry, and support policy.** Disclaimer (operational + formal),
  `SECURITY.md` amendment naming the bypassed gate, machine-readable registry with provenance
  columns, vocabulary CI guard, PLUGIN_DEV.md rewrite, issue template and triage policy.
- **H5 — CLI surface.** `install` / `update` / `remove` / `list` / `verify` / `outdated`,
  staged mutation with running-state detection, removal remediation output.

**Both PROJECT.md sequencing notes hold and are reinforced by this research:** H is the only
workstream needing a genuine design pass, and H warrants a post-verification REVIEW.md deep
pass. Give that review two explicit criteria: **(a)** for every shipped control, one sentence
naming what it does not stop; **(b)** confirmation that no shipped artifact — code, docs, CLI
help, release notes — uses "sandbox", "isolated", "curated", "verified", or "safe" about
third-party plugins.

---

## Sources

**Supply-chain incidents (all HIGH confidence — multiple independent sources per incident):**

- event-stream / flatmap-stream: [npm blog post-mortem](https://blog.npmjs.org/post/180565383195/details-about-the-event-stream-incident), [Snyk post-mortem](https://snyk.io/blog/a-post-mortem-of-the-malicious-event-stream-backdoor/), [systematic analysis paper](https://es-incident.github.io/paper.html)
- PyPI `ctx` / PHP `phpass`: [Python Security advisory](https://python-security.readthedocs.io/pypi-vuln/index-2022-05-24-ctx-domain-takeover.html), [Sonatype](https://www.sonatype.com/blog/pypi-package-ctx-compromised-are-you-at-risk), [BleepingComputer](https://www.bleepingcomputer.com/news/security/popular-python-and-php-libraries-hijacked-to-steal-aws-keys/)
- polyfill.io: [Checkmarx](https://checkmarx.com/blog/alert-cdn-service-polyfill-io-used-by-100k-websites-provided-malicious-code-in-responses/), [Sonatype](https://www.sonatype.com/blog/polyfill.io-supply-chain-attack-hits-100000-websites-all-you-need-to-know), [cside timeline](https://cside.com/blog/polyfill-io-supply-chain-attack-timeline)
- tj-actions/changed-files: [Semgrep](https://semgrep.dev/blog/2025/popular-github-action-tj-actionschanged-files-is-compromised/), [Cycode](https://cycode.com/blog/github-action-tj-actions-changed-files-supply-chain-attack-the-complete-guide/), [Aqua](https://www.aquasec.com/blog/github-action-tj-actions-changed-files-compromised/)
- xz-utils / CVE-2024-3094: [Wikipedia (well-sourced timeline)](https://en.wikipedia.org/wiki/XZ_Utils_backdoor), [Sonatype](https://www.sonatype.com/blog/cve-2024-3094-the-targeted-backdoor-supply-chain-attack-against-xz-and-liblzma)
- Shai-Hulud (v1 + v2): [Unit 42](https://unit42.paloaltonetworks.com/npm-supply-chain-attack/), [ReversingLabs](https://www.reversinglabs.com/blog/shai-hulud-worm-npm), [Arctic Wolf](https://arcticwolf.com/resources/blog/shai-hulud-malware-targets-numerous-npm-packages-second-wave-npm-supply-chain-attack/)
- Fractureiser: [Prism Launcher alert](https://prismlauncher.org/news/cf-compromised-alert/), [investigation repo](https://github.com/fractureiser-investigation/fractureiser), [BleepingComputer](https://www.bleepingcomputer.com/news/security/new-fractureiser-malware-used-curseforge-minecraft-mods-to-infect-windows-linux/)
- GlassWorm: [Truesec](https://www.truesec.com/hub/blog/glassworm-self-propagating-vscode-extension), [Endor Labs — invisible Unicode analysis](https://www.endorlabs.com/learn/invisible-threats-glassworm-unicode-vscode), [The Hacker News — 24-extension resurgence](https://thehackernews.com/2025/12/glassworm-returns-with-24-malicious.html), [The Hacker News — 73 cloned extensions](https://thehackernews.com/2026/04/researchers-uncover-73-fake-vs-code.html)
- The Great Suspender: [The Register](https://www.theregister.com/2021/01/07/great_suspender_malware/), [BleepingComputer](https://www.bleepingcomputer.com/news/security/the-great-suspender-chrome-extensions-fall-from-grace/), [LWN](https://lwn.net/Articles/846272/)
- Nano Adblocker / Nano Defender: [LWN](https://lwn.net/Articles/846272/)
- HACS / Home Assistant custom integrations: [Security Disclosure 2](https://www.home-assistant.io/blog/2021/01/23/security-disclosure2/), [Security Disclosure 1](https://www.home-assistant.io/blog/2021/01/22/security-disclosure/), [GitHub Security Lab review](https://github.blog/security/vulnerability-research/securing-our-home-labs-home-assistant-code-review/)
- Repojacking: [Checkmarx — namespace retirement bypass](https://checkmarx.com/blog/persistent-threat-new-exploit-puts-thousands-of-github-repositories-and-millions-of-users-at-risk/), [Checkmarx — exploited in the wild](https://checkmarx.com/blog/github-repojacking-weakness-exploited-in-the-wild-by-attackers/)

**Sandboxing (HIGH confidence — upstream/authoritative):**

- [PEP 578 — Python Runtime Audit Hooks](https://peps.python.org/pep-0578/) — "This is not sandboxing…"
- [CPython `sys` docs — `addaudithook` security note](https://docs.python.org/3/library/sys.html) — C-API-before-init requirement; `ctypes` caveat
- [Victor Stinner, "The pysandbox project is broken", python-dev, Nov 2013](https://mail.python.org/pipermail/python-dev/2013-November/130132.html); [LWN coverage](https://lwn.net/Articles/574215/); [pysandbox repo warning](https://github.com/vstinner/pysandbox)
- [RestrictedPython README](https://github.com/zopefoundation/RestrictedPython) — "not a sandbox system or a secured environment"
- Escape technique write-ups: [delroth](https://blog.delroth.net/2013/03/escaping-a-python-sandbox-ndh-2013-quals-writeup/), [Zolmeister](https://zolmeister.com/2013/05/escaping-python-sandbox.html)
- [PyPI/pip security best practices — `--only-binary` + `--require-hashes`](https://github.com/lirantal/pypi-security-best-practices); [Veracode on Python install-time execution](https://www.veracode.com/blog/python-package-installation-attacks/)

**Consent and warning design (MEDIUM-HIGH):**

- Böhme & Köpsell, *Trained to Accept? A Field Experiment on Consent Dialogs*, [CHI 2010](https://dl.acm.org/doi/10.1145/1753326.1753689) — 80,000 users; EULA-shaped dialogs increase blind acceptance
- Chrome SSL warning clickthrough telemetry (~50% in ≤1.7s), cited across the warning-fatigue literature

**Comparable-project policy (MEDIUM — practice, not standards):**

- [Obsidian — Plugin security](https://obsidian.md/help/plugin-security) — Restricted Mode by default; "cannot reliably restrict plugins to specific permissions"; recommends an independent audit for sensitive data
- [home-assistant/core#169994](https://github.com/home-assistant/core/issues/169994) — custom integrations shadowing built-ins is "a feature, not a bug"
- [Home Assistant — Reporting issues](https://www.home-assistant.io/help/reporting_issues/) — custom-integration triage posture

**This repository (HIGH — read directly, 2026-08-02):**

- `core/registry.py:19-57` (`_discover_plugins` / `exec_module`), `:115-125` (first-match routing), `:172-191` (`set`-ordered activation)
- `core/plugin_base.py:15` (`PLUGIN_API_VERSION`, unenforced), `:82-92` (`__init_subclass__` hook), `:151-192` (`place_order_guarded`), `:326-372` (`restore_session`)
- `core/credentials.py:47-77` (`SECRET_KEYS`), `:310-320` (`get_store()` global)
- `core/checkout_profile.py:20`, `:78`; `core/session_store.py:49`, `:74`
- `core/orchestrator.py:369` (`asyncio.timeout`), `:571-580` (`monitor_only` gate), `:802-812` (registry construction, `plugins_dir`)
- `core/service.py:120-141` (`get_analytics` → registry), `:143-160` (`list_plugins` → registry)
- `web/routes/pages.py:16-32` (`GET /`), `web/routes/api.py:170-179` (`GET /api/analytics`)
- `core/cli/plugins.py:49`; `plugins/PLUGIN_DEV.md:212-217`; `SECURITY.md:50-52`, `:68-76`
- `.planning/seeds/SEED-003-remote-plugin-manager-and-extensibility-framework.md`

---
*Pitfalls research for: third-party plugin distribution into a credential-holding, money-spending Python application*
*Researched: 2026-08-02*
