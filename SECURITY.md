# Security Policy

## Responsible Disclosure

Do NOT file security issues as public GitHub issues. A public issue can leak
exploit details before a fix is available. Use one of the two private channels
below.

1. Email: `<TODO: set security contact>`

   The maintainers have not published a dedicated security email yet. Until
   they do, prefer channel 2.

2. GitHub Security Advisories: open a private advisory at
   `/security/advisories/new` on the upstream repository
   (https://github.com/thezoid/ShopPyBot/security/advisories/new).

### What to include in a report

- Affected component (file or module path)
- Steps to reproduce
- Impact assessment (what an attacker gains)
- Suggested mitigation, if you have one (optional)
- Your preferred attribution for the fix changelog (optional)

### Response targets

- Acknowledgement within 7 days of receiving the report
- Confirmed-issue triage and a fix or mitigation plan within 30 days
- Public disclosure coordinated with the reporter once a fix ships

## Supported Versions

Only the current `master` branch receives security fixes. There are no LTS
branches and no backports to older tags. If you are running an old checkout,
update to `master` before reporting.

## Reporting Bugs vs Security Issues

Regular bugs, crashes, and feature requests go through the public issue
tracker. See [CONTRIBUTING.md](CONTRIBUTING.md) for the standard reporting
workflow. Anything that looks like a vulnerability (credential exposure,
auth bypass, code execution, data leak) goes through Responsible Disclosure
above instead.

## Known TOS and Legal Risks per Platform

ShopPyBot automates retail purchases. Automation may violate the Terms of
Service of the targeted platform and can result in account suspension or a
permanent ban. Each platform plugin must declare its own risk profile. The
table below is the current baseline. See [README.md](README.md) for the
general personal-use disclaimer that applies to every platform.

| Platform | TOS / Legal Risk | Anti-Detection Difficulty |
|----------|------------------|---------------------------|
| Amazon | TOS prohibits automation; account suspension risk on detection | Medium: manual OTP login, CAPTCHA on purchase |
| BestBuy | TOS prohibits automation; account flag on aggressive polling | Medium: queue and throttle on high-traffic SKUs |
| Walmart | TOS prohibits automation; account ban risk | High: PerimeterX / HUMAN Security; headless Selenium is consistently blocked |
| Target | TOS prohibits automation; account ban risk | High: Akamai Bot Manager; headless blocked; checkout flow is experimental |
| GameStop | TOS prohibits automation; account ban risk | Medium to High: CAPTCHA gates checkout |
| Square Enix | TOS prohibits automation; account ban risk | Medium |
| NewEgg | TOS prohibits automation; account ban risk | Medium |

Plugin contributors adding a new platform must extend this table and declare
the anti-detection risk in their plugin's class docstring. See
[CONTRIBUTING.md](CONTRIBUTING.md) Plugin Submission Checklist.

## Credential Hygiene

The bot intentionally keeps secrets out of the repository. Follow these
rules when contributing code or running the bot:

- `config.yml` is gitignored. Never commit it. Verify with `git status`
  before every push.
- Credentials (`amz_email`, `amz_pwd`, `bb_email`, `bb_password`, and any
  new platform equivalents) are read from environment variables only. Do
  not add them to `config.yml`, even in examples. See README.md
  "Credentials and Environment" for the exact env var names.
- CVV is collected at runtime via `getpass.getpass()`. It is never written
  to logs, never stored in `config.yml`, and never echoed to the terminal.
- Plugin contributors must not call `from config import config`. The legacy
  global config singleton was retired in Phase 1. Plugins receive a
  `platform_config` slice in `__init__` instead.
- Rotate any credential that has appeared in a commit, even briefly. Treat
  shell history, CI logs, and crash dumps as compromised once a secret
  passes through them.
- Do not paste real credentials, cookies, session tokens, or order numbers
  into issues, PRs, or screenshots. Redact before posting.

## Out of Scope

The following are NOT in scope for this security policy. Do not file
advisories about them here.

- Vulnerabilities in target retailer websites (report to the retailer
  directly).
- Anti-detection bypass requests. This project does not develop or
  distribute techniques to defeat platform bot protection.
- Generic dependency CVEs with no demonstrated exploit path through
  ShopPyBot. Open a regular issue or PR to bump the dependency instead.
- Social engineering, phishing, and account takeover against retailer
  accounts. Those are retailer support concerns.
