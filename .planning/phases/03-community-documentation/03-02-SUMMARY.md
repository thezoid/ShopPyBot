---
phase: 03-community-documentation
plan: "02"
subsystem: github-templates
tags: [docs, github, issue-templates, pr-template, community]
dependency_graph:
  requires: [03-01]
  provides: [DOCS-04, DOCS-05]
  affects: []
tech_stack:
  added: []
  patterns: [github-issue-forms-yaml, github-pr-template-markdown]
key_files:
  created:
    - .github/ISSUE_TEMPLATE/bug_report.yml
    - .github/ISSUE_TEMPLATE/plugin_request.yml
    - .github/ISSUE_TEMPLATE/config.yml
    - .github/PULL_REQUEST_TEMPLATE.md
  modified:
    - .gitignore
decisions:
  - "config.yml contact_links url points to SECURITY.md blob on master (satisfies plan requirement that url contains SECURITY.md)"
  - "Anchored /config.yml in .gitignore to prevent ISSUE_TEMPLATE/config.yml from being ignored"
metrics:
  duration: "~5 minutes"
  completed: "2026-06-03"
  tasks_completed: 2
  files_created: 4
  files_modified: 1
---

# Phase 3 Plan 02: GitHub Contribution Templates Summary

GitHub issue forms (bug report, plugin request) and a PR checklist template
created; blank issues disabled with a security contact link routing reporters
to SECURITY.md.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Issue forms and ISSUE_TEMPLATE config | 5cb3e6a | bug_report.yml, plugin_request.yml, config.yml, .gitignore |
| 2 | PR template | b11df2c | PULL_REQUEST_TEMPLATE.md |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Anchored /config.yml in .gitignore**

- Found during: Task 1 staging
- Issue: .gitignore line 7 had a bare `config.yml` pattern matching all paths; this excluded `.github/ISSUE_TEMPLATE/config.yml` from git tracking.
- Fix: Changed `config.yml` to `/config.yml` to anchor the rule to the repo root, leaving only the user configuration file at `./config.yml` ignored.
- Files modified: .gitignore
- Commit: 5cb3e6a

## Verification Results

All automated checks passed:

- bug_report.yml parses as valid YAML with required fields and a security-routing note
- plugin_request.yml parses as valid YAML with required fields and a risk-level dropdown (low/medium/high)
- config.yml: blank_issues_enabled=false; contact_links url contains SECURITY.md
- PULL_REQUEST_TEMPLATE.md: contains ABC, shopbot_plugin_, pytest, risk, credentials/secrets checklist items; no em dashes; no horizontal-rule lines

## Known Stubs

None. All template content is complete and wired.

## Threat Flags

None. No new network endpoints, auth paths, or schema changes introduced.

## Self-Check: PASSED

Files confirmed present:
- .github/ISSUE_TEMPLATE/bug_report.yml: FOUND
- .github/ISSUE_TEMPLATE/plugin_request.yml: FOUND
- .github/ISSUE_TEMPLATE/config.yml: FOUND
- .github/PULL_REQUEST_TEMPLATE.md: FOUND

Commits confirmed:
- 5cb3e6a: FOUND
- b11df2c: FOUND
