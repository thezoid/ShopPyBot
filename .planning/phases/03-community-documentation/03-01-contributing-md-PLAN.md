---
phase: 03-community-documentation
plan: 01
type: execute
wave: 0
depends_on: []
files_modified:
  - CONTRIBUTING.md
  - tests/test_docs.py
autonomous: true
requirements:
  - DOCS-01
  - DOCS-02
tags:
  - documentation
  - contributor
  - community

must_haves:
  truths:
    - "CONTRIBUTING.md exists at the repo root"
    - "CONTRIBUTING.md documents fork/branch/PR workflow so a contributor can submit a change without reading source code"
    - "CONTRIBUTING.md documents commit message conventions matching project history (type(scope): description, types: feat|fix|docs|style|refactor|test|chore, subject under 72 chars)"
    - "CONTRIBUTING.md documents test requirements (pytest, test colocation in tests/, RED-before-GREEN expectation)"
    - "CONTRIBUTING.md links to plugins/PLUGIN_DEV.md for plugin technical contract (does not duplicate it)"
    - "CONTRIBUTING.md includes a plugin submission checklist enumerating: filename convention (shopbot_plugin_*.py), required ABC methods (check_availability, auto_buy), domain_pattern attribute (list[str]), test coverage requirement, anti-detection risk declaration"
    - "CONTRIBUTING.md links to SECURITY.md for the responsible disclosure path"
    - "CONTRIBUTING.md links to README.md TOS/account-risk disclaimer for legal context"
    - "CONTRIBUTING.md links to LICENSE if a LICENSE file exists at repo root; otherwise the link section is omitted (executor verifies at write time)"
    - "tests/test_docs.py asserts CONTRIBUTING.md exists and contains the required anchors"
  artifacts:
    - path: "CONTRIBUTING.md"
      provides: "External contributor onboarding: workflow, conventions, plugin checklist"
      contains: "Plugin Submission Checklist"
      min_lines: 80
    - path: "tests/test_docs.py"
      provides: "Substring/existence tests asserting CONTRIBUTING.md content anchors are present"
  key_links:
    - from: "CONTRIBUTING.md"
      to: "plugins/PLUGIN_DEV.md"
      via: "markdown link in the plugin contributions section"
      pattern: "plugins/PLUGIN_DEV\\.md"
    - from: "CONTRIBUTING.md"
      to: "SECURITY.md"
      via: "markdown link in the responsible disclosure section"
      pattern: "SECURITY\\.md"
    - from: "CONTRIBUTING.md"
      to: "README.md"
      via: "markdown link in the legal/TOS context section"
      pattern: "README\\.md"
---

<objective>
Ship CONTRIBUTING.md covering DOCS-01 (fork/branch/PR workflow, commit conventions, test requirements, plugin doc link) and DOCS-02 (plugin submission checklist). Single file, single plan.

Purpose: After this plan, an external contributor can clone the repo, open CONTRIBUTING.md, and submit a plugin PR that matches project conventions without reading source code.

Output: CONTRIBUTING.md at repo root and a small extension to tests/test_docs.py asserting required anchors.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/REQUIREMENTS.md
@.planning/ROADMAP.md
@README.md
@plugins/PLUGIN_DEV.md
@tests/test_docs.py
</context>

<interfaces>
CONTRIBUTING.md required structure (each heading is a Markdown `##`, doc title `#`):

```markdown
# Contributing to ShopPyBot

## Before you start
Brief intro. Link to README.md Disclaimer for personal-use/TOS/account-risk context.
Link to SECURITY.md for security issues (do not file as a public issue).

## Development workflow
1. Fork the repository on GitHub
2. Create a topic branch from master: `git checkout -b feat/my-change`
3. Run setup (python -m venv .venv; activate; pip install -r requirements.txt)
4. Make changes; add/extend tests in tests/
5. Run `pytest` locally; all tests must pass
6. Commit with the convention below
7. Push your fork and open a PR against master

## Commit message convention
Format: `type(scope): description`
Types: feat, fix, docs, style, refactor, test, chore
Subject under 72 chars. Describe why, not just what.
Examples (code block).

## Tests
- pytest is the test runner; tests live in tests/
- New code requires tests; bug fixes require a regression test
- Prefer RED-before-GREEN: write the failing test first, then the implementation
- No test should spawn a real Chrome browser; mock build_driver

## Contributing a plugin
Link to plugins/PLUGIN_DEV.md for the technical contract reference.
This section is workflow only; do not duplicate PLUGIN_DEV.md content.

### Plugin Submission Checklist
- [ ] Filename matches `plugins/shopbot_plugin_<platform>.py`
- [ ] One plugin class per file
- [ ] Subclasses `RetailerPlugin` from `plugin_base`
- [ ] Implements `check_availability(self, url) -> bool`
- [ ] Implements `auto_buy(self, url, config) -> bool`
- [ ] Declares `domain_pattern: list[str]` (not a single string)
- [ ] Tests added in `tests/test_plugins_<platform>.py` (import test, ABC compliance test, mocked routing test)
- [ ] Anti-detection risk declared in the plugin docstring (e.g., "PerimeterX/HUMAN Security risk", "Akamai blocks headless")
- [ ] No credentials, secrets, or PII in any commit

## Reporting bugs and requesting features
GitHub Issues. Templates pre-fill the required fields.
Security issues: do not file publicly; see SECURITY.md.

## License
[Only include this section if a LICENSE file exists at repo root.
Executor: run `ls LICENSE LICENSE.md LICENSE.txt 2>/dev/null` before writing.
If found, add: "This project is licensed under the terms of the LICENSE file at the repo root."
If absent, omit this section entirely.]
```

Style rules (CLAUDE.md global):
- No emojis
- No em dashes (use colons or restructure)
- No horizontal-rule lines (`---`, `***`, `___`) anywhere in body
- Markdown link form: `[text](path)` using relative paths for repo-internal links
- Length target: 80-200 lines
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: RED tests for CONTRIBUTING.md</name>
  <files>tests/test_docs.py</files>
  <read_first>
    - tests/test_docs.py (existing; will append)
    - README.md (for the disclaimer-link anchor)
    - plugins/PLUGIN_DEV.md (for the forward-link target)
  </read_first>
  <behavior>
    Append to `tests/test_docs.py` under a new section header comment for DOCS-01/02:

      - test_contributing_md_exists: CONTRIBUTING.md exists at repo root
      - test_contributing_md_documents_workflow: lowercase source contains all of "fork", "branch", "pull request" (or "pr")
      - test_contributing_md_documents_commit_convention: source contains the literal "type(scope): description" AND at least three of the type names from {feat, fix, docs, style, refactor, test, chore}
      - test_contributing_md_documents_pytest: lowercase source contains "pytest"
      - test_contributing_md_links_plugin_dev: source contains the substring "plugins/PLUGIN_DEV.md"
      - test_contributing_md_links_security: source contains the substring "SECURITY.md"
      - test_contributing_md_links_readme: source contains the substring "README.md"
      - test_contributing_md_has_plugin_checklist: lowercase source contains "plugin submission checklist"
      - test_contributing_md_checklist_items: source contains all of these substrings: "shopbot_plugin_", "check_availability", "auto_buy", "domain_pattern", "list[str]", "anti-detection"
      - test_contributing_md_no_em_dashes: em dash `—` does NOT appear
      - test_contributing_md_no_horizontal_rule: no line stripped equals "---", "***", or "___"
  </behavior>
  <action>
    1. Open `tests/test_docs.py`. Append a new section (with a comment header `# DOCS-01/02 (Plan 03-01): CONTRIBUTING.md`).
    2. Add a module-level constant: `CONTRIBUTING_FILE = pathlib.Path("CONTRIBUTING.md")` and helper `_contributing_text()`.
    3. Add the 11 tests listed under `<behavior>`.
    4. Run `rtk pytest tests/test_docs.py`. The new tests fail (CONTRIBUTING.md does not exist yet) -- RED state.
  </action>
  <verify>
    <automated>rtk pytest tests/test_docs.py -q</automated>
  </verify>
  <done>RED tests for CONTRIBUTING.md committed; existing Phase 1/2 tests still pass</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Ship CONTRIBUTING.md (GREEN)</name>
  <files>CONTRIBUTING.md</files>
  <read_first>
    - tests/test_docs.py (RED tests from Task 1)
    - README.md
    - plugins/PLUGIN_DEV.md
    - .planning/REQUIREMENTS.md (DOCS-01, DOCS-02 wording is authoritative for must_haves)
  </read_first>
  <behavior>
    - All 11 new tests pass
    - Full pytest suite stays green
    - Contains zero em dashes and zero horizontal-rule lines
  </behavior>
  <action>
    1. Before writing, check for a LICENSE file at the repo root:
       `rtk find . -maxdepth 1 -iname "LICENSE*"`
       If any file is found, include a `## License` section linking to it; otherwise omit that section.
    2. Create `CONTRIBUTING.md` at the repo root following the outline in `<interfaces>`.
       Required literal substrings (case-sensitive unless noted):
         - "type(scope): description"
         - "feat", "fix", "docs", "refactor", "test", "chore" (at least 3 of these)
         - "pytest"
         - "plugins/PLUGIN_DEV.md"
         - "SECURITY.md"
         - "README.md"
         - "Plugin Submission Checklist" (case-insensitive substring match in test)
         - "shopbot_plugin_"
         - "check_availability"
         - "auto_buy"
         - "domain_pattern"
         - "list[str]"
         - "anti-detection"
       Style:
         - No em dashes anywhere (use colons or restructure)
         - No `---`, `***`, or `___` horizontal-rule lines
         - No emojis
         - Use Markdown `##` for major sections; `###` for subsections (the checklist)
       Length target: 80-200 lines.
    3. Run `rtk pytest tests/test_docs.py -q`. All Phase 3 Plan 01 tests pass.
    4. Run `rtk pytest -q` full suite. No regressions.
  </action>
  <verify>
    <automated>rtk pytest tests/test_docs.py -q</automated>
    <automated>rtk pytest -q</automated>
    <automated>rtk grep -c "Plugin Submission Checklist" CONTRIBUTING.md</automated>
    <automated>rtk grep -c "plugins/PLUGIN_DEV.md" CONTRIBUTING.md</automated>
  </verify>
  <done>CONTRIBUTING.md shipped; DOCS-01 and DOCS-02 satisfied; tests green</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| public contributor reads CONTRIBUTING.md and submits PR | A misleading checklist could let a non-compliant plugin merge (e.g., string domain_pattern, missing tests). The checklist is a soft security control: it codifies the gating criteria for plugin PRs |
| public contributor needs to disclose a security bug | If CONTRIBUTING.md does not forward-link SECURITY.md, contributors may file security issues publicly. The link is a process control that routes them to the private channel |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-3-DOCS-01-DRIFT | Tampering | CONTRIBUTING.md vs. plugin_base.py contract | mitigate | Tests assert literal substrings (`check_availability`, `auto_buy`, `domain_pattern`, `list[str]`) so an ABC change forces a docs update |
| T-3-DOCS-02-DISCLOSURE | Information Disclosure | Security bugs reported publicly | mitigate | CONTRIBUTING.md links to SECURITY.md in the bug-reporting section; tests assert the link substring exists |
| T-3-DOCS-01-TOS | Repudiation | Contributor unaware of TOS/account risk before submitting auto-buy code | mitigate | CONTRIBUTING.md links to README.md disclaimer in the "Before you start" section |
</threat_model>

<verification>
- `rtk pytest -q tests/test_docs.py` passes including the 11 new tests
- `rtk pytest -q` full suite passes
- `rtk find CONTRIBUTING.md` resolves
- `rtk grep -n "—" CONTRIBUTING.md` returns no matches
</verification>

<success_criteria>
- DOCS-01 satisfied: workflow + conventions + tests + PLUGIN_DEV.md link present
- DOCS-02 satisfied: plugin submission checklist present with all required items
- Substring tests in `tests/test_docs.py` lock the anchors so future drift is caught
</success_criteria>

<output>
After completion, create `.planning/phases/03-community-documentation/03-01-SUMMARY.md`
</output>
