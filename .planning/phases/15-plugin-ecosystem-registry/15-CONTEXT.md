# Phase 15: Plugin Ecosystem Registry - Context

**Gathered:** 2026-06-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Make community plugins discoverable and locally inspectable. Add three non-breaking class attributes to the plugin ABC (`difficulty`, `requires_proxy`, `requires_captcha`) with sensible defaults so existing plugins keep loading. Add a `shoppybot plugins list` CLI command that displays all locally loaded plugins (domain patterns, difficulty, proxy/captcha flags) with NO network call. Provide a GitHub wiki registry table spec and update CONTRIBUTING.md + the PR template to require the new fields for plugin submissions.

</domain>

<decisions>
## Implementation Decisions

### Plugin ABC Attributes (non-breaking)
- Add class attributes to the plugin base (`core/plugin_base.py`):
  - `difficulty: Literal["easy", "medium", "hard"] = "medium"` — anti-detection difficulty
  - `requires_proxy: bool = False`
  - `requires_captcha: bool = False`
- Existing plugins that don't declare these continue to load with the defaults (medium / False / False). NO ABC version bump that breaks loading (additive class attributes only; if PLUGIN_API_VERSION convention requires a note, treat as a non-breaking minor — at Claude's discretion, but loading of existing plugins MUST NOT break).
- `difficulty` is validated against the three allowed values.

### CLI: `shoppybot plugins list`
- New subcommand under the existing argparse `set_defaults(func=...)` dispatch in `core/cli/` (mirror `items list` / `config` command structure; likely a new `core/cli/plugins.py`).
- Default output: human-readable aligned plain-text table with columns: name, domain patterns, difficulty, requires_proxy, requires_captcha.
- Add a `--json` flag that emits the same data as JSON for scripting/agents.
- NO network call — reads only the locally loaded plugin registry.

### Documentation
- GitHub wiki registry table SPEC (a doc in the repo, e.g. `docs/PLUGIN_REGISTRY.md`, describing the wiki table) with required fields: name, platform, domain patterns, maintainer, anti-detection difficulty, methods implemented, last-verified date, proxy-required, captcha-required.
- Update `CONTRIBUTING.md` and the PR template (`.github/PULL_REQUEST_TEMPLATE.md` or existing) to require contributors to supply `difficulty`, `requires_proxy`, `requires_captcha` for new plugin submissions.

### Claude's Discretion
- Exact module/file names for the new CLI command, table-formatting helper, how the loaded-plugin list is enumerated from the registry, the precise wiki-table doc location/format, and PR-template wording — all at Claude's discretion, guided by existing `core/cli/` and `core/registry.py` conventions.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/cli/__init__.py` — argparse `build_parser()` with `sub.add_parser(...)` + `set_defaults(func=...)` dispatch; `items` uses a nested subparser group (`items list/add/remove`). Mirror this for `plugins list`. Per-command modules live in `core/cli/` (config_cmd.py, items.py, run.py, setup.py, web.py).
- `core/registry.py` — the plugin registry that loads plugins; source of the "locally loaded plugins" list for `plugins list` (no network).
- `core/plugin_base.py` — the ABC where the 3 new class attributes are added; existing plugins in `plugins/` inherit them.

### Established Patterns
- Python argparse subcommands with `set_defaults(func=...)`; `_require_subcommand` helper for group-without-leaf. pytest under `tests/` for CLI + ABC defaults.
- Phases 13/14 added concrete helpers/attributes without breaking plugin loading.

### Integration Points
- `plugins list` enumerates `core/registry.py`'s loaded plugins. New attributes read off each plugin class. CONTRIBUTING.md / PR template live at repo root / `.github/`.

</code_context>

<specifics>
## Specific Ideas

- `plugins list` MUST NOT make a network call (success criterion 3).
- Existing plugins MUST keep loading unchanged (success criterion 1) — additive defaults only.
- Wiki registry fields are fixed by criterion 2; the repo doc specifies them.

</specifics>

<deferred>
## Deferred Ideas

- Plugin marketplace / ratings system — explicitly out of scope (v3.0 Out of Scope list).
- Auto-generated plugin health testing against live retail — out of scope.
- Price monitoring — Phase 16.
- Broad v3.0 test hardening — Phase 17.

</deferred>
