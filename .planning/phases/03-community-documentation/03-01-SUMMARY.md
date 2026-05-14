---
phase: 03-community-documentation
plan: 01
subsystem: documentation
tags:
  - documentation
  - contributor
  - community
requires: []
provides:
  - "External contributor onboarding doc (CONTRIBUTING.md)"
  - "Plugin submission checklist for PR reviewers"
affects:
  - tests/test_docs.py
tech-stack:
  added: []
  patterns:
    - "Markdown-only doc; substring-tested anchors"
key-files:
  created:
    - CONTRIBUTING.md
  modified:
    - tests/test_docs.py
decisions:
  - "Omit the License section from CONTRIBUTING.md; no LICENSE file exists at repo root yet."
  - "Forward-link plugins/PLUGIN_DEV.md instead of duplicating the technical contract; CONTRIBUTING.md is process-only."
metrics:
  duration: "single session"
  completed: 2026-05-14
  tasks: 2
  files_touched: 2
---

# Phase 3 Plan 01: CONTRIBUTING.md Summary

One-liner: External contributor onboarding doc (workflow, commit convention, test rules, plugin submission checklist) covering DOCS-01 and DOCS-02, with substring tests locking the anchors.

## What shipped

- `CONTRIBUTING.md` at repo root (~140 lines). Sections: Before you start,
  Development workflow, Commit message convention, Tests, Contributing a
  plugin (links to `plugins/PLUGIN_DEV.md`), Plugin Submission Checklist,
  Reporting bugs and requesting features, Code style.
- `tests/test_docs.py` extended with 11 new tests asserting CONTRIBUTING.md
  exists, contains the required anchors (workflow keywords, commit
  convention literal, pytest mention, forward-links to PLUGIN_DEV.md /
  SECURITY.md / README.md, checklist substrings), and enforces style rules
  (no em dashes, no horizontal-rule lines).

## Requirements satisfied

- DOCS-01: fork/branch/PR workflow, commit conventions (type(scope):
  description, types feat/fix/docs/style/refactor/test/chore, 72-char
  subject), test requirements (pytest, RED-before-GREEN, mock build_driver),
  link to plugins/PLUGIN_DEV.md.
- DOCS-02: Plugin Submission Checklist enumerates filename convention
  (`shopbot_plugin_<platform>.py`), required ABC methods
  (`check_availability`, `auto_buy`), `domain_pattern: list[str]` attribute,
  test coverage requirement (import + ABC compliance + mocked routing), and
  anti-detection risk declaration in the class docstring.

## Commits

| Hash    | Message                                                    |
| ------- | ---------------------------------------------------------- |
| 2fa44ce | test(03-01): RED tests for CONTRIBUTING.md (DOCS-01/02)    |
| 89e117a | docs(03-01): add CONTRIBUTING.md (DOCS-01, DOCS-02)        |

## Verification results

- `pytest tests/test_docs.py -q` : 36 passed (all 11 new tests pass; existing
  Phase 1/2 docs tests still green).
- `grep -c "Plugin Submission Checklist" CONTRIBUTING.md` : 1.
- `grep -c "plugins/PLUGIN_DEV.md" CONTRIBUTING.md` : 1.
- `grep -n "—" CONTRIBUTING.md` : no matches (no em dashes).

## Deviations from Plan

None of substance. The plan's `<interfaces>` outline included a "License"
section gated on `LICENSE` existing at repo root. No `LICENSE*` file exists,
so per the plan's own instruction (`If absent, omit this section entirely`)
the section was omitted. This is a planned conditional, not a deviation.

## Deferred Issues (out of scope)

The full `pytest -q` run surfaces pre-existing failures unrelated to this
plan:

- `tests/test_utils.py` fails to collect: `pygame` not installed in the
  current venv. Pre-existing.
- `tests/test_driver_setup.py` (3 failures): selenium not importable in the
  current venv. Pre-existing.
- `tests/test_models.py` (2 errors): SQLite path resolution at test setup.
  Pre-existing.

Per Rule 4 (out-of-scope), none of these were touched. They predate Phase 3
and belong to Phase 1 / 4 environment hardening. Filed mentally for the
phase-level deferred-items log.

## Self-Check: PASSED

- FOUND: CONTRIBUTING.md (E:\repos\ShopPyBot\.claude\worktrees\gallant-ritchie-fa629c\CONTRIBUTING.md)
- FOUND: tests/test_docs.py extension (+95 lines, 11 new tests)
- FOUND commit: 2fa44ce
- FOUND commit: 89e117a
