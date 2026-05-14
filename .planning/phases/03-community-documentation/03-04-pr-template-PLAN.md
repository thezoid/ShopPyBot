---
phase: 03-community-documentation
plan: 04
type: execute
wave: 0
depends_on: []
files_modified:
  - .github/PULL_REQUEST_TEMPLATE.md
  - tests/test_docs.py
autonomous: true
requirements:
  - DOCS-05
tags:
  - documentation
  - github
  - templates

must_haves:
  truths:
    - ".github/PULL_REQUEST_TEMPLATE.md exists"
    - "PR template includes a Summary section prompting a short why-not-just-what description"
    - "PR template includes a Type-of-change checklist (feat/fix/docs/refactor/test/chore) matching commit conventions"
    - "PR template includes an ABC compliance checklist for plugin PRs: subclasses RetailerPlugin, implements check_availability, implements auto_buy, declares domain_pattern as list[str]"
    - "PR template includes a Naming convention check: filename matches shopbot_plugin_<platform>.py for new plugins"
    - "PR template includes a Test presence checklist: new tests added, full pytest suite passes locally"
    - "PR template includes a Risk documentation checklist for plugins: anti-detection risk declared in docstring; references SECURITY.md per-platform risk register"
    - "PR template includes a Security/Credentials confirmation: no secrets/PII committed"
    - "PR template forward-links CONTRIBUTING.md"
    - "tests/test_docs.py asserts the template exists and contains the required anchors"
  artifacts:
    - path: ".github/PULL_REQUEST_TEMPLATE.md"
      provides: "Pre-filled PR description with checklist enforcing ABC compliance, naming, tests, risk docs, secret hygiene"
      contains: "ABC Compliance"
      min_lines: 30
    - path: "tests/test_docs.py"
      provides: "Substring tests asserting PR template anchors"
  key_links:
    - from: ".github/PULL_REQUEST_TEMPLATE.md"
      to: "CONTRIBUTING.md"
      via: "markdown link in the header"
      pattern: "CONTRIBUTING\\.md"
    - from: ".github/PULL_REQUEST_TEMPLATE.md"
      to: "SECURITY.md"
      via: "markdown link in the risk-documentation section"
      pattern: "SECURITY\\.md"
---

<objective>
Ship .github/PULL_REQUEST_TEMPLATE.md covering DOCS-05: ABC compliance, naming convention, test presence, risk documentation, secret hygiene.

Purpose: After this plan, opening a PR pre-fills a checklist that maintainers (and the contributor) can walk through to confirm the PR is mergeable, with no source-code spelunking required.

Output: One Markdown file under .github/ and a small extension to tests/test_docs.py.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/REQUIREMENTS.md
@.planning/ROADMAP.md
@tests/test_docs.py
</context>

<interfaces>
PULL_REQUEST_TEMPLATE.md required structure (Markdown only, no YAML frontmatter on this file):

```markdown
# Pull Request

Thanks for contributing. Please read [CONTRIBUTING.md](../CONTRIBUTING.md) before
opening the PR if you have not already.

## Summary
Brief description of the change. Explain why, not just what.

Closes #<issue-number> (if applicable).

## Type of change
- [ ] feat (new feature)
- [ ] fix (bug fix)
- [ ] docs (documentation only)
- [ ] refactor (no functional change)
- [ ] test (test additions or fixes)
- [ ] chore (build, CI, tooling)

## For plugin contributions

### ABC Compliance
- [ ] Plugin subclasses `RetailerPlugin` from `plugin_base`
- [ ] Implements `check_availability(self, url) -> bool`
- [ ] Implements `auto_buy(self, url, config) -> bool`
- [ ] Declares `domain_pattern: list[str]` (a list literal, not a single string)
- [ ] One plugin class per file

### Naming convention
- [ ] Filename matches `plugins/shopbot_plugin_<platform>.py`
- [ ] Class name follows `<Platform>Plugin` convention

### Tests
- [ ] New tests added in `tests/test_plugins_<platform>.py`
- [ ] Tests mock `build_driver`; no real Chrome is launched
- [ ] `pytest` runs clean locally

### Risk documentation
- [ ] Anti-detection risk declared in the plugin module docstring
- [ ] Updated per-platform risk row in [SECURITY.md](../SECURITY.md) if adding a new platform

## Security and credentials
- [ ] No credentials, API keys, CVVs, or PII included in this PR
- [ ] No `config.yml` with real values committed
- [ ] If this PR fixes a security issue, the disclosure flow in [SECURITY.md](../SECURITY.md) was followed first

## Manual test plan
List the exact commands or clicks a reviewer can run to validate the change.
```

Style rules:
- No emojis
- No em dashes
- No horizontal-rule lines
- Length target: 40-100 lines
- Relative paths (../CONTRIBUTING.md, ../SECURITY.md) because the file lives at .github/
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: RED tests for PR template</name>
  <files>tests/test_docs.py</files>
  <read_first>
    - tests/test_docs.py
    - .planning/REQUIREMENTS.md (DOCS-05 wording)
  </read_first>
  <behavior>
    Append to tests/test_docs.py under `# DOCS-05 (Plan 03-04): PR template`:

      - test_pr_template_exists: .github/PULL_REQUEST_TEMPLATE.md exists
      - test_pr_template_has_summary_section: lowercase source contains "## summary"
      - test_pr_template_has_type_of_change: source contains all of "feat", "fix", "docs", "refactor", "test", "chore"
      - test_pr_template_has_abc_compliance: lowercase source contains "abc compliance" AND all of: "RetailerPlugin", "check_availability", "auto_buy", "domain_pattern", "list[str]"
      - test_pr_template_has_naming_section: source contains "shopbot_plugin_"
      - test_pr_template_has_tests_section: lowercase source contains "pytest" AND "build_driver"
      - test_pr_template_has_risk_section: source contains "anti-detection" AND "SECURITY.md"
      - test_pr_template_has_secret_hygiene: lowercase source contains "credentials" AND ("pii" OR "personal")
      - test_pr_template_links_contributing: source contains "CONTRIBUTING.md"
      - test_pr_template_no_em_dashes: em dash `—` does NOT appear
      - test_pr_template_no_horizontal_rule: no line stripped equals "---", "***", "___"
  </behavior>
  <action>
    1. Open `tests/test_docs.py`. Append section header `# DOCS-05 (Plan 03-04): PR template`.
    2. Add `PR_TEMPLATE_FILE = pathlib.Path(".github/PULL_REQUEST_TEMPLATE.md")` and helper `_pr_text()`.
    3. Add the 11 tests listed under `<behavior>`.
    4. Run `rtk pytest tests/test_docs.py -q`. New tests fail -- RED state.
  </action>
  <verify>
    <automated>rtk pytest tests/test_docs.py -q</automated>
  </verify>
  <done>RED tests for PR template committed</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Ship PR template (GREEN)</name>
  <files>.github/PULL_REQUEST_TEMPLATE.md</files>
  <read_first>
    - tests/test_docs.py (RED tests)
    - .planning/REQUIREMENTS.md (DOCS-05 wording)
  </read_first>
  <behavior>
    - All 11 new tests pass
    - Full pytest suite stays green
    - Zero em dashes; zero horizontal-rule lines
  </behavior>
  <action>
    1. Create `.github/PULL_REQUEST_TEMPLATE.md` using the body in `<interfaces>` verbatim.
       Required literal substrings:
         - "## Summary"
         - "feat", "fix", "docs", "refactor", "test", "chore"
         - "ABC Compliance"
         - "RetailerPlugin", "check_availability", "auto_buy", "domain_pattern", "list[str]"
         - "shopbot_plugin_"
         - "pytest", "build_driver"
         - "anti-detection"
         - "SECURITY.md"
         - "credentials", "PII"
         - "CONTRIBUTING.md"
       Style:
         - No em dashes
         - No horizontal-rule lines
         - No emojis
    2. Run `rtk pytest tests/test_docs.py -q`. All DOCS-05 tests pass.
    3. Run `rtk pytest -q`. No regressions.
  </action>
  <verify>
    <automated>rtk pytest tests/test_docs.py -q</automated>
    <automated>rtk pytest -q</automated>
    <automated>rtk grep -c "ABC Compliance" .github/PULL_REQUEST_TEMPLATE.md</automated>
  </verify>
  <done>PR template shipped; DOCS-05 satisfied; tests green</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| contributor opens a PR | Without a checklist, plugin PRs may land with missing tests, wrong filename, undeclared risk, or committed secrets |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-3-DOCS-05-CONTRACT | Tampering | Plugin merged without ABC compliance | mitigate | ABC Compliance checklist enforces explicit confirmation of RetailerPlugin subclass, both abstract methods, and `list[str]` domain_pattern. Tests assert the substrings are present in the template |
| T-3-DOCS-05-CRED | Information Disclosure | PR includes credentials/PII | mitigate | Secret hygiene checkbox requires explicit confirmation; tests assert anchor present |
| T-3-DOCS-05-RISK | Repudiation | New plugin lacks anti-detection risk disclosure | mitigate | Risk documentation section requires the contributor to update SECURITY.md per-platform table; tests assert SECURITY.md reference present |
</threat_model>

<verification>
- `rtk pytest -q tests/test_docs.py` passes including new DOCS-05 tests
- `rtk pytest -q` full suite passes
- `rtk find .github/PULL_REQUEST_TEMPLATE.md` resolves
- `rtk grep -n "—" .github/PULL_REQUEST_TEMPLATE.md` returns no matches
</verification>

<success_criteria>
- DOCS-05 satisfied: PR template enforces ABC compliance, naming, tests, risk, secret hygiene
- Template forward-links CONTRIBUTING.md and SECURITY.md
- Substring tests lock the anchors so future drift is caught
</success_criteria>

<output>
After completion, create `.planning/phases/03-community-documentation/03-04-SUMMARY.md`
</output>
