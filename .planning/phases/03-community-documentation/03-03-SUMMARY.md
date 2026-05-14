---
phase: 03-community-documentation
plan: 03
subsystem: documentation
tags: [documentation, github, templates]
requires: [SECURITY.md, CONTRIBUTING.md]
provides:
  - .github/ISSUE_TEMPLATE/bug_report.yml
  - .github/ISSUE_TEMPLATE/plugin_request.yml
  - .github/ISSUE_TEMPLATE/platform_issue.yml
  - .github/ISSUE_TEMPLATE/config.yml
affects: [.gitignore]
tech-stack:
  added: []
  patterns: [github-issue-forms-yaml]
key-files:
  created:
    - .github/ISSUE_TEMPLATE/bug_report.yml
    - .github/ISSUE_TEMPLATE/plugin_request.yml
    - .github/ISSUE_TEMPLATE/platform_issue.yml
    - .github/ISSUE_TEMPLATE/config.yml
  modified:
    - tests/test_docs.py
    - .gitignore
decisions:
  - Used modern YAML issue forms (not legacy markdown templates) for structured input
  - Added gitignore negation for .github/ISSUE_TEMPLATE/config.yml so chooser config tracks despite root-level config.yml exclusion
metrics:
  duration: ~5min
  completed: 2026-05-14
requirements: [DOCS-04]
---

# Phase 03 Plan 03: GitHub Issue Templates Summary

Ships four YAML issue-form files under `.github/ISSUE_TEMPLATE/` (bug report, plugin request, plugin issue, chooser config) satisfying DOCS-04; structured intake routes security disclosures off the public issue tracker and disables blank issues.

## What Shipped

- `bug_report.yml`: version/OS/Python/repro/expected/actual textarea fields, log render as `shell`, required confirmation checkboxes for credential hygiene and security-routing
- `plugin_request.yml`: platform name, store URL, anti-detection difficulty dropdown, contributor-intent checkboxes, required TOS/account-risk acknowledgement
- `platform_issue.yml`: dropdown over current plugins (amazon, bestbuy, walmart, target, gamestop, squareenix, newegg, other), product URL, log snippet, last-working version, credential-redaction confirmation
- `config.yml`: `blank_issues_enabled: false` plus two `contact_links` routing to GitHub Security Advisories and SECURITY.md
- `tests/test_docs.py` extended with 17 DOCS-04 tests (existence, YAML parsing, required top-level keys, required-field validation, blank-issues disabled, security-link present)

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | RED tests for issue templates | 2ba8005 | tests/test_docs.py |
| 2 | Ship four issue template YAMLs (GREEN) | ebc4f66 | .github/ISSUE_TEMPLATE/*.yml, .gitignore |

## Verification

- `python -m pytest tests/test_docs.py -q`: 63 passed (46 prior + 17 new)
- Full suite (excluding pre-existing test_utils.py import error unrelated to this plan): 154 passed
- All four YAMLs parsed via `yaml.safe_load` successfully

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] .gitignore blocked `.github/ISSUE_TEMPLATE/config.yml`**
- **Found during:** Task 2 commit
- **Issue:** Root `.gitignore` line 7 (`config.yml`) excludes the runtime config but also matched the new issue-chooser config file, preventing `git add`
- **Fix:** Added negation `!.github/ISSUE_TEMPLATE/config.yml` immediately after the existing `config.yml` rule. Scope-minimal: does not change behavior for the root-level runtime config
- **Files modified:** .gitignore
- **Commit:** ebc4f66

## Threat Model Coverage

All three STRIDE entries from the plan's threat model are mitigated:

- `T-3-DOCS-04-PUBLIC-SEC`: `config.yml` contact_links route to `security/advisories` and SECURITY.md; blank issues disabled. Test `test_chooser_disables_blank_issues` + `test_chooser_links_security` lock both anchors.
- `T-3-DOCS-04-CRED-LEAK`: bug_report.yml + platform_issue.yml both contain `required: true` checkboxes confirming no credentials/PII in submission, with markdown headers repeating the warning.
- `T-3-DOCS-04-MALFORMED`: `test_form_yml_files_parse` asserts each YAML parses with `yaml.safe_load`.

## Known Stubs

None.

## Self-Check: PASSED

- FOUND: .github/ISSUE_TEMPLATE/bug_report.yml
- FOUND: .github/ISSUE_TEMPLATE/plugin_request.yml
- FOUND: .github/ISSUE_TEMPLATE/platform_issue.yml
- FOUND: .github/ISSUE_TEMPLATE/config.yml
- FOUND commit: 2ba8005
- FOUND commit: ebc4f66
