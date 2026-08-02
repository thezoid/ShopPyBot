# Feature Research

**Domain:** Third-party plugin distribution for a Python retail-automation bot (ShopPyBot v5.0 workstream H / SEED-003)
**Researched:** 2026-08-02
**Confidence:** MEDIUM-HIGH (mechanism claims verified against official docs for 7 of 8 systems; exact UI copy for VS Code's trust dialog could not be sourced verbatim — flagged inline)

> **Supersedes** a prior version of this file scoped to the v4.1 observability dashboard
> (health cards, price charts, log viewer). That research is retired — v4.1 shipped.
> This file is scoped entirely to v5.0 workstream H / SEED-003.

## Framing

This app already has the hard part of an extension framework built: `core/registry.py`
auto-discovers `shopbot_plugin_*.py` files with per-plugin import-failure isolation,
`core/plugin_base.py`'s `RetailerPlugin` ABC has only two required methods plus a
`PLUGIN_API_VERSION` import-time compatibility gate, and `difficulty` /
`requires_proxy` / `requires_captcha` are already first-class metadata attributes
surfaced by `shoppybot plugins list`. What does not exist is a *distribution* story:
a way to get a plugin from a third-party repo into that directory, and a trust
story for having done so. That is the entire scope of this research — not "how do
plugin systems work" in general, but "how do comparable systems solve the
install/trust/update problem specifically," so v5.0 workstream H can be scoped as
the small, mostly-additive piece SEED-003 says it should be.

## Ecosystem Survey: How 8 Real Systems Actually Do This

Each entry: install UX, where code lands, trust model, update semantics, how
arbitrary-code-execution is handled. Confidence noted per system.

### pipx / pip VCS install — HIGH confidence

- **Install UX:** `pipx install git+https://github.com/owner/repo.git[@ref]` or
  `pip install git+https://git.example.com/MyProject.git@ref`. `ref` can be a
  branch, tag, or full commit SHA — pinning to an exact commit is ordinary syntax,
  not a special mode: `pipx install git+https://github.com/psf/black.git@ce14fa8b...`.
- **Where code lands:** pipx creates one isolated venv per package
  (`~/.local/pipx/venvs/<name>` or platform equivalent) and exposes the entry point
  on `PATH`. pip installs into whatever environment is active.
- **Trust model:** none. No signature check, no publisher verification, no listing
  or curation of any kind. Isolation here means dependency isolation — the installed
  code still runs with full user privileges the moment its entry point is invoked.
- **Update semantics:** `pipx upgrade <name>` re-resolves the same source spec.
  Pinned to a branch, upgrade silently picks up new commits; pinned to a SHA,
  upgrade is a no-op until the user edits the pin.
- **Arbitrary-code handling:** zero machinery. This is the ecosystem's floor —
  useful as the "what happens if we build nothing" baseline.
- Sources: [pip VCS Support](https://pip.pypa.io/en/stable/topics/vcs-support/), [pipx GitHub](https://github.com/pypa/pipx)

### Obsidian community plugins — HIGH confidence

- **Install UX:** Settings → Community plugins → in-app catalog → Install, then a
  separate explicit Enable toggle per plugin (two steps, not one).
- **Where code lands:** `.obsidian/plugins/<plugin-id>/` inside the vault
  (`main.js`, `manifest.json`) — same "import is execution" shape as this project's
  Python files, just JS.
- **Trust model:** the enforcement point is not a per-install dialog, it's a
  persistent app-level posture. Official docs: **"By default, Obsidian runs in
  Restricted Mode to prevent third-party code execution. Only disable Restricted
  mode if you trust the authors of the plugins that you install."** and, plainly:
  **"Community plugins run third-party code on your behalf that could potentially
  do harm."** While Restricted Mode is on, nothing installed runs at all — it's a
  hard gate, not advisory copy. Separately, plugins submitted to the official
  directory get an initial human review before first listing; updates to
  already-listed plugins are not re-reviewed line by line.
- **Update semantics:** in-app "Check for updates," one-click per plugin, no forced
  auto-update.
- **Arbitrary-code handling:** the *toggle-and-stay-off-by-default* pattern is the
  most concretely reusable idea here — trust is captured as an ambient state the
  user must deliberately exit, not a one-time click-through they can blow past.
- Sources: [Obsidian: Community plugins](https://obsidian.md/help/community-plugins), [Plugin security](https://github.com/obsidianmd/obsidian-help/blob/master/en/Extending%20Obsidian/Plugin%20security.md)

### VS Code extensions / Marketplace — HIGH confidence on mechanism, LOW on exact copy

- **Install UX:** in-editor Marketplace panel, or `code --install-extension <id>`.
- **Where code lands:** `~/.vscode/extensions/<publisher>.<name>-<version>/`.
- **Trust model, two independent layers:**
  1. Publish-time integrity signing — the Marketplace signs every extension; VS
     Code verifies the signature on install (catches tampering in transit, says
     nothing about intent). A blue "Verified Publisher" check mark only proves
     domain-name ownership, not code safety.
  2. As of VS Code 1.97, a runtime dialog on **first install from a publisher the
     user hasn't trusted before**, asking for confirmation; Microsoft and GitHub
     publishers are pre-trusted. The exact dialog copy could not be sourced
     verbatim from official docs or GitHub issue threads despite direct fetches —
     flagged LOW confidence on wording, HIGH confidence the mechanism exists.
  3. Separately, **Workspace Trust** gates whether workspace-provided code/tasks
     can auto-run, and defaults to a passive Restricted Mode *banner* rather than
     an upfront modal (`security.workspace.trust.startupPrompt` defaults to
     `never`) — friction the user opts into, not friction forced on them.
- **Update semantics:** auto-update by default, silent, background; can be
  disabled by the user.
- **Arbitrary-code handling:** signature verification stops tampering, not
  malice. Actual safety net is publisher reputation and reviews — same as
  everywhere else, just with a nicer badge.
- Sources: [Extension Marketplace](https://code.visualstudio.com/docs/configure/extensions/extension-marketplace), [Extension runtime security](https://code.visualstudio.com/docs/configure/extensions/extension-runtime-security), [Workspace Trust](https://code.visualstudio.com/docs/editing/workspaces/workspace-trust)

### Home Assistant HACS — MEDIUM confidence (closest analogue; also the weakest trust model surveyed)

HACS is the closest structural analogue to what SEED-003 proposes: a community
plugin store bolted onto a first-party app that was not originally designed for
one.

- **Install UX:** HACS itself is installed once as a "custom integration" (a
  bootstrap step outside HA's normal integration flow). After that, its own UI
  offers a semi-curated "default store" plus an "add custom repository" flow
  where the user pastes any GitHub URL directly.
- **Where code lands:** `custom_components/<domain>/` (integrations) or
  `www/community/<name>/` (frontend cards), inside the live Home Assistant config
  directory, loaded by HA's own component loader exactly like first-party code.
  **No isolation whatsoever** — this is a materially weaker posture than any
  Python-import-based plugin loader that at least confines plugins to their own file.
- **Trust model:** default-store inclusion requires *structural* metadata — a
  `hacs.json` manifest, GitHub topics, a README, and published GitHub releases —
  checked by an automated CI action. That is validation of shape, not of intent;
  it is not a code-safety review. Custom repositories (arbitrary URL) skip even
  that structural gate entirely. Direct fetches of the HACS README and hacs.xyz
  docs turned up **no disclaimer or "not officially supported" language at the
  point of adding a custom repository** — this absence is itself the key finding,
  not a gap in this research. HACS, despite being the best-resourced project in
  this survey, ships less consent machinery around third-party code than Obsidian,
  gh CLI, or VS Code.
- **Update semantics:** available updates surface in HACS's own UI; per-item
  manual "Update" by default, with an optional per-repo auto-update setting a
  user can opt into.
- **Arbitrary-code handling:** effectively none in-product. This is the strongest
  evidence in the whole survey that "closest analogue" does not mean "best
  precedent to copy" — it is a cautionary data point, not a template.
- Sources: [hacs.xyz](https://www.hacs.xyz/), [hacs/integration](https://github.com/hacs/integration), [HACS: Publish requirements](https://www.hacs.xyz/docs/publish/start/)

### Neovim plugin managers — lazy.nvim / packer.nvim — MEDIUM-HIGH confidence

- **Install UX:** declarative — a plugin spec (`owner/repo` short-name) lives in
  the user's own Lua config; the manager clones it on next start. There is no
  separate "install command" moment — the friction is entirely pre-install, in
  the user's own authored config.
- **Where code lands:** `~/.local/share/nvim/lazy/<repo>/` — a plain git clone,
  no isolation.
- **Trust model:** none beyond "you wrote this line yourself" — closest in shape
  to pip/pipx.
- **Update semantics — the standout idea in this survey:** lazy.nvim
  auto-generates `lazy-lock.json`, mapping every installed plugin to the exact
  commit SHA currently in use. Running an update advances the lock; the file is
  meant to be committed to the user's own dotfiles so a fresh machine reproduces
  byte-identical plugin state instead of "whatever HEAD is today." Individual
  plugins can also be hard-pinned to a commit/tag/branch/semver range directly in
  the spec.
- **Lifecycle note:** packer.nvim (the predecessor) used a compiled Lua "snapshot"
  file and an explicit `PackerCompile`/`PackerSync` step; it is now unmaintained,
  and Neovim 0.12 shipped a built-in `vim.pack` manager. Even a well-adopted
  community plugin-manager project gets superseded — an argument against
  over-building bespoke manager UI for a hobbyist tool.
- **Arbitrary-code handling:** none — the reusable idea here is the
  lockfile-as-reproducibility mechanism, not any trust feature.
- Sources: [lazy.nvim](https://github.com/folke/lazy.nvim), [lazy.nvim lockfile docs](https://lazy.folke.io/usage/lockfile)

### Sublime Package Control — MEDIUM confidence

- **Install UX:** Command Palette → "Package Control: Install Package" → fuzzy
  search over a channel file (the default channel is Package Control's own
  curated JSON index) plus any custom repositories added in settings.
- **Where code lands:** `Packages/<name>/`, loaded directly by the editor — no
  isolation.
- **Trust model:** default-channel packages go through a real, if lightweight,
  human-reviewed submission process (a PR against the channel's package list,
  increasingly assisted by automated linting tooling). Custom repositories added
  by raw URL bypass that process entirely and are visually indistinguishable from
  default-channel packages once added — no "unofficial" badge found in current
  docs.
- **Update semantics:** per-package "Upgrade Package," or "Upgrade All" — the
  docs explicitly warn this **upgrades every installed package including ones not
  installed via Package Control**, a real footgun for anyone who manually vendors
  a package alongside managed ones.
- **Arbitrary-code handling:** review gate exists only for the curated channel;
  nothing stops a custom-repo package from doing anything.
- Sources: [Package Control: Usage](https://packagecontrol.io/docs/usage), [Package Control GitHub](https://github.com/wbond/package_control)

### oh-my-zsh plugins — LOW-MEDIUM confidence (community-sourced, not official-doc-quoted)

- **Install UX:** bundled plugins need no install step at all — add a name to
  `plugins=(...)` in `.zshrc`. Third-party plugins require the user to manually
  `git clone` into `~/.oh-my-zsh/custom/plugins/<name>/` (or layer a separate
  manager like zinit/antidote on top), then reference the same name.
- **Where code lands:** sourced directly into the running shell process — the
  most permissive system surveyed. A malicious `.plugin.zsh` runs the instant the
  shell starts, with full access to every environment variable and the ability to
  silently alias or override any command.
- **Trust model:** none, and not enforced anywhere in the framework itself.
  Community best-practice pages advise reviewing third-party plugin source before
  adding it; curated link-lists like `awesome-zsh-plugins` carry the general
  understanding that entries aren't vetted for malicious code, but this is
  community norm, not project-enforced language.
- **Update semantics:** `omz update` updates the framework and its own bundled
  plugins only; separately cloned third-party plugins are the user's own `git
  pull`, unless a layered manager handles it.
- **Arbitrary-code handling:** none. Useful as the low-water mark: "just a
  directory convention, no consent, no metadata" is exactly the shape ShopPyBot's
  *current* in-tree `plugins/` directory already has for bundled plugins — the
  ecosystem's own answer to that gap has been third-party managers built
  precisely because oh-my-zsh never built one in.
- Sources: [ohmyzsh/ohmyzsh](https://github.com/ohmyzsh/ohmyzsh), [ohmyzsh wiki: Plugins](https://github.com/ohmyzsh/ohmyzsh/wiki/plugins)

### `gh extension install` (GitHub CLI) — HIGH confidence — closest shape to SEED-003's ask

This is the most directly analogous system surveyed: a first-party CLI with a
subcommand group (`gh extension`) that fetches and executes third-party code from
arbitrary repos, closely mirroring a `shoppybot plugins install <repo>` shape
sitting next to the already-shipped `shoppybot plugins list`.

- **Install UX:** `gh extension install owner/repo` (repo must be named
  `gh-<name>` by convention, mirroring this project's `shopbot_plugin_<name>.py`
  convention); accepts a full URL for GitHub Enterprise hosts; `gh extension
  install .` installs a locally-cloned copy for development as a symlink.
- **Where code lands:** a user-scoped local directory
  (`~/.local/share/gh/extensions/<name>/` on Linux), becoming a new top-level `gh
  <name>` subcommand.
- **Trust model — documentation-only disclaimer, explicit and specific:**
  > "Extensions outside of GitHub and GitHub CLI are not certified by GitHub and
  > are governed by separate terms of service, privacy policy, and support
  > documentation."

  > "To mitigate risk when using third-party extensions, audit the source code of
  > the extension before installing or updating the extension."

  No in-CLI interactive consent prompt, no typed confirmation, no isolation —
  the entire trust posture is this paragraph in the manual.
- **Update semantics:** `gh extension upgrade <name>` or `--all`; `--force`
  bypasses the already-up-to-date short-circuit. Critically, **`--pin
  <tag-or-commit>`** locks an extension to an exact release tag or commit SHA as
  an ordinary, documented, first-class flag — not a workaround or advanced mode.
- **Arbitrary-code handling:** disclaimer-only in the trust dimension, but the
  `--pin` flag is the single most directly reusable piece of prior art here: it
  proves a CLI plugin-install command can offer commit-level pinning as a plain
  flag without needing a lockfile or any heavier machinery.
- Sources: [Using GitHub CLI extensions](https://docs.github.com/en/github-cli/github-cli/using-github-cli-extensions), [gh extension install manual](https://cli.github.com/manual/gh_extension_install)

## Disclaimer & Consent Language Precedents

Direct answer to "how do comparable OSS projects word this, and where do they
capture it in the flow." None of the 8 systems surveyed require a **typed**
confirmation (typing a phrase, the plugin name, "yes", etc.) before installing a
plugin. That is a real, verified finding, not an omission in this research — the
strongest precedent found is Obsidian's structural Restricted-Mode toggle (a
persistent state flip) and VS Code's per-publisher click-through dialog (a click,
not a typed string).

| System | Capture point | Type | Quoted text | Confidence |
|---|---|---|---|---|
| Obsidian | Persistent app-level Restricted Mode + per-plugin enable switch | Active (toggle), not typed | "By default, Obsidian runs in Restricted Mode to prevent third-party code execution. Only disable Restricted mode if you trust the authors of the plugins that you install." / "Community plugins run third-party code on your behalf that could potentially do harm." | HIGH — official docs, direct fetch |
| gh CLI extensions | Documentation only, no runtime prompt | Passive notice | "Extensions outside of GitHub and GitHub CLI are not certified by GitHub and are governed by separate terms of service, privacy policy, and support documentation." / "To mitigate risk when using third-party extensions, audit the source code of the extension before installing or updating the extension." | HIGH — official docs, direct fetch |
| VS Code | Runtime dialog, first install per untrusted publisher | Active (click), not typed | Mechanism confirmed; exact dialog copy not found in official docs or issue threads | HIGH (mechanism) / LOW (exact copy) |
| Sublime Package Control | None found at custom-repo add time | — | No disclaimer text found in official docs | MEDIUM (searched, absence noted) |
| HACS | None found at custom-repo add time | — | No disclaimer text found in README or hacs.xyz docs | MEDIUM (searched, absence noted) |
| oh-my-zsh | Community norm only, not project-enforced | Passive, informal | General "review before you add it" advice on wikis/curated lists | LOW-MEDIUM — community-sourced, not an official quote |
| pipx / pip | None | — | No disclaimer — dependency-isolation framing only, not a safety claim | HIGH |
| ShopPyBot (existing, in this repo) | Already-written contributor doc + security policy | Passive notice, documentation-only, pre-dates any install flow | `plugins/PLUGIN_DEV.md:212-217`: "Loading a plugin file is equivalent to executing it. Only install plugin files from sources you trust... The full community plugin policy will be documented in CONTRIBUTING.md and SECURITY.md (planned for a later phase)." `SECURITY.md`'s existing "Legal Scope and Disclaimer": "ShopPyBot is provided for personal, non-commercial use only, on an 'as is' basis, without warranty of any kind, express or implied... The developer(s) accept no liability for any consequences arising from use of this software or any derivative." | HIGH — read directly from repo |

**Reading on the existing ShopPyBot text:** `SECURITY.md`'s current disclaimer
covers general software liability ("as is," no warranty) but does not yet say
anything about third-party plugin sources specifically — it does not state that
the maintainer neither reviews nor endorses what a third-party plugin does. That
is the precise, still-open gap SEED-003 thread 2 names. The new language should
extend this existing section (same file, same tone, same "does not expand,
limit, or supersede the full Disclaimer in README.md" cross-reference pattern
already established) rather than invent a new disclaimer surface.

## Feature Landscape

### Table Stakes (Users Expect These)

A plugin manager isn't credible without these — every credible precedent above
has some form of each.

| Feature | Why Expected | Complexity | Notes |
|---|---|---|---|
| Install from a source spec (`shoppybot plugins install <repo>[@ref]`) | Every surveyed system's core verb; matches existing `shoppybot plugins` CLI group | LOW-MEDIUM | Mechanically a git-clone into `plugins/` plus filename-convention validation — `_discover_plugins` already does the load/isolate step |
| List with provenance (extend existing `plugins list`) | `plugins list` already exists and shows difficulty/requires_proxy/requires_captcha; users will expect to see *where a plugin came from*, same as `gh extension list` | LOW | Add source URL + installed ref/commit columns to the existing command; no new command needed |
| Remove/uninstall (`plugins remove <name>`) | Every system surveyed has this as a first-class op | LOW | Delete the single file; `_discover_plugins`'s per-file isolation makes this mechanically trivial |
| Version/compatibility pinning at install | Universal except HACS's default store; ShopPyBot already has the enforcement half (`PLUGIN_API_VERSION` import-time gate) | LOW-MEDIUM | Real precedent in Obsidian's `manifest.json` minAppVersion, VS Code's `engines.vscode`, Sublime's `sublime_text` build field, `gh extension install --pin`, pip/pipx git refs |
| Source visibility before/at install | Weakest in most surveyed systems (pip, HACS, oh-my-zsh give none); doing even "echo the resolved URL + commit SHA before writing the file" clears the bar | LOW | No system surveyed shows a pre-execution diff — none is expected to; showing the resolved ref is achievable and already exceeds most precedents |
| Install-time consent gate (any form, even passive) | Every system surveyed except HACS/oh-my-zsh has *something*; shipping nothing here contradicts SEED-003 thread 2's own mandate | LOW | Minimum viable version: a confirmation prompt naming the source and requiring y/N before the file is written |
| `update <name>` | Direct precedent: `gh extension upgrade`, `pipx upgrade`, Obsidian's in-app update, HACS's per-item update | LOW-MEDIUM | Re-fetch at the pinned ref, or advance a tracked branch; must build on provenance tracking (see dependencies) |

### Differentiators (What Would Genuinely Help This App)

None of the 8 surveyed systems manage anything with purchase authority or a
credential store this sensitive — this is where ShopPyBot's actual domain shape
should drive design, not general plugin-manager convention.

| Feature | Value Proposition | Complexity | Notes |
|---|---|---|---|
| Safety metadata surfaced **at install time**, not just after in `plugins list` | `difficulty`/`requires_proxy`/`requires_captcha` already exist as ABC class attrs (`core/plugin_base.py:78-80`) — showing them in the install confirmation, before the file is written, is a UX reorder, not new data | LOW | No comparable system surveyed has retailer-specific risk metadata to show; this is domain-unique to ShopPyBot already |
| Typed install-time confirmation naming the source repo | Directly named in SEED-003 as the cheapest option on its own list; genuinely exceeds every precedent surveyed (none require typing, only clicking or toggling) | LOW | e.g., prompt requires typing the plugin name or repo slug back to proceed |
| Commit-SHA pinning as the **default** install mode, not opt-in | Same mechanism as `gh extension install --pin`, flipped to default-on; directly answers SEED-003's own stated worry ("pinning by commit SHA rather than branch, so an install cannot silently change later") | LOW | Prevents a plugin the user reviewed once from being silently swapped on next `update` if tracking a branch |
| "This plugin can spend money" warning tier | Genuinely unique to this domain — no surveyed system manages financial transaction authority; distinguishing "checks availability" from "can complete a purchase with saved payment" is a meaningfully different risk statement than any generic plugin warning | MEDIUM | Detection is trivial (`auto_buy` is already a required abstract method on every plugin); the design work is the tiering and whether/how it interacts with the existing `monitor_only` run-mode guard |
| Machine-readable registry replacing the hand-maintained wiki table (REG-01) | `docs/PLUGIN_REGISTRY.md`'s 9-column spec already defines the schema; converting it to a fetchable JSON file lets `plugins install` show maintainer/last-verified/risk-tier even for non-bundled plugins, purely informational | MEDIUM | Structurally what Obsidian's community-plugins list and Sublime's channel JSON already are — a consumable index, explicitly *not* a code-review gate |

### Anti-Features (Deliberately Not Building)

Each argued against a real alternative, not just flagged.

| Feature | Why Requested | Why Problematic | Alternative |
|---|---|---|---|
| Hosted marketplace / central discovery website | Obvious ask once a manager exists — "how do I find plugins" | Requires hosting infra, a submission pipeline, and ongoing moderation a single maintainer cannot staff; even HACS — better-resourced than this project — only validates *structure* via CI, not quality, and its issue tracker shows steady maintenance drag from exactly this surface | The machine-readable registry (differentiator above) gives discoverability with zero hosting: a JSON file in-repo, and `plugins install` works against any user-supplied URL with no central index required |
| Auto-update (silent, unattended) | "Always current" feels safer; VS Code does this by default | For this app specifically, auto-update is a silent supply-chain channel straight onto a machine holding an encrypted credential store, live retail sessions, and a checkout path that clicks Place Order — exactly the risk SEED-003's own security section names ("a malicious plugin does not need an exploit; import is execution"). None of the surveyed systems that touch anything sensitive (gh CLI, pipx) auto-update; the ones that do (VS Code, oh-my-zsh's own bundled plugins) aren't managing financial transaction authority | Explicit, always user-invoked `plugins update <name>` per SEED-003 thread 1 |
| Plugin ratings / stars / telemetry-driven trust signals | Feels like a cheap trust proxy; several surveyed systems lean on it (VS Code reviews, Package Control listing metadata) | Requires either a hosted backend (see above) or scraping GitHub stars (weak, gameable), and computing install counts means adding a telemetry surface this project has deliberately avoided everywhere else — every prior milestone's constraint has been "observability is read-only... no new secrets," with no existing telemetry pipeline to extend | The registry's existing fields (last-verified date, maintainer, difficulty) are a more honest, much cheaper trust signal than a star count at this project's scale |
| Maintainer-staffed curation/review gate on install (an allowlist model) | It's the obvious way to make trust real, and it's exactly what already happens for in-tree plugins today (SECURITY.md's per-platform risk-assessment gate on merge) | The entire point of SEED-003 thread 1 is letting a plugin be installed *without* ever being merged or seen by the maintainer — a review gate on install reintroduces the PR bottleneck the seed exists to bypass, for a single-maintainer project that per the v5.0 milestone context is already behind on reviewing its own in-tree backlog | Shift the trust decision to the installing user via safety metadata, typed consent, and commit pinning, rather than gatekeeping who can publish |
| Process isolation / sandboxing for plugin execution | The only option on SEED-003's own list that actually *stops* a malicious plugin from reading the credential store, rather than disclosing the risk | SEED-003 itself ranks it "the real fix and also by far the most expensive"; PROJECT.md's Future Candidate Directions already lists it as deferred, separate from v5.0. Conflating it with workstream H risks turning a "small-to-medium, mostly verification" scope into an open-ended architecture rewrite (subprocess boundary, IPC for browser/DB/credential access, a much smaller plugin surface than "any Python file") | Ship consent + capability-lite (the differentiators above) now; keep isolation on the roadmap as the eventual answer once the ecosystem justifies the cost |

## Feature Dependencies

```
Install (git-clone into plugins/, naming-convention check)
    └──requires──> PLUGIN_API_VERSION enforcement at import (already shipped, core/plugin_base.py:15,82)
                       └──requires──> RetailerPlugin ABC __init_subclass__ validation (already shipped)

Install-time consent gate
    └──requires──> Safety metadata read before write (difficulty/requires_proxy/requires_captcha already exist,
                    core/plugin_base.py:78-80 — just need to be read pre-import instead of post-import)

Typed confirmation
    └──enhances──> Install-time consent gate (raises the bar past every precedent surveyed)

Commit-SHA pinning (default-on)
    └──requires──> Provenance tracking (source URL + installed ref must be recorded — a small per-plugin
                    manifest or a central installed-plugins.json; nothing today records this)

plugins update <name>
    └──requires──> Provenance tracking (must know what ref/branch to re-resolve against)

"can spend money" warning tier
    └──requires──> auto_buy method presence detection (trivial — ABC already forces every plugin to implement it)
    └──enhances──> Install-time consent gate

Machine-readable registry
    └──replaces──> docs/PLUGIN_REGISTRY.md wiki-table workflow (REG-01, currently manual/human-curated)
    └──enhances──> Install-time consent gate (can show maintainer/last-verified even for non-bundled plugins)

Hosted marketplace ──conflicts──> single-maintainer staffing reality (anti-feature)
Auto-update ──conflicts──> credential-store / checkout threat model (anti-feature)
Maintainer review gate on install ──conflicts──> SEED-003 thread 1's entire premise (no-merge-required distribution)
```

### Dependency Notes

- **Provenance tracking is the one genuinely new piece of state.** Nothing in the
  existing surface records where an installed plugin file came from or what ref
  it's pinned to — `plugins list`, `update`, and default-commit-pinning all sit
  downstream of this. Scope it early; it's the load-bearing addition, not a
  side detail.
- **Everything else in Table Stakes and most of Differentiators sits on top of
  already-shipped ABC surface** (`PLUGIN_API_VERSION`, `difficulty` /
  `requires_proxy` / `requires_captcha`, the two-method-only ABC). This is why
  SEED-003 estimates thread 3 (framework) as "likely small, mostly verification"
  — confirmed by this survey: the missing piece really is distribution +
  provenance + consent, not a framework rebuild.
- **The registry (differentiator) and the wiki table it replaces (REG-01) are the
  same schema, not a redesign** — `docs/PLUGIN_REGISTRY.md`'s 9 columns are
  already the target shape.

## MVP Definition (v5.0 Workstream H Scope)

### Launch With (workstream H, this milestone)

- [ ] `plugins install <repo>[@ref]` — clone into `plugins/`, validate naming
      convention and `PLUGIN_API_VERSION`, default-pin to the resolved commit SHA
      (not the branch) — table stakes + top differentiator, same mechanism
- [ ] `plugins list` extended with provenance (source URL, installed ref) —
      table stakes, additive to existing command
- [ ] `plugins remove <name>` — table stakes, mechanically trivial given
      per-file isolation
- [ ] `plugins update <name>` — table stakes, depends on provenance tracking
- [ ] Install-time consent gate showing safety metadata (difficulty,
      requires_proxy, requires_captcha, and whether `auto_buy` is a real
      purchase path) and requiring a typed confirmation naming the source repo —
      table stakes + two differentiators combined into one prompt
- [ ] SECURITY.md extended (not replaced) with third-party-plugin-specific
      disclaimer language, following the existing "Legal Scope and Disclaimer"
      section's tone and cross-reference pattern

### Add After Validation (post-workstream-H, still v5.0-adjacent or early v5.x)

- [ ] Machine-readable registry file replacing the REG-01 wiki-table workflow,
      consumed optionally by `plugins install` to show maintainer/last-verified
      data even for non-bundled plugins — worth doing once the install/consent
      flow itself is proven, not before

### Future Consideration (explicitly deferred, on the record)

- [ ] Process isolation / sandboxing for plugin execution — already listed in
      PROJECT.md's Future Candidate Directions as the real fix, deliberately
      out of scope for v5.0's cost/scope profile
- [ ] Any hosted marketplace, ratings, or telemetry surface — anti-features,
      not partially-deferred features; do not resurrect without a staffing
      change to the project's single-maintainer posture

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---|---|---|---|
| `plugins install <repo>[@ref]` with default commit pinning | HIGH | MEDIUM | P1 |
| Install-time consent gate (safety metadata + typed confirm) | HIGH | LOW | P1 |
| `plugins list` provenance columns | MEDIUM | LOW | P1 |
| `plugins remove <name>` | MEDIUM | LOW | P1 |
| `plugins update <name>` | MEDIUM | LOW-MEDIUM | P1 |
| SECURITY.md third-party-plugin disclaimer extension | HIGH | LOW | P1 |
| "Can spend money" warning tier | MEDIUM-HIGH | MEDIUM | P2 |
| Machine-readable registry (replaces REG-01) | MEDIUM | MEDIUM | P2 |
| Process isolation / sandboxing | HIGH (if ever built) | HIGH | P3 (deferred, tracked) |
| Hosted marketplace / ratings / telemetry | LOW (for this project's scale) | HIGH | Rejected, not deferred |

**Priority key:**
- P1: In scope for v5.0 workstream H
- P2: Natural next step once H ships and is validated
- P3: On the roadmap as a future milestone candidate, not this one

## Sources

- [pip: VCS Support](https://pip.pypa.io/en/stable/topics/vcs-support/)
- [pipx (GitHub)](https://github.com/pypa/pipx)
- [Obsidian: Community plugins](https://obsidian.md/help/community-plugins)
- [Obsidian: Plugin security](https://github.com/obsidianmd/obsidian-help/blob/master/en/Extending%20Obsidian/Plugin%20security.md)
- [VS Code: Extension Marketplace](https://code.visualstudio.com/docs/configure/extensions/extension-marketplace)
- [VS Code: Extension runtime security](https://code.visualstudio.com/docs/configure/extensions/extension-runtime-security)
- [VS Code: Workspace Trust](https://code.visualstudio.com/docs/editing/workspaces/workspace-trust)
- [HACS](https://www.hacs.xyz/) / [hacs/integration (GitHub)](https://github.com/hacs/integration) / [HACS: Publish requirements](https://www.hacs.xyz/docs/publish/start/)
- [lazy.nvim (GitHub)](https://github.com/folke/lazy.nvim) / [lazy.nvim lockfile docs](https://lazy.folke.io/usage/lockfile)
- [Package Control: Usage](https://packagecontrol.io/docs/usage) / [Package Control (GitHub)](https://github.com/wbond/package_control)
- [ohmyzsh/ohmyzsh (GitHub)](https://github.com/ohmyzsh/ohmyzsh) / [ohmyzsh wiki: Plugins](https://github.com/ohmyzsh/ohmyzsh/wiki/plugins)
- [GitHub CLI: Using GitHub CLI extensions](https://docs.github.com/en/github-cli/github-cli/using-github-cli-extensions)
- [GitHub CLI: gh extension install manual](https://cli.github.com/manual/gh_extension_install)
- ShopPyBot repo (already read): `.planning/PROJECT.md`, `.planning/seeds/SEED-003-remote-plugin-manager-and-extensibility-framework.md`, `docs/PLUGIN_REGISTRY.md`, `plugins/PLUGIN_DEV.md`, `SECURITY.md`, `CONTRIBUTING.md`

---
*Feature research for: ShopPyBot v5.0 workstream H — remote plugin manager and third-party liability disclaimer (SEED-003)*
*Researched: 2026-08-02*
