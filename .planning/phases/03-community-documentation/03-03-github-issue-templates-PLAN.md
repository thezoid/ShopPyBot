---
phase: 03-community-documentation
plan: 03
type: execute
wave: 0
depends_on: []
files_modified:
  - .github/ISSUE_TEMPLATE/bug_report.yml
  - .github/ISSUE_TEMPLATE/plugin_request.yml
  - .github/ISSUE_TEMPLATE/platform_issue.yml
  - .github/ISSUE_TEMPLATE/config.yml
  - tests/test_docs.py
autonomous: true
requirements:
  - DOCS-04
tags:
  - documentation
  - github
  - templates

must_haves:
  truths:
    - ".github/ISSUE_TEMPLATE/ directory exists"
    - "bug_report.yml exists as a GitHub YAML issue form (not legacy markdown) with name, description, body, and required fields"
    - "plugin_request.yml exists as a YAML form with fields for platform name, store URL, anti-detection risk assessment, and contributor willingness"
    - "platform_issue.yml exists as a YAML form covering plugin-specific issues: which plugin, store URL, error/log snippet, last-working version"
    - "config.yml (.github/ISSUE_TEMPLATE/config.yml) disables blank issues and adds a link routing security issues to SECURITY.md"
    - "All four YAML files parse as valid YAML"
    - "tests/test_docs.py asserts each template file exists and parses, and that each form-style template has the required top-level keys (name, description, body) plus a required `labels` field"
  artifacts:
    - path: ".github/ISSUE_TEMPLATE/bug_report.yml"
      provides: "Pre-filled bug report form: repro steps, expected vs actual, environment, logs"
      contains: "name:"
      min_lines: 30
    - path: ".github/ISSUE_TEMPLATE/plugin_request.yml"
      provides: "Pre-filled new-platform-plugin request form"
      contains: "name:"
      min_lines: 25
    - path: ".github/ISSUE_TEMPLATE/platform_issue.yml"
      provides: "Pre-filled report for issues with an existing plugin"
      contains: "name:"
      min_lines: 25
    - path: ".github/ISSUE_TEMPLATE/config.yml"
      provides: "Issue template chooser config: disables blank issues, routes security issues to SECURITY.md"
      contains: "blank_issues_enabled"
  key_links:
    - from: ".github/ISSUE_TEMPLATE/config.yml"
      to: "SECURITY.md"
      via: "contact_links entry directing security disclosures to SECURITY.md"
      pattern: "SECURITY\\.md|security/advisories"
---

<objective>
Ship .github/ISSUE_TEMPLATE/ with three YAML form templates (bug, plugin request, platform issue) plus the chooser config to disable blank issues and route security to SECURITY.md. Satisfies DOCS-04.

Purpose: After this plan, opening "New issue" on GitHub presents three structured forms with required fields; blank issues are blocked; security disclosures are routed off the public issue tracker.

Output: Four YAML files under .github/ISSUE_TEMPLATE/ and a small extension to tests/test_docs.py.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/REQUIREMENTS.md
@.planning/ROADMAP.md
@README.md
@tests/test_docs.py
</context>

<interfaces>
GitHub YAML issue form reference: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms

Each form requires top-level keys: `name`, `description`, `body`. Recommended: `title`, `labels`, `assignees`.
Body items: types `markdown`, `input`, `textarea`, `dropdown`, `checkboxes`. Required validation via `validations: {required: true}`.

### bug_report.yml (skeleton)
```yaml
name: Bug Report
description: Report a defect in ShopPyBot core or an officially supported plugin
title: "[Bug]: "
labels: ["bug", "triage"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for filing a bug. Please complete every required field.
        Security issues: do NOT use this form. See SECURITY.md.
  - type: input
    id: shoppybot-version
    attributes:
      label: ShopPyBot version / commit SHA
    validations: {required: true}
  - type: dropdown
    id: os
    attributes:
      label: Operating System
      options: [Windows, macOS, Linux]
    validations: {required: true}
  - type: input
    id: python-version
    attributes:
      label: Python version (output of `python --version`)
    validations: {required: true}
  - type: textarea
    id: steps
    attributes:
      label: Steps to reproduce
      description: Minimum config.yml (REDACT CREDENTIALS) and exact commands
    validations: {required: true}
  - type: textarea
    id: expected
    attributes:
      label: Expected behavior
    validations: {required: true}
  - type: textarea
    id: actual
    attributes:
      label: Actual behavior + log snippet
      description: Paste relevant lines from logs/. Redact credentials and PII.
      render: shell
    validations: {required: true}
  - type: checkboxes
    id: confirmations
    attributes:
      label: Confirmations
      options:
        - label: I have not included credentials, CVVs, or PII in this report
          required: true
        - label: This is not a security vulnerability (those go to SECURITY.md)
          required: true
```

### plugin_request.yml (skeleton)
```yaml
name: New Platform Plugin Request
description: Request support for a new retailer
title: "[Plugin]: "
labels: ["plugin-request", "triage"]
body:
  - type: markdown
    attributes:
      value: |
        ShopPyBot welcomes new plugins. Plugins ship as drop-in files
        in `plugins/`. See `plugins/PLUGIN_DEV.md` and `CONTRIBUTING.md`.
  - type: input
    id: platform-name
    attributes:
      label: Platform name
    validations: {required: true}
  - type: input
    id: store-url
    attributes:
      label: Storefront URL (example product page)
    validations: {required: true}
  - type: dropdown
    id: anti-detection
    attributes:
      label: Known anti-detection difficulty
      options:
        - "Low (no visible bot detection)"
        - "Medium (CAPTCHA on checkout)"
        - "High (PerimeterX, Akamai, or similar)"
        - "Unknown"
    validations: {required: true}
  - type: checkboxes
    id: contributor
    attributes:
      label: Contributor intent
      options:
        - label: I am willing to implement this plugin myself
        - label: I am requesting someone else implement it
        - label: I confirm I have read SECURITY.md and accept the TOS / account-risk disclaimer
          required: true
```

### platform_issue.yml (skeleton)
```yaml
name: Existing Plugin Issue
description: Report a problem with an existing platform plugin (Amazon, BestBuy, or community)
title: "[Plugin Issue]: "
labels: ["plugin-issue", "triage"]
body:
  - type: markdown
    attributes:
      value: |
        Use this template for issues with a specific plugin. For core bugs,
        use the Bug Report template. For security issues, see SECURITY.md.
  - type: dropdown
    id: plugin
    attributes:
      label: Affected plugin
      options: [amazon, bestbuy, walmart, target, gamestop, squareenix, newegg, other]
    validations: {required: true}
  - type: input
    id: store-url
    attributes:
      label: Product URL that triggered the issue
    validations: {required: true}
  - type: textarea
    id: log-snippet
    attributes:
      label: Log snippet (redact credentials)
      render: shell
    validations: {required: true}
  - type: input
    id: last-working
    attributes:
      label: Last known working commit / version (if any)
```

### config.yml (issue chooser)
```yaml
blank_issues_enabled: false
contact_links:
  - name: Security vulnerability
    url: https://github.com/thezoid/ShopPyBot/security/advisories/new
    about: Do not file security issues publicly. See SECURITY.md.
  - name: Read SECURITY.md
    url: https://github.com/thezoid/ShopPyBot/blob/master/SECURITY.md
    about: Responsible disclosure policy and per-platform risk register.
```

Decision (planner locked): use YAML form templates (modern GitHub UX), NOT legacy markdown templates.
Style rules:
- No emojis
- No em dashes
- ASCII only
- Each YAML file parses as valid YAML
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: RED tests for issue templates</name>
  <files>tests/test_docs.py</files>
  <read_first>
    - tests/test_docs.py
    - GitHub issue forms docs reference (provided in <interfaces>)
  </read_first>
  <behavior>
    Append to tests/test_docs.py under `# DOCS-04 (Plan 03-03): GitHub issue templates`:

      - test_issue_template_dir_exists: .github/ISSUE_TEMPLATE/ exists
      - test_bug_report_yml_exists: bug_report.yml exists
      - test_plugin_request_yml_exists: plugin_request.yml exists
      - test_platform_issue_yml_exists: platform_issue.yml exists
      - test_chooser_config_yml_exists: .github/ISSUE_TEMPLATE/config.yml exists
      - test_form_yml_files_parse: each of {bug_report,plugin_request,platform_issue,config}.yml parses as valid YAML
      - test_form_templates_have_required_top_level_keys (parametrized over the 3 forms): each form has keys "name", "description", "body", "labels"
      - test_form_bodies_have_at_least_one_required_field (parametrized over the 3 forms): walks the body list and asserts at least one entry has `validations: {required: true}`
      - test_chooser_disables_blank_issues: config.yml has `blank_issues_enabled: false`
      - test_chooser_links_security: config.yml contact_links contains an entry whose URL contains either "security/advisories" or "SECURITY.md"

    Note on YAML loading: use `yaml.safe_load`. If PyYAML is not in requirements.txt, the executor adds it (it IS already a transitive dep via pydantic/other; verify with `python -c "import yaml"` first).
  </behavior>
  <action>
    1. Verify PyYAML is importable: `python -c "import yaml"`. (It already is; ShopPyBot uses config.yml.)
    2. Open `tests/test_docs.py`. Append section header.
    3. Add module-level constants:
       ```python
       ISSUE_TEMPLATE_DIR = pathlib.Path(".github/ISSUE_TEMPLATE")
       FORM_FILES = ["bug_report.yml", "plugin_request.yml", "platform_issue.yml"]
       CHOOSER_FILE = ISSUE_TEMPLATE_DIR / "config.yml"
       ```
    4. Add the tests listed under `<behavior>`. Use `pytest.mark.parametrize` for the two per-form tests.
    5. Run `rtk pytest tests/test_docs.py -q`. New tests fail (no files yet) -- RED state.
  </action>
  <verify>
    <automated>rtk pytest tests/test_docs.py -q</automated>
  </verify>
  <done>RED tests for issue templates committed</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Ship the four issue template YAML files (GREEN)</name>
  <files>
    .github/ISSUE_TEMPLATE/bug_report.yml,
    .github/ISSUE_TEMPLATE/plugin_request.yml,
    .github/ISSUE_TEMPLATE/platform_issue.yml,
    .github/ISSUE_TEMPLATE/config.yml
  </files>
  <read_first>
    - tests/test_docs.py (RED tests from Task 1)
    - .planning/REQUIREMENTS.md (DOCS-04 wording)
  </read_first>
  <behavior>
    - All issue-template tests pass
    - Each YAML file parses with `yaml.safe_load`
    - Full pytest suite stays green
  </behavior>
  <action>
    1. Create `.github/ISSUE_TEMPLATE/` directory if it does not exist.
    2. Write each of the four YAML files using the skeletons in `<interfaces>` verbatim
       (small adjustments allowed: more fields, friendlier wording; do NOT remove required
       keys or required-field validations).
    3. After writing, parse each file with `python -c "import yaml; yaml.safe_load(open('<file>'))"`
       to confirm YAML validity before running the test suite.
    4. Run `rtk pytest tests/test_docs.py -q`. All DOCS-04 tests pass.
    5. Run `rtk pytest -q`. No regressions.
  </action>
  <verify>
    <automated>rtk pytest tests/test_docs.py -q</automated>
    <automated>python -c "import yaml; [yaml.safe_load(open(f'.github/ISSUE_TEMPLATE/{n}')) for n in ['bug_report.yml','plugin_request.yml','platform_issue.yml','config.yml']]"</automated>
    <automated>rtk pytest -q</automated>
  </verify>
  <done>Three issue forms + chooser config shipped; DOCS-04 satisfied; tests green</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| public user files an issue | Without templates, security bugs and credential dumps appear in public issues. Templates + chooser config route those off-tracker |
| issue reporter pastes logs/config | Logs can contain credentials, session cookies, PII. Templates instruct redaction explicitly with a required confirmation checkbox |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-3-DOCS-04-PUBLIC-SEC | Information Disclosure | Security vuln filed as public issue | mitigate | config.yml chooser routes "Security vulnerability" to GitHub Security Advisories and SECURITY.md; blank issues disabled. Tests assert both anchors |
| T-3-DOCS-04-CRED-LEAK | Information Disclosure | User pastes credentials in log snippets | mitigate | Bug report form includes a `required: true` checkbox confirming no credentials/PII included; markdown header in form repeats the warning |
| T-3-DOCS-04-MALFORMED | Tampering | YAML form invalidates GitHub's parser; falls back to blank issue | mitigate | Tests assert each YAML parses with `yaml.safe_load`; required top-level keys present |
</threat_model>

<verification>
- `rtk pytest -q tests/test_docs.py` passes including new DOCS-04 tests
- `rtk pytest -q` full suite passes
- Each of the four YAML files parses with `yaml.safe_load`
- `rtk find .github/ISSUE_TEMPLATE/ -name "*.yml"` returns 4 files
</verification>

<success_criteria>
- DOCS-04 satisfied: three structured issue forms + chooser config in place
- Blank issues are disabled at the chooser
- Security disclosures are routed off the public issue tracker
- YAML form templates locked (modern GitHub UX), not legacy markdown
</success_criteria>

<output>
After completion, create `.planning/phases/03-community-documentation/03-03-SUMMARY.md`
</output>
