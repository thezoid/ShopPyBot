---
phase: 15-plugin-ecosystem-registry
reviewed: 2026-06-09T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - core/plugin_base.py
  - core/service.py
  - core/cli/plugins.py
  - core/cli/__init__.py
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: resolved
---

# Phase 15: Code Review Report

**Reviewed:** 2026-06-09
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Four files reviewed covering the plugin metadata attributes (plugin_base.py), service accessor
(service.py), CLI handler (cli/plugins.py), and parser wiring (cli/__init__.py). The phase is
additive and structurally sound: no PLUGIN_API_VERSION bump, no abstractmethod added, no
network/browser call in `list_plugins()`, MOD-02 constraint respected, bare `plugins` exits 2.

Two warnings and one info item found.

## Warnings

### WR-01: Unused `sys` import in cli/plugins.py

**File:** `core/cli/plugins.py:7`
**Issue:** `import sys` is present at the top of the file but `sys` is never referenced
anywhere in the module. The module docstring even calls out the exact imports the file uses
(`json`, `sys`, `BotService`) -- the docstring claim for `sys` is itself the only trace of
intent, and nothing in the file ever calls `sys.exit`, `sys.stderr`, or any `sys.*` attribute.
Dead import; violates the project "unused imports" quality bar and will trigger linters.
**Fix:** Remove line 7 (`import sys`). If a future caller needs `sys.exit` for error paths,
add it at that time.

### WR-02: `_format_plugins_table` crashes with `ValueError` when any plugin has an empty `domain_patterns` list

**File:** `core/cli/plugins.py:33-36`
**Issue:** The inner `max(len(row[i]) for row in data)` expression is called unconditionally.
When a plugin has `domain_patterns = []`, the `", ".join([])` produces an empty string and
`len("")` is 0, which is fine for that row. The outer `max(len(h), ...)` receives a valid
sequence in that case.

However, the *real* crash path is one level up: if every plugin in the set happens to produce
an empty domain-patterns cell AND the header is the widest value, the `max(...)` over
`data` still works (returns 0). There is no crash there.

The actual crash path: if `data` is populated (rows is non-empty, the guard on line 19
already handles the fully-empty case) but all plugins have `domain_patterns = []`, then
`max(len(row[i]) for row in data)` is `max(0, 0, ...)` which is valid. This is safe.

**Revised finding -- actual crash:** `max(len(row[i]) for row in data)` is called with `data`
guaranteed non-empty (rows guard on line 19), but if a plugin exposes `domain_patterns` that
is not a list (e.g., a 3rd-party plugin that stores it as a tuple or a string), the
`", ".join(r["domain_patterns"])` on line 26 will crash for non-iterable types, or produce
character-separated output for a bare string (e.g., `domain_patterns = "amazon.com"` yields
`"a, m, a, z, o, n, ., c, o, m"`).

The `list_plugins()` method in service.py returns `plugin.domain_patterns` verbatim (line 91
of service.py) without coercing to list. All current first-party plugins use list literals, so
no crash today. But 3rd-party or malformed plugins passed from `_all_plugins` could produce
confusing output or a `TypeError` from `", ".join()` if `domain_patterns` is not an iterable
of strings.

**Fix:** Coerce in `list_plugins()` or in `_format_plugins_table`. Either:

In `service.py` list_plugins, change:
```python
"domain_patterns": plugin.domain_patterns,
```
to:
```python
"domain_patterns": list(getattr(plugin, "domain_patterns", [])),
```

Or defensively in `_format_plugins_table`:
```python
", ".join(str(p) for p in r["domain_patterns"]),
```

## Info

### IN-01: `__init_subclass__` fires for intermediate abstract subclasses that inherit `difficulty = "medium"`

**File:** `core/plugin_base.py:26-36`
**Issue:** `__init_subclass__` is called for every class that subclasses `RetailerPlugin`,
including intermediate abstract classes (e.g., a `class BaseAmazonPlugin(RetailerPlugin):`
that is still abstract). Because the default `difficulty = "medium"` is always in `_VALID_DIFFICULTY`,
these fire-and-pass calls are harmless. This is not a bug -- just worth noting that any
abstract intermediate class that sets an invalid `difficulty` will raise at import time, which
is the stated intent. Behaviour is correct.

No code change needed; informational only.

---

_Reviewed: 2026-06-09_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
