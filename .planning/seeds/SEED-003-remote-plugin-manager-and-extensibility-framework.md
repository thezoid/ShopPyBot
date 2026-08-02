---
id: SEED-003
status: dormant
planted: 2026-08-01
planted_during: post-v4.2 Release Readiness (awaiting next milestone)
trigger_when: when scoping a community/ecosystem milestone, or before promoting the project as extensible to third parties
scope: unknown
---

# SEED-003: Remote plugin manager, third-party liability disclaimer, and first-class extensibility framework

Three related threads, captured together because they only make sense as one story:
letting users install plugins the maintainer never sees, saying so plainly, and making
the app genuinely pleasant to extend.

1. **Plugin manager that installs from other repos.** A user should be able to add a
   retailer plugin sourced from a third-party repository without that plugin ever being
   merged into this one. Install, list, update, remove, all without touching core.
2. **Liability disclaimer (CYA).** Explicit, prominent statements that the maintainer
   neither reviews, endorses, nor supports anything a third-party plugin does, and that
   installing one is the user's decision and risk.
3. **Extensibility framework.** Make the app easily customizable and plugin-adaptable,
   if and where that is not already true.

## Why This Matters

The project's stated core value is already "a drop-in plugin framework that lets the
community add new retail platform integrations by placing a single Python file in
`plugins/` with no core changes required." Today that promise only pays off for people
who either write the plugin themselves or get it merged upstream. There is no
distribution story. A plugin manager is what turns a documented extension point into an
actual ecosystem.

Thread 3 is mostly already done, which is the useful discovery here. The extension
framework largely exists (see Breadcrumbs), so a future milestone should verify and
close gaps rather than rebuild. **Do not re-plan this as greenfield work.**

Thread 2 is not optional decoration. It is the precondition that makes thread 1
defensible.

## When to Surface

**Trigger:** When scoping a community/ecosystem milestone, or before marketing the
project as third-party extensible. Also re-surface if [[SEED-001-public-repo-history-scrub-squash]]
or a public-launch milestone is scoped, since a public launch invites exactly the
third-party plugins this seed governs.

Related and already-open: `REG-01` (the GitHub wiki Plugin Registry page) is the manual,
human-curated ancestor of thread 1. A real plugin manager could consume a machine-readable
version of that registry instead of a wiki table.

## Scope Estimate

**Unknown** — needs a real design pass. Rough shape:

- Thread 3 (framework): likely **small**, mostly verification and gap-closing.
- Thread 2 (disclaimer): **small**, documentation plus a first-run or install-time
  acknowledgement.
- Thread 1 (manager): **medium to large**, and the size depends almost entirely on how
  much trust machinery ships with it.

## The security question this seed must answer before it ships

Stating this up front so a future planning pass does not discover it late.

Fetching a Python file from an arbitrary repository and loading it is arbitrary code
execution, on a machine that holds an encrypted credential store, retail account
logins, live browser sessions, and a checkout path that types a CVV and clicks Place
Order. A malicious plugin does not need an exploit; `_discover_plugins` imports the
module, and import *is* execution. `plugins/PLUGIN_DEV.md:212-217` already says exactly
this: "Loading a plugin file is equivalent to executing it."

So the disclaimer in thread 2 is necessary but **not sufficient on its own**. A
disclaimer sets expectations; it does not stop a plugin from reading the credential
store. Options worth weighing during design, roughly cheapest to most involved:

- Explicit install-time consent, naming the source repo and requiring a typed confirm.
- Pinning by commit SHA rather than branch, so an install cannot silently change later.
- A vetted allowlist or signature check, reusing the `REG-01` registry as the trust root.
- Capability limits on what a plugin can reach (credential store access being the
  obvious thing to gate).
- Process isolation, which is the real fix and also by far the most expensive.

Pick deliberately. "Disclaimer only" is a legitimate choice for a hobbyist tool, but it
should be a decision on the record, not a default that happens because nobody raised it.

## Breadcrumbs

Framework pieces that already exist (thread 3 is further along than it looks):

- `core/registry.py:19-41` — `_discover_plugins` autoloads any `shopbot_plugin_*.py` in
  `plugins/` by filename convention; warns and skips non-matching `.py` files; isolates
  import failures so one bad plugin cannot crash the app. A plugin manager's install
  step could be as simple as writing a file into this directory.
- `core/plugin_base.py:123-129` — `RetailerPlugin` ABC has only **two** abstract methods
  (`check_availability`, `auto_buy`). Everything else has a working default. The surface
  a plugin author must implement is already small.
- `core/plugin_base.py:15,82` — `PLUGIN_API_VERSION = 2` plus `__init_subclass__`
  import-time validation. A version-compatibility gate for remote plugins already has a
  hook to hang off.
- `core/plugin_base.py:78-80` — `difficulty`, `requires_proxy`, `requires_captcha`
  metadata attributes. These are the fields a registry/manager would surface to users.
- `core/plugin_base.py:269` — `get_platform_config(model_cls)`, shipped as CFG-02 in
  v4.2 Phase 33 alongside `extra="allow"` on `PlatformsConfig`. A new plugin can declare
  and validate its own config section with **zero** edits to `core/config_schema.py`.
  This was the last major core-coupling point and it is already closed.
- `plugins/example_plugin.py` — reference implementation, already shipped.
- `plugins/PLUGIN_DEV.md` — authoring guide. Section 9 "Trust and Security" (line 212)
  already carries the execution warning and explicitly defers "the full community plugin
  policy" to CONTRIBUTING.md and SECURITY.md "planned for a later phase". **This seed is
  that later phase.**
- `docs/PLUGIN_REGISTRY.md` — the 9-column registry spec. Currently rendered by hand onto
  a GitHub wiki page (`REG-01`, still outstanding). A machine-readable version is the
  natural index for a plugin manager.
- `SECURITY.md:50-52` — requires a documented risk assessment per platform before a
  plugin is merged. A third-party plugin bypasses that gate entirely, which is precisely
  the gap thread 2 has to name.
- `.github/PULL_REQUEST_TEMPLATE.md` — already collects plugin metadata on merge.

Related seeds: [[SEED-001-public-repo-history-scrub-squash]] (public launch is the event
that makes third-party plugins likely).

## Notes

Captured 2026-08-01, between the v4.2 close and the next milestone, during a UAT audit
session.

Worth deciding early whether the manager is a CLI subcommand (`shoppybot plugins install
<repo>`, fitting the existing `shoppybot plugins list`), a dashboard surface, or both.
The CLI already has a `plugins` command group, so that is the cheaper entry point.

Note the 5 community plugins bundled today (Walmart, Target, GameStop, NewEgg,
SquareEnix) are all EXPERIMENTAL with selector-unverified status and no BF-02 place-order
marker propagation. A plugin manager makes the "how do users know a plugin is safe to
point at real money" question much sharper than it is while everything ships in-tree.
