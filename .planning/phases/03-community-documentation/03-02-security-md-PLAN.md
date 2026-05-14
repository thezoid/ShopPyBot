---
phase: 03-community-documentation
plan: 02
type: execute
wave: 0
depends_on: []
files_modified:
  - SECURITY.md
  - tests/test_docs.py
autonomous: true
requirements:
  - DOCS-03
tags:
  - documentation
  - security
  - disclosure

must_haves:
  truths:
    - "SECURITY.md exists at the repo root"
    - "SECURITY.md documents a responsible disclosure process with a contact method (dedicated security email AND a link to GitHub Security Advisories)"
    - "SECURITY.md enumerates known TOS/legal risks per platform: Amazon, BestBuy, Walmart, Target, GameStop, Square Enix, NewEgg (one-line risk note each)"
    - "SECURITY.md documents per-platform anti-detection difficulty disclosure: at minimum Walmart (PerimeterX/HUMAN Security high risk) and Target (Akamai blocks headless) are called out"
    - "SECURITY.md provides guidance on keeping credentials out of commits: env vars only, getpass for CVV, never commit config.yml with secrets"
    - "SECURITY.md uses a clearly-marked placeholder for the security contact email (e.g., <TODO: set security contact>) when no project email is set, so the executor cannot accidentally publish a wrong address"
    - "tests/test_docs.py asserts SECURITY.md exists and contains the required anchors"
  artifacts:
    - path: "SECURITY.md"
      provides: "Responsible disclosure policy + per-platform TOS/legal risk register + credential hygiene"
      contains: "Responsible Disclosure"
      min_lines: 60
    - path: "tests/test_docs.py"
      provides: "Substring/existence tests asserting SECURITY.md content anchors"
  key_links:
    - from: "SECURITY.md"
      to: "GitHub Security Advisories"
      via: "external link"
      pattern: "security/advisories"
    - from: "SECURITY.md"
      to: "README.md"
      via: "back-reference to TOS disclaimer for legal context"
      pattern: "README\\.md"
---

<objective>
Ship SECURITY.md covering DOCS-03 in three parts: responsible disclosure policy, per-platform TOS/legal/anti-detection risk register, and credential hygiene guidance.

Purpose: After this plan, a security researcher knows exactly where to send a vulnerability report (and where NOT to file it), and a contributor adding a new platform plugin can see the risk-disclosure template they must follow.

Output: SECURITY.md at repo root and a small extension to tests/test_docs.py.
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
SECURITY.md required structure:

```markdown
# Security Policy

## Responsible Disclosure
Do not file security issues as public GitHub issues. Two private channels:

1. Email: <TODO: set security contact>
   (Executor: leave this literal TODO marker if no project security email is provided.)
2. GitHub Security Advisories: https://github.com/<owner>/ShopPyBot/security/advisories/new
   (Executor: use a generic relative `/security/advisories` form if the owner is unknown.)

What to include in a report:
- Affected component (file/module)
- Steps to reproduce
- Impact assessment
- Suggested mitigation (optional)

Response target: acknowledgement within 7 days; fix or mitigation plan within 30 days for confirmed issues.

## Supported Versions
Only the current master branch receives security fixes. There are no LTS branches.

## Known TOS and Legal Risks per Platform
ShopPyBot automates retail purchases. Automation may violate the Terms of Service
of the targeted platform and can result in account suspension or banning. Each
platform plugin must declare its known risk profile.

| Platform | TOS / Legal Risk | Anti-Detection Difficulty |
|----------|------------------|---------------------------|
| Amazon | TOS prohibits automation; account suspension risk on detection | Medium (manual OTP login, CAPTCHA on purchase) |
| BestBuy | TOS prohibits automation; account flag on aggressive polling | Medium (queue/throttle on high traffic SKUs) |
| Walmart | TOS prohibits automation; account ban risk | High (PerimeterX / HUMAN Security; headless Selenium consistently blocked) |
| Target | TOS prohibits automation; account ban risk | High (Akamai Bot Manager; headless blocked; checkout flow experimental) |
| GameStop | TOS prohibits automation | Medium-High (CAPTCHA on checkout) |
| Square Enix | TOS prohibits automation | Medium |
| NewEgg | TOS prohibits automation | Medium |

See README.md for the general personal-use disclaimer.

## Credential Hygiene
- Never commit `config.yml` with real credentials. The repo .gitignore excludes it; verify before pushing.
- Credentials are read from environment variables only (see README.md "Credentials and Environment").
- CVV is collected at runtime via `getpass.getpass()` and never written to logs or config files.
- Plugin contributors: never call `from config import config`; receive a platform_config slice in `__init__` instead.
- Rotate any credential that has appeared in a commit, even briefly. Treat shell history and CI logs as compromised.

## Out of Scope
- Vulnerabilities in target retailer websites (report to the retailer)
- Anti-detection bypass requests (this project does not develop or distribute bypass techniques)
```

Style rules:
- No emojis
- No em dashes (use colons, commas, or restructure)
- No `---`, `***`, `___` horizontal-rule lines
- Length target: 60-150 lines
- Reuse the platform list and risk wording from REQUIREMENTS.md PLG-04..08 where applicable
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: RED tests for SECURITY.md</name>
  <files>tests/test_docs.py</files>
  <read_first>
    - tests/test_docs.py
    - .planning/REQUIREMENTS.md (DOCS-03 wording; PLG-04..08 risk wording)
    - README.md (credential hygiene section to cross-reference)
  </read_first>
  <behavior>
    Append to tests/test_docs.py under a new section header `# DOCS-03 (Plan 03-02): SECURITY.md`:

      - test_security_md_exists: SECURITY.md exists at repo root
      - test_security_md_responsible_disclosure: lowercase source contains "responsible disclosure"
      - test_security_md_contact_method: source contains EITHER a literal "<TODO: set security contact>" marker OR an "@" character (an email address) AND the substring "security/advisories" (GitHub Security Advisories link)
      - test_security_md_platforms_enumerated: source contains all of: "Amazon", "BestBuy", "Walmart", "Target", "GameStop", "Square Enix", "NewEgg"
      - test_security_md_anti_detection_walmart: source contains "PerimeterX" OR "HUMAN Security"
      - test_security_md_anti_detection_target: source contains "Akamai"
      - test_security_md_credential_hygiene: lowercase source contains all of: "config.yml", "environment variable" (or "env var"), "getpass"
      - test_security_md_links_readme: source contains "README.md"
      - test_security_md_no_em_dashes: em dash `—` does NOT appear
      - test_security_md_no_horizontal_rule: no line stripped equals "---", "***", or "___"
  </behavior>
  <action>
    1. Open `tests/test_docs.py`. Append section header comment.
    2. Add: `SECURITY_FILE = pathlib.Path("SECURITY.md")` and helper `_security_text()`.
    3. Add the 10 tests listed under `<behavior>`.
    4. Run `rtk pytest tests/test_docs.py -q`. New tests fail (SECURITY.md does not exist) -- RED state.
  </action>
  <verify>
    <automated>rtk pytest tests/test_docs.py -q</automated>
  </verify>
  <done>RED tests for SECURITY.md committed</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Ship SECURITY.md (GREEN)</name>
  <files>SECURITY.md</files>
  <read_first>
    - tests/test_docs.py (RED tests from Task 1)
    - .planning/REQUIREMENTS.md (DOCS-03 + PLG-04..08 risk annotations are authoritative)
    - README.md (credential and disclaimer wording to align with)
  </read_first>
  <behavior>
    - All 10 new tests pass
    - Full pytest suite stays green
    - Zero em dashes and zero horizontal-rule lines
  </behavior>
  <action>
    1. Create `SECURITY.md` at the repo root using the outline in `<interfaces>`.
       Required literal substrings:
         - "Responsible Disclosure" (or lowercase "responsible disclosure")
         - "security/advisories"
         - Either an "@" (email address) OR the literal "<TODO: set security contact>" marker (Decision: planner locks the placeholder approach since no project email is set)
         - "Amazon", "BestBuy", "Walmart", "Target", "GameStop", "Square Enix", "NewEgg"
         - "PerimeterX" or "HUMAN Security" (Walmart difficulty)
         - "Akamai" (Target difficulty)
         - "config.yml"
         - "environment variable" or "env var"
         - "getpass"
         - "README.md"
       Style:
         - No em dashes
         - No horizontal-rule lines
         - No emojis
       Length target: 60-150 lines.
    2. Run `rtk pytest tests/test_docs.py -q`. All DOCS-03 tests pass.
    3. Run `rtk pytest -q`. No regressions.
  </action>
  <verify>
    <automated>rtk pytest tests/test_docs.py -q</automated>
    <automated>rtk pytest -q</automated>
    <automated>rtk grep -c "Responsible Disclosure" SECURITY.md</automated>
    <automated>rtk grep -c "PerimeterX\|HUMAN Security" SECURITY.md</automated>
  </verify>
  <done>SECURITY.md shipped; DOCS-03 satisfied; tests green</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| security researcher discovers a vuln -> chooses disclosure channel | If SECURITY.md is missing or vague, researchers default to public issues, leaking exploit details before a fix is available |
| new contributor adds a plugin without risk disclosure | Plugin ships with no anti-detection / TOS context; downstream users may unknowingly violate platform TOS and lose accounts |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-3-DOCS-03-PUBLIC | Information Disclosure | Security bugs filed publicly | mitigate | SECURITY.md provides two private channels (email + GitHub Security Advisories). Tests assert the advisories link substring exists |
| T-3-DOCS-03-EMAIL | Spoofing | Wrong/placeholder contact email | mitigate | Planner locks `<TODO: set security contact>` marker rather than guessing an email. Test allows either a real `@` or the literal TODO so the file ships honestly |
| T-3-DOCS-03-TOS | Repudiation | Contributor claims they were not warned about TOS risk | mitigate | Per-platform risk table enumerates known TOS / anti-detection difficulty; tests assert all 7 platforms named |
| T-3-DOCS-03-CREDS | Information Disclosure | Credentials committed | mitigate | Credential Hygiene section makes env-var-only and getpass mandatory; tests assert the anchors |
</threat_model>

<verification>
- `rtk pytest -q tests/test_docs.py` passes including the 10 new tests
- `rtk pytest -q` full suite passes
- `rtk find SECURITY.md` resolves
- `rtk grep -n "—" SECURITY.md` returns no matches
</verification>

<success_criteria>
- DOCS-03 satisfied: responsible disclosure + per-platform risks + credential hygiene present
- Per-platform anti-detection difficulty is disclosed in SECURITY.md (not duplicated in CONTRIBUTING.md, per planner constraint)
- Security contact is either a real email or a clearly-marked TODO placeholder (no guessed addresses)
</success_criteria>

<output>
After completion, create `.planning/phases/03-community-documentation/03-02-SUMMARY.md`
</output>
