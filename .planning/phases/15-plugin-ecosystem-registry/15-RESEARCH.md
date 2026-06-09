# Phase 15: Plugin Ecosystem Registry - Research

**Researched:** 2026-06-09
**Domain:** Python argparse CLI extension, ABC class attributes, in-process plugin registry enumeration, contributor docs
**Confidence:** HIGH

## Summary

Phase 15 is a documentation and lightweight code phase. The three deliverables are:
(1) three additive class attributes on the plugin ABC, (2) a new `plugins list` CLI
subcommand that reads the in-process registry with no network call, and (3) updated
contributor docs. All integration points are well-understood from reading the live
source.

The primary risk is getting the `BotService` API seam right so `handle_plugins_list`
can access `_all_plugins` without violating MOD-02 (CLI modules import only
`BotService`, never `core.registry` or `core.orchestrator` directly). The
recommended approach is adding a `list_plugins()` method to `BotService` that
instantiates a `PluginRegistry` with `AppConfig()` and the standard plugins dir,
then returns a list of plain dicts. This mirrors how `list_items()` calls
`get_items_sync()` -- the service owns the data-access delegation.

**Primary recommendation:** Add `list_plugins()` to `BotService`, wire a new
`core/cli/plugins.py` module following the exact `items.py` pattern, register the
`plugins` nested subparser in `core/cli/__init__.py`, and update the three doc files.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Plugin ABC Attributes (non-breaking):**
- Add class attributes to the plugin base (`core/plugin_base.py`):
  - `difficulty: Literal["easy", "medium", "hard"] = "medium"`
  - `requires_proxy: bool = False`
  - `requires_captcha: bool = False`
- Existing plugins that don't declare these continue to load with the defaults.
  NO ABC version bump that breaks loading (additive class attributes only; if
  PLUGIN_API_VERSION convention requires a note, treat as a non-breaking minor).
- `difficulty` is validated against the three allowed values.

**CLI: `shoppybot plugins list`:**
- New subcommand under the existing argparse `set_defaults(func=...)` dispatch.
- Mirror `items list` / `config` command structure; new `core/cli/plugins.py`.
- Default output: human-readable aligned plain-text table with columns: name,
  domain patterns, difficulty, requires_proxy, requires_captcha.
- `--json` flag emits the same data as JSON for scripting/agents.
- NO network call -- reads only the locally loaded plugin registry.

**Documentation:**
- GitHub wiki registry table SPEC in `docs/PLUGIN_REGISTRY.md` with required
  fields: name, platform, domain patterns, maintainer, anti-detection difficulty,
  methods implemented, last-verified date, proxy-required, captcha-required.
- Update `CONTRIBUTING.md` and `.github/PULL_REQUEST_TEMPLATE.md` to require
  contributors to supply `difficulty`, `requires_proxy`, `requires_captcha` for
  new plugin submissions.

### Claude's Discretion

Exact module/file names for the new CLI command, table-formatting helper, how the
loaded-plugin list is enumerated from the registry, the precise wiki-table doc
location/format, and PR-template wording -- all at Claude's discretion, guided by
existing `core/cli/` and `core/registry.py` conventions.

### Deferred Ideas (OUT OF SCOPE)

- Plugin marketplace / ratings system.
- Auto-generated plugin health testing against live retail.
- Price monitoring (Phase 16).
- Broad v3.0 test hardening (Phase 17).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| REG-01 | Maintainers can list community plugins in a GitHub wiki registry table with required fields | `docs/PLUGIN_REGISTRY.md` spec doc; fields enumerated in CONTEXT |
| REG-02 | Plugin authors can declare `difficulty`, `requires_proxy`, `requires_captcha` as class attributes (non-breaking ABC additions with sensible defaults) | Additive class attrs with defaults; `plugin_base.py` analysis confirms this is safe |
| REG-03 | User can run `shoppybot plugins list` to see all locally loaded plugins (no network call) | `BotService.list_plugins()` + `core/cli/plugins.py`; `_all_plugins` is the source |
| REG-04 | Contributors guided via updated `CONTRIBUTING.md` and PR template | Both files exist and are well-structured; require checklist additions only |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| ABC attribute declaration | `core/plugin_base.py` | -- | Single source of truth for all plugin contracts |
| Plugin enumeration for CLI | `core/service.py` (BotService) | `core/registry.py` (delegated) | MOD-02: CLI modules never import registry directly |
| CLI subcommand dispatch | `core/cli/__init__.py` | `core/cli/plugins.py` | Consistent with existing items/config pattern |
| Table + JSON formatting | `core/cli/plugins.py` | -- | Self-contained per command module convention |
| Wiki registry spec | `docs/PLUGIN_REGISTRY.md` | -- | docs/ is the repo's reference material location |
| Contributor requirements | `CONTRIBUTING.md` + `.github/PULL_REQUEST_TEMPLATE.md` | -- | Both files already exist and have plugin sections |

## Standard Stack

No new dependencies. All work uses stdlib (`argparse`, `json`, `typing.Literal`,
`importlib`) and existing project modules (`core/plugin_base.py`,
`core/registry.py`, `core/service.py`).

### Libraries in Use (no additions)

| Module | Purpose | Notes |
|--------|---------|-------|
| `argparse` (stdlib) | CLI subcommand + `--json` flag | Already used; add_argument pattern confirmed |
| `json` (stdlib) | `--json` output serialization | No new dep; `json.dumps(data, indent=2)` |
| `typing.Literal` (stdlib) | `difficulty` type annotation | Python 3.8+; project already uses type hints |
| `core/registry.py` | Plugin discovery + `_all_plugins` list | Read from `BotService.list_plugins()` only |
| `core/service.py` | `BotService.list_plugins()` new method | Mirrors `list_items()` delegation pattern |

## Package Legitimacy Audit

No external packages are added in this phase. This section is not applicable.

## Architecture Patterns

### System Architecture Diagram

```
shoppybot plugins list [--json]
         |
         v
core/service.py: main()
  build_parser() -> args.func = handle_plugins_list
  BotService() constructed
  sys.exit(args.func(args, svc) or 0)
         |
         v
core/cli/plugins.py: handle_plugins_list(args, svc)
  rows = svc.list_plugins()      <-- no network
         |
         v
core/service.py: BotService.list_plugins()
  PluginRegistry(cfg, plugins_dir)  <-- _discover_plugins runs
  returns [{"name":..., "domain_patterns":...,
            "difficulty":..., "requires_proxy":...,
            "requires_captcha":...}, ...]
         |
         v
handle_plugins_list: format as table or JSON -> print -> return 0
```

### Recommended Project Structure

New and modified files only:

```
core/
  plugin_base.py       # add 3 class attrs + Literal import
  service.py           # add list_plugins() method
  cli/
    __init__.py        # add plugins nested subparser block
    plugins.py         # new: handle_plugins_list + _format_plugins_table

docs/
  PLUGIN_REGISTRY.md   # new: wiki registry table spec

CONTRIBUTING.md        # add difficulty/proxy/captcha to checklist
.github/
  PULL_REQUEST_TEMPLATE.md  # add 3 fields to plugin checklist

tests/
  test_cli_plugins.py  # new: mirrors test_cli_items.py pattern
  test_plugin_base.py  # extend: 3 new attribute-default assertions
```

### Pattern 1: ABC Additive Class Attribute (non-breaking)

**What:** Add class-level attributes with defaults directly on `RetailerPlugin`.
Subclasses that do not declare them inherit the base-class value. Python class
attribute lookup guarantees this is safe -- no `__init__` change required.

**Why non-breaking:** `PluginRegistry._discover_plugins` calls `cls(config)` on
discovered plugin classes. Adding class attributes (not abstract methods) does not
change the ABC's `__abstractmethods__` frozenset. Existing plugins that omit the
attributes will simply inherit the defaults at `getattr(plugin, "difficulty")` read
time.

**Source:** [VERIFIED: read core/plugin_base.py line 5-60] [VERIFIED: read
tests/test_plugin_base.py] -- current ABC structure confirmed.

```python
# Source: core/plugin_base.py (to be modified)
from typing import Literal

PLUGIN_API_VERSION = 2  # no bump required; additive attrs are non-breaking

class RetailerPlugin(ABC):
    domain_patterns: list[str]

    # REG-02: additive registry attrs -- existing plugins inherit these defaults
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    requires_proxy: bool = False
    requires_captcha: bool = False
```

**PLUGIN_API_VERSION note:** `PLUGIN_API_VERSION` is currently `2` and the
STATE.md decision log records "PLUGIN_API_VERSION stays 2; no ABC changes" for
Phase 14. Adding class attributes with defaults is the same class of additive
change -- no version bump is needed. The constant is documented as a
"bumped from 1; v1 subclasses are not compatible" guard; this change has no
compatibility implications. [VERIFIED: read core/plugin_base.py line 5]

### Pattern 2: BotService.list_plugins() delegation

**What:** A new read-only method on `BotService` that constructs a fresh
`PluginRegistry` (discovery only, no browser setup), walks `_all_plugins`, and
returns a list of plain dicts. The CLI handler never imports `core.registry`
directly (MOD-02 compliance).

**Source:** [VERIFIED: read core/service.py lines 64-75] -- `list_items()` is the
direct model.

```python
# Source: core/service.py (to be modified)
# Add at the end of the read-only accessors block (after list_items)

def list_plugins(self) -> list[dict]:
    """Return metadata for all locally discovered plugins (no browser launch).

    Reads domain_patterns, difficulty, requires_proxy, requires_captcha from
    each discovered plugin class. No network call. (REG-03)
    """
    from pathlib import Path
    from core.registry import PluginRegistry

    plugins_dir = Path(__file__).parent.parent / "plugins"
    registry = PluginRegistry(self._cfg, plugins_dir)
    rows = []
    for plugin in registry._all_plugins:
        rows.append({
            "name": type(plugin).__name__,
            "domain_patterns": plugin.domain_patterns,
            "difficulty": getattr(plugin, "difficulty", "medium"),
            "requires_proxy": getattr(plugin, "requires_proxy", False),
            "requires_captcha": getattr(plugin, "requires_captcha", False),
        })
    return rows
```

**Note on `getattr` with defaults:** Using `getattr(plugin, "difficulty",
"medium")` is a belt-and-suspenders guard. Once the ABC declares the attribute
with a default, plain `plugin.difficulty` works. Using `getattr` makes the
accessor resilient to edge-case external plugins that were compiled against an
older ABC and placed in the plugins dir without a reinstall.

### Pattern 3: Nested argparse subparser (mirror items pattern)

**What:** Register a `plugins` top-level subparser with a `list` leaf. The
`_require_subcommand` helper already exists in `core/cli/__init__.py` and handles
bare `shoppybot plugins` (no leaf) with exit code 2.

**Source:** [VERIFIED: read core/cli/__init__.py lines 51-92] -- items pattern
is the exact template.

```python
# Source: core/cli/__init__.py (addition to build_parser())

from core.cli.plugins import handle_plugins_list

# --- plugins ---
plugins_p = sub.add_parser("plugins", help="Inspect loaded plugins.")
plugins_sub = plugins_p.add_subparsers(dest="plugins_command")

list_p = plugins_sub.add_parser("list", help="List all loaded plugins.")
list_p.add_argument(
    "--json",
    action="store_true",
    default=False,
    help="Emit JSON instead of a text table.",
)
list_p.set_defaults(func=handle_plugins_list)

# Bare `shoppybot plugins` exits 2, does not start the bot.
plugins_p.set_defaults(func=_require_subcommand(plugins_p))
```

### Pattern 4: core/cli/plugins.py command module

**What:** Mirrors `core/cli/items.py` exactly -- one `_format_plugins_table()`
helper and one `handle_plugins_list(args, svc)` handler. The `--json` path uses
`json.dumps`. [VERIFIED: read core/cli/items.py]

```python
# Source: core/cli/plugins.py (new file)
import json
import sys

from core.service import BotService


def _format_plugins_table(rows: list[dict]) -> str:
    """Return a left-justified aligned text table for plugin rows."""
    if not rows:
        return "No plugins loaded."
    headers = ("Name", "Domain Patterns", "Difficulty", "Proxy", "CAPTCHA")
    col_values = [
        [r["name"] for r in rows],
        [", ".join(r["domain_patterns"]) for r in rows],
        [r["difficulty"] for r in rows],
        [str(r["requires_proxy"]) for r in rows],
        [str(r["requires_captcha"]) for r in rows],
    ]
    widths = [
        max(len(h), max(len(v) for v in vals))
        for h, vals in zip(headers, col_values)
    ]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    lines = [fmt.format(*headers), "  ".join("-" * w for w in widths)]
    for i, r in enumerate(rows):
        lines.append(fmt.format(
            r["name"],
            ", ".join(r["domain_patterns"]),
            r["difficulty"],
            str(r["requires_proxy"]),
            str(r["requires_captcha"]),
        ))
    return "\n".join(lines)


def handle_plugins_list(args, svc: BotService) -> int:
    """Print loaded plugins as a text table or JSON (--json flag)."""
    rows = svc.list_plugins()
    if getattr(args, "json", False):
        print(json.dumps(rows, indent=2))
    else:
        print(_format_plugins_table(rows))
    return 0
```

### Pattern 5: `--json` flag convention

`--json` does not exist in any current CLI module. [VERIFIED: grep of
`core/cli/` found no `--json` references.] This is the first use. The pattern
above (argparse `action="store_true"`, `getattr(args, "json", False)`) is
idiomatic argparse and consistent with how `--auto-buy` is handled in `items add`.

### Anti-Patterns to Avoid

- **Importing `core.registry` in `core/cli/plugins.py` directly:** Violates
  MOD-02. The CLI layer must go through `BotService` only.
- **Calling `registry.setup_for_items()` in `list_plugins()`:** This launches
  browsers. `list_plugins()` must use `_all_plugins` only (plugin objects
  constructed by `PluginRegistry.__init__`, no `setup()` call).
- **Bumping `PLUGIN_API_VERSION` to 3:** No ABC structural change is made.
  Version stays at 2. A comment noting the additive attrs is sufficient.
- **Using `inspect.getmembers` or `__subclasses__()` in the CLI handler:** The
  registry already does discovery correctly. Reuse it via `BotService`.
- **Reading `_active_plugins` instead of `_all_plugins`:** Active plugins only
  exist after `setup_for_items()` runs (lazy browser launch). For `plugins list`
  the bot is not running, so `_active_plugins` is always empty. Use `_all_plugins`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Aligned text table | Custom padding logic from scratch | Mirror `_format_items_table` from `items.py` | Identical pattern; max-width column sizing is already proven |
| Plugin discovery | Re-implement importlib scan | `PluginRegistry.__init__` via `list_plugins()` | Registry already handles naming convention, import errors, and class extraction |
| JSON serialization | Manual string concat | `json.dumps(rows, indent=2)` | Handles escaping, Unicode, nesting |

**Key insight:** The registry already does all the hard work. The CLI is only a
read-path over data the registry already computed.

## Common Pitfalls

### Pitfall 1: `_active_plugins` is empty at CLI time

**What goes wrong:** `handle_plugins_list` reads `svc._registry._active_plugins`
and gets an empty list. No error, just silent "No plugins loaded."

**Why it happens:** `_active_plugins` is only populated after `setup_for_items()`
runs, which launches browsers. The CLI runs before any bot loop.

**How to avoid:** Always use `_all_plugins` as the source for `plugins list`. The
`list_plugins()` method constructs a fresh `PluginRegistry` and reads
`registry._all_plugins`. [VERIFIED: read core/registry.py lines 60-71]

**Warning signs:** Test returns "No plugins loaded" even with plugin files present.

### Pitfall 2: `PluginRegistry.__init__` requires a valid `plugins_dir`

**What goes wrong:** Passing a non-existent path produces an empty list (the
registry logs WARNING and returns `[]` from `_discover_plugins`).

**How to avoid:** Derive the path as `Path(__file__).parent.parent / "plugins"`.
This is the same pattern used in tests via the `tmp_plugins_dir` fixture.
[VERIFIED: read core/registry.py lines 19-30]

### Pitfall 3: `difficulty` validation must be explicit

**What goes wrong:** A plugin author typos `difficulty = "Easy"` (capital E) or
uses an unknown string. The default is silently inherited, masking the error.

**How to avoid:** Add a `__init_subclass__` hook on `RetailerPlugin` that raises
`ValueError` when `difficulty` is set but not in `{"easy", "medium", "hard"}`. This
validates at class-definition time, not at runtime. Alternatively, validate in
`_discover_plugins` and log WARNING + skip. The CONTEXT says "difficulty is
validated against the three allowed values" -- the planner must decide which
enforcement point to use. `__init_subclass__` is cleanest.

**Warning signs:** `plugins list` shows a plugin with a typo'd difficulty string
that was supposed to raise an error.

### Pitfall 4: MOD-02 violation in the CLI handler

**What goes wrong:** `core/cli/plugins.py` does `from core.registry import
PluginRegistry` directly. This is explicitly forbidden by the MOD-02 constraint
(CLI modules import only `BotService`, never `core.registry`).

**How to avoid:** All registry access goes through `svc.list_plugins()` where
`svc` is the `BotService` instance passed by `main()`. [VERIFIED: read
core/cli/items.py line 1-8 -- only `sys` and `BotService` imported]

### Pitfall 5: STATE.md Pitfall 5.1 -- GitHub wiki is directory listing only

**What goes wrong:** The `docs/PLUGIN_REGISTRY.md` file describes a GitHub wiki
page that does not yet exist. Confusion between in-repo spec and out-of-repo wiki.

**How to avoid:** The in-repo file (`docs/PLUGIN_REGISTRY.md`) is the SPEC (what
the wiki table must contain). The actual GitHub wiki page is created by a
maintainer manually. The spec file must make this distinction clear. This is
pre-flagged in STATE.md: "GitHub wiki is directory listing only; all API contract
docs live in PLUGIN_DEV.md in-repo (PITFALLS 5.1)." [VERIFIED: read
.planning/STATE.md line 83]

### Pitfall 6: PR template anti-detection field already partially exists

**What goes wrong:** Adding duplicate fields to the PR template.

**How to avoid:** The current `.github/PULL_REQUEST_TEMPLATE.md` already has an
"Anti-detection risk" free-text field in the Risk Declaration section.
[VERIFIED: read .github/PULL_REQUEST_TEMPLATE.md lines 53-58] The update must
REPLACE the free-text risk declaration with structured checkboxes for `difficulty`,
`requires_proxy`, `requires_captcha`, and update the Risk Declaration section
accordingly. Do not add a second risk section.

## Code Examples

### Reading all plugin metadata from a freshly constructed registry

```python
# Source: core/registry.py lines 60-71 [VERIFIED]
# _all_plugins is populated in __init__ by _discover_plugins
# No setup() call needed; plugin instances are constructed immediately

registry = PluginRegistry(config, plugins_dir)
for plugin in registry._all_plugins:
    name = type(plugin).__name__
    patterns = plugin.domain_patterns        # class attr, always present
    difficulty = getattr(plugin, "difficulty", "medium")   # new attr
    requires_proxy = getattr(plugin, "requires_proxy", False)
    requires_captcha = getattr(plugin, "requires_captcha", False)
```

### Existing aligned table pattern to mirror

```python
# Source: core/cli/items.py lines 11-28 [VERIFIED]
def _format_items_table(rows: list) -> str:
    headers = ("Name", "URL", "Auto-Buy", "Qty", "Purchased")
    if not rows:
        return "No items tracked."
    widths = [
        max(len(h), max(len(str(r[i])) for r in rows))
        for i, h in enumerate(headers)
    ]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    lines = [fmt.format(*headers), "  ".join("-" * w for w in widths)]
    for r in rows:
        lines.append(fmt.format(r[0], r[1], bool(r[2]), r[3], bool(r[4])))
    return "\n".join(lines)
```

### Handler dispatch pattern (confirmed from service.py main())

```python
# Source: core/service.py lines 196-206 [VERIFIED]
# All handlers receive (args, BotService()) and return int | None
# sys.exit(args.func(args, BotService()) or 0)
```

### Test pattern for CLI commands (mirror test_cli_items.py)

```python
# Source: tests/test_cli_items.py lines 7-19 [VERIFIED]
def test_plugins_list_table(capsys, tmp_data_dir):
    from core.service import main
    mock_svc = MagicMock()
    mock_svc.list_plugins.return_value = [
        {"name": "FakePlugin", "domain_patterns": ["fake.com"],
         "difficulty": "easy", "requires_proxy": False, "requires_captcha": False}
    ]
    with patch("core.service.BotService", return_value=mock_svc):
        with pytest.raises(SystemExit) as exc_info:
            main(["plugins", "list"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "FakePlugin" in out
    assert "fake.com" in out
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Free-text "Anti-detection risk" in PR template | Structured `difficulty`/`requires_proxy`/`requires_captcha` class attrs + checklist items | Phase 15 | Consistent machine-readable metadata for registry |

**Existing (to be extended):**
- `CONTRIBUTING.md` Plugin Submission Checklist: currently 6 items, no structured
  difficulty/proxy/captcha fields. [VERIFIED: read CONTRIBUTING.md lines 64-98]
- `.github/PULL_REQUEST_TEMPLATE.md`: currently has a free-text "Anti-detection
  risk" + Rationale in the Risk Declaration. [VERIFIED: read PULL_REQUEST_TEMPLATE.md]
- `plugins/PLUGIN_DEV.md`: the ABC contract table (section 2) does not list the
  new attributes. This file should also be updated to document `difficulty`,
  `requires_proxy`, `requires_captcha` in the method/attribute table. [VERIFIED:
  read plugins/PLUGIN_DEV.md lines 44-58]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `plugins_dir` path computed as `Path(__file__).parent.parent / "plugins"` in `list_plugins()` | Pattern 2 | Wrong path = empty plugin list; low risk, easy to verify in test |
| A2 | `__init_subclass__` is the recommended enforcement point for `difficulty` validation | Pitfall 3 | Alternative is validate-on-read in `list_plugins()`; behavior difference is when the error surfaces |

## Open Questions (RESOLVED)

1. **`difficulty` validation enforcement point**
   - **RESOLVED:** Use `__init_subclass__` (fail-fast at import for an explicitly-invalid value; plugins omitting `difficulty` use the default and are unaffected). Implemented in 15-01 Task 1.
   - What we know: CONTEXT says "difficulty is validated against the three allowed
     values" but does not specify when.
   - What's unclear: `__init_subclass__` raises at import time; validate-in-
     `_discover_plugins` raises at discovery time and logs+skips; validate-in-
     `list_plugins` raises at CLI time only.
   - Recommendation: `__init_subclass__` is cleanest (fails fast, error is at the
     plugin author's code, not the user's runtime). If breaking import is too
     aggressive, use `_discover_plugins` log+skip (already the pattern for other
     import errors).

2. **`plugins/PLUGIN_DEV.md` update scope**
   - **RESOLVED:** Include `PLUGIN_DEV.md` in the docs update (primary plugin-author reference). Implemented in 15-03 Task 2.
   - What we know: the file's ABC table does not mention the new attributes.
   - What's unclear: CONTEXT.md lists "update CONTRIBUTING.md and PR template"
     but does not explicitly list `PLUGIN_DEV.md`.
   - Recommendation: include `PLUGIN_DEV.md` in the update -- it is the primary
     plugin author reference and omitting the new attributes from its table would
     cause contributor confusion. Fits within "documentation" scope and is
     consistent with CONTEXT's intent.

## Environment Availability

Step 2.6: SKIPPED -- this phase is code and doc changes only; no external tools,
services, CLIs, databases, or runtimes beyond the project's existing Python
environment are required.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (asyncio_mode=auto via pytest-asyncio) |
| Config file | `pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_cli_plugins.py tests/test_plugin_base.py -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| REG-02 | `MinimalPlugin` inherits `difficulty="medium"`, `requires_proxy=False`, `requires_captcha=False` | unit | `pytest tests/test_plugin_base.py -q` | Exists -- add assertions |
| REG-02 | Plugin that overrides `difficulty="easy"` has correct value | unit | `pytest tests/test_plugin_base.py -q` | Exists -- add test |
| REG-02 | Existing plugins (Amazon, BestBuy) still load with defaults | unit | `pytest tests/test_plugin_base.py -q` | Exists -- add smoke |
| REG-03 | `main(["plugins","list"])` prints table with name + domain patterns | unit | `pytest tests/test_cli_plugins.py::test_plugins_list_table -q` | Wave 0 gap |
| REG-03 | `main(["plugins","list","--json"])` prints valid JSON | unit | `pytest tests/test_cli_plugins.py::test_plugins_list_json -q` | Wave 0 gap |
| REG-03 | `main(["plugins"])` (no leaf) exits 2 and does not start bot | unit | `pytest tests/test_cli_plugins.py::test_plugins_no_leaf_exits_2 -q` | Wave 0 gap |
| REG-03 | `main(["plugins","list"])` with empty plugin dir prints "No plugins loaded." | unit | `pytest tests/test_cli_plugins.py::test_plugins_list_empty -q` | Wave 0 gap |
| REG-01 | `docs/PLUGIN_REGISTRY.md` exists and contains all 9 required field names | doc-presence | `pytest tests/test_docs.py::test_plugin_registry_doc` or inline assertion | May need new test file |
| REG-04 | `CONTRIBUTING.md` contains `difficulty`, `requires_proxy`, `requires_captcha` | doc-presence | `pytest tests/test_docs.py::test_contributing_fields` | May need new test file |

### Sampling Rate

- Per task commit: `pytest tests/test_cli_plugins.py tests/test_plugin_base.py -q`
- Per wave merge: `pytest tests/ -q`
- Phase gate: Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_cli_plugins.py` -- covers REG-03 (4 tests listed above)
- [ ] `tests/test_plugin_base.py` additions -- 3 new assertions for REG-02
  defaults + 1 override test + 1 existing-plugin smoke test (extend existing file)
- [ ] `tests/test_docs.py` -- covers REG-01 and REG-04 doc-presence checks
  (may already exist; check before creating)

## Security Domain

This phase adds no authentication, session management, cryptography, or input from
external sources. The only user-facing input is the `--json` flag (boolean; no
injection surface) and the `difficulty` class attribute value (validated against an
allow-list of 3 strings at class definition time).

No ASVS categories are applicable. The one relevant security rule from
CONTRIBUTING.md and the PR template update is the existing credential policy
(no secrets committed); this phase does not change that policy.

## Sources

### Primary (HIGH confidence)

- `core/cli/__init__.py` (read in full) -- exact argparse dispatch pattern,
  `_require_subcommand` helper, nested subparser registration
- `core/cli/items.py` (read in full) -- handler signature, table formatter,
  `BotService` delegation pattern
- `core/registry.py` (read in full) -- `PluginRegistry.__init__`, `_all_plugins`
  list, `_discover_plugins`, `setup_for_items` distinction
- `core/plugin_base.py` (read in full) -- current ABC structure, `PLUGIN_API_VERSION`
- `core/service.py` (read in full) -- `main()` dispatch, `list_items()` pattern,
  `BotService` constructor
- `plugins/shopbot_plugin_amazon.py` (read in full) -- `domain_patterns` declaration,
  platform name, attribute structure
- `plugins/shopbot_plugin_bestbuy.py` (header read) -- confirms `domain_patterns`
  pattern is consistent
- `tests/conftest.py` (read in full) -- `tmp_plugins_dir` fixture, `fake_plugin`
  factory, `tmp_data_dir` fixture
- `tests/test_cli_items.py` (read in full) -- exact test pattern to mirror
- `tests/test_plugin_base.py` (read in full) -- existing assertions to extend
- `CONTRIBUTING.md` (read in full) -- current plugin submission checklist
- `.github/PULL_REQUEST_TEMPLATE.md` (read in full) -- existing risk declaration
- `plugins/PLUGIN_DEV.md` (read in full) -- ABC contract table, attribute docs

### Secondary (MEDIUM confidence)

- `.planning/STATE.md` -- Phase 14 decision "PLUGIN_API_VERSION stays 2" confirms
  version bump policy; Pitfall 5.1 confirms wiki-vs-repo distinction

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new deps; all integration points read from live source
- Architecture: HIGH -- exact file paths, method names, and line numbers cited
- Pitfalls: HIGH -- each pitfall derived from reading actual code, not assumptions

**Research date:** 2026-06-09
**Valid until:** 2026-07-09 (stable codebase; no external dependencies to drift)
