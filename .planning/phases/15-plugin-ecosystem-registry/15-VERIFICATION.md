---
phase: 15-plugin-ecosystem-registry
verified: 2026-06-09T00:00:00Z
status: human_needed
score: 8/8 must-haves verified (all in-repo deliverables)
overrides_applied: 0
human_verification:
  - test: "Open the project GitHub wiki and create the Plugin Registry page following docs/PLUGIN_REGISTRY.md"
    expected: "A wiki page named 'Plugin Registry' exists with the 9-column table described in the spec; at minimum the built-in Amazon plugin row is present"
    why_human: "The GitHub wiki is an external surface not in this repository; it cannot be created or verified programmatically via grep or test"
---

# Phase 15: Plugin Ecosystem Registry Verification Report

**Phase Goal:** Community contributors have a discoverable registry with clear difficulty ratings, and users can inspect loaded plugins locally without a network call.
**Verified:** 2026-06-09
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Plugin authors can declare difficulty, requires_proxy, requires_captcha as class attributes | VERIFIED | `core/plugin_base.py` lines 22-24: three class attrs with defaults on `RetailerPlugin` ABC |
| 2 | A plugin omitting these attrs loads with defaults medium / False / False | VERIFIED | `__init_subclass__` only validates; omitted attrs inherit from class body; `test_defaults` confirms |
| 3 | All 7 existing shopbot_plugin_*.py plugins still load unchanged | VERIFIED | `test_existing_plugins_load` asserts `len >= 7`; 7 files confirmed in `plugins/` |
| 4 | A plugin declaring an out-of-range difficulty value fails at class-definition time | VERIFIED | `__init_subclass__` raises `ValueError` for any value not in `{"easy","medium","hard"}`; `test_invalid_difficulty_raises` confirms |
| 5 | Running `shoppybot plugins list` prints an aligned table of loaded plugins | VERIFIED | `core/cli/plugins.py`: `_format_plugins_table()` + `handle_plugins_list()`; registered in `core/cli/__init__.py` lines 119-132; `test_plugins_list_table` confirms |
| 6 | `shoppybot plugins list --json` prints valid parseable JSON | VERIFIED | `handle_plugins_list` branches on `args.json`; `test_plugins_list_json` confirms `json.loads` succeeds |
| 7 | `shoppybot plugins list` makes no network call | VERIFIED | `BotService.list_plugins()` reads `registry._all_plugins` only (no `setup()`/browser); `test_plugins_list_no_network` patches `socket.socket` to raise and asserts exit 0 |
| 8 | docs/PLUGIN_REGISTRY.md specifies the wiki registry table with all 9 required fields | VERIFIED | File exists; all 9 fields present: name, platform, domain patterns, maintainer, anti-detection difficulty, methods implemented, last-verified, proxy-required, captcha-required; in-repo SPEC vs external-wiki distinction explicit |
| 9 | CONTRIBUTING.md requires difficulty, requires_proxy, requires_captcha for plugin submissions | VERIFIED | `CONTRIBUTING.md` lines 86-99: structured Anti-detection metadata checklist with all 3 attrs |
| 10 | PR template has structured difficulty/requires_proxy/requires_captcha checklist | VERIFIED | `.github/PULL_REQUEST_TEMPLATE.md`: "Plugin Metadata" section lines 53-59; no duplicate Risk Declaration |
| 11 | plugins/PLUGIN_DEV.md ABC contract table lists the 3 new attributes | VERIFIED | `plugins/PLUGIN_DEV.md` lines 59-61: 3 table rows for difficulty, requires_proxy, requires_captcha with types/defaults |
| 12 | GitHub wiki registry table is populated with community plugin data | HUMAN NEEDED | The GitHub wiki is an external surface not in this repository |

**Score:** 8/8 in-repo must-haves verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `core/plugin_base.py` | difficulty/requires_proxy/requires_captcha class attrs + __init_subclass__ validation | VERIFIED | Lines 22-24 (3 attrs), lines 26-36 (__init_subclass__); PLUGIN_API_VERSION stays 2 |
| `tests/test_plugin_base.py` | default, override, invalid-difficulty, existing-plugin-smoke assertions | VERIFIED | 4 tests added: test_defaults, test_override, test_invalid_difficulty_raises, test_existing_plugins_load |
| `core/service.py` | BotService.list_plugins() reading registry._all_plugins | VERIFIED | Lines 76-101: method reads `_all_plugins`, imports PluginRegistry locally (MOD-02), returns 5-key dicts |
| `core/cli/plugins.py` | handle_plugins_list + _format_plugins_table; no core.registry import | VERIFIED | File exists; imports only `json` and `BotService`; no `core.registry` import (MOD-02 satisfied) |
| `core/cli/__init__.py` | plugins nested subparser with list leaf + --json flag | VERIFIED | Lines 119-132: plugins parser, list subparser, --json flag, _require_subcommand for bare plugins |
| `tests/test_cli_plugins.py` | table, --json, no-leaf-exit-2, empty, no-network tests | VERIFIED | 6 tests present (5 original + 1 for WR-02 string-coercion regression) |
| `docs/PLUGIN_REGISTRY.md` | 9-field wiki registry table SPEC + in-repo-vs-wiki note | VERIFIED | All 9 fields present; explicit "This file is the in-repo specification" statement |
| `CONTRIBUTING.md` | difficulty/requires_proxy/requires_captcha checklist items | VERIFIED | Lines 86-99: structured Anti-detection metadata checklist item |
| `.github/PULL_REQUEST_TEMPLATE.md` | structured Plugin Metadata section (no duplicate risk section) | VERIFIED | "Plugin Metadata" section present; no second "Risk Declaration" section |
| `plugins/PLUGIN_DEV.md` | ABC table rows for difficulty, requires_proxy, requires_captcha | VERIFIED | Lines 59-61: 3 rows in ABC Contract table |
| `tests/test_docs.py` | 4 doc-presence tests for REG-01 and REG-04 | VERIFIED | 4 tests: registry 9-fields, contributing attrs, PR template attrs, plugin_dev attrs |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `core/cli/plugins.py` | `BotService.list_plugins` | `svc.list_plugins()` call | WIRED | `handle_plugins_list` calls `rows = svc.list_plugins()` at line 49 |
| `core/service.py` | `registry._all_plugins` | fresh PluginRegistry construction | WIRED | `list_plugins()` constructs `PluginRegistry(self._cfg, plugins_dir)` then iterates `registry._all_plugins` |
| `core/cli/__init__.py` | `handle_plugins_list` | `set_defaults(func=handle_plugins_list)` | WIRED | Line 15 import + line 129 `set_defaults` |
| `.github/PULL_REQUEST_TEMPLATE.md` | `core/plugin_base.py` attrs | checklist names all 3 class attributes | WIRED | PR template "Plugin Metadata" section explicitly names `difficulty`, `requires_proxy`, `requires_captcha` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `core/cli/plugins.py` | `rows` | `svc.list_plugins()` -> `registry._all_plugins` | Yes: PluginRegistry._all_plugins populated eagerly from real plugin files in `plugins/` dir | FLOWING |
| `BotService.list_plugins()` | `registry._all_plugins` | `PluginRegistry.__init__` calls `_discover_plugins(plugins_dir)` | Yes: discovers 7 real plugin files; not static | FLOWING |

### Behavioral Spot-Checks

Step 7b behavioral checks require running the CLI with the actual plugin files loaded. The test suite covers these via mocks. The `test_existing_plugins_load` test in `test_plugin_base.py` does a real discovery against the `plugins/` directory confirming 7 plugins load with valid attrs.

| Behavior | Test | Status |
|----------|------|--------|
| plugins list table output | test_plugins_list_table | PASS (by test suite) |
| plugins list --json output | test_plugins_list_json | PASS (by test suite) |
| bare plugins exits 2 | test_plugins_no_leaf_exits_2 | PASS (by test suite) |
| no network call | test_plugins_list_no_network | PASS (socket patched, exit 0) |
| 7 existing plugins load with valid attrs | test_existing_plugins_load | PASS (asserts >= 7) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| REG-01 | 15-03-PLAN | Wiki registry table spec with 9 required fields | SATISFIED | `docs/PLUGIN_REGISTRY.md` exists with all 9 fields; in-repo SPEC delivered; live wiki is manual/human action |
| REG-02 | 15-01-PLAN | difficulty/requires_proxy/requires_captcha class attrs on ABC | SATISFIED | `core/plugin_base.py` lines 22-36; non-breaking; PLUGIN_API_VERSION=2 |
| REG-03 | 15-02-PLAN | `shoppybot plugins list` with no network call | SATISFIED | Full implementation in `core/cli/plugins.py` + `core/service.py`; 6 tests pass |
| REG-04 | 15-03-PLAN | CONTRIBUTING.md + PR template + PLUGIN_DEV.md updated | SATISFIED | All 3 docs updated with structured attrs; `tests/test_docs.py` locks content |

Note: `REQUIREMENTS.md` shows REG-03 with an unchecked `[ ]` checkbox. This is a documentation tracking discrepancy only — the implementation is fully present and tested. The checkbox was not updated after Plan 02 completed.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | No TBD/FIXME/XXX markers found in any phase-modified file | — | — |

Review warnings WR-01 (dead `sys` import in `core/cli/plugins.py`) and WR-02 (domain_patterns string-coercion) were both fixed in commit `428aaf8`. The test file now has 6 tests (the 6th covers the WR-02 regression path: `test_plugins_list_string_domain_patterns_not_char_split`).

### Human Verification Required

#### 1. GitHub Wiki Registry Page Population

**Test:** Open the ShopPyBot GitHub repository wiki. Create a page named "Plugin Registry". Add a table following the 9-column structure defined in `docs/PLUGIN_REGISTRY.md`. Add at minimum the AmazonPlugin row using the example in that file.

**Expected:** The wiki page exists with all 9 column headers (name, platform, domain patterns, maintainer, anti-detection difficulty, methods implemented, last-verified, proxy-required, captcha-required) and the AmazonPlugin row is correctly populated.

**Why human:** The GitHub wiki is an external surface outside this repository. It cannot be populated, read, or verified via grep, pytest, or any file-system tool. This is the only in-scope deliverable for REG-01 that is explicitly flagged as a manual maintainer action in `docs/PLUGIN_REGISTRY.md` and `15-VALIDATION.md`.

### Gaps Summary

No gaps. All in-repo deliverables for REG-01 through REG-04 are fully implemented, substantive, wired, and test-covered. The single human verification item is the external GitHub wiki population, which is intentionally manual per the phase design (flagged in STATE.md Pitfall 5.1, documented in VALIDATION.md Manual-Only Verifications table, and explicit in docs/PLUGIN_REGISTRY.md).

---

_Verified: 2026-06-09_
_Verifier: Claude (gsd-verifier)_
