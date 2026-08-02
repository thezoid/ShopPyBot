# Security Policy

## Supported Versions

The `master` branch is the only supported line for security fixes. Older tags
and branches do not receive patches. If you are running an older release, update
to the latest commit on `master` before reporting.

## Reporting a Vulnerability

**Do NOT file a public GitHub issue for security vulnerabilities.** Public issues
expose details before a fix is available, putting all users at risk.

Use GitHub's private vulnerability reporting flow: navigate to
[https://github.com/thezoid/ShopPyBot/security/advisories/new](https://github.com/thezoid/ShopPyBot/security/advisories/new)
(or the Security tab → "Report a vulnerability"). GitHub keeps the report
private until coordinated disclosure — this is the only supported reporting
channel; there is no public email address for security reports.

> **Operator note:** Private Vulnerability Reporting must be enabled once in
> repository Settings → Security → "Private vulnerability reporting" for this
> link to work. This is a one-time repo setting and is not toggled by this
> automation.

Your report should include: affected version, description of the issue, steps
to reproduce, and (if known) suggested remediation.

## Coordinated Disclosure

The project maintainer(s) will acknowledge your report within **7 days**. The
target coordinated disclosure window is **90 days** from the acknowledgement
date. If a fix requires longer, we will communicate the reason and agree on an
updated timeline with you. Credit is given to reporters in the release notes
unless they prefer to remain anonymous.

## Platform Risk

Each supported retailer carries distinct anti-detection and legal risks. The
table below uses a three-tier scale: **low**, **medium**, **high**.

| Platform     | Anti-Detection Risk | TOS/Legal Risk | Notes |
|--------------|---------------------|----------------|-------|
| amazon.com   | High                | High           | Aggressive bot detection; automated purchasing violates Amazon Conditions of Use. Account suspension risk is well-documented. |
| bestbuy.com  | Medium              | Medium         | Queue-based checkout partially mitigates bot detection; TOS prohibits automated purchasing. Account-ban risk is real but less aggressive than Amazon. |
| walmart.com  | High                | High           | Protected by PerimeterX/HUMAN Security (Bot Defender), which scores 2,500+ behavioral signals per request; headless detection without spoofing is near-certain. Automated purchasing violates Walmart TOS; auto-buy will likely be blocked. |
| target.com   | High                | High           | Protected by Akamai Bot Manager, which detects headless Chromium with ~80% accuracy. Auto-buy (checkout) is experimental and frequently blocked; availability checks may intermittently succeed in non-headless mode. Automated purchasing violates Target TOS. |
| gamestop.com | Medium              | Medium         | Product-page protection is lighter than Walmart or Target, but a CAPTCHA appears at checkout. Availability checks are likely functional; auto-buy will be blocked without a CAPTCHA solver integration. Automated purchasing violates GameStop TOS. |
| store.square-enix-games.com | Medium | Medium      | Best-estimate risk: likely basic Cloudflare or OEM protection (no major vendor confirmed). Lower-volume retail site; headless detection is less aggressive than PerimeterX or Akamai. Selectors are best-effort and require live verification. Automated purchasing likely violates Square Enix TOS. |
| newegg.com   | Medium              | Medium         | Best-estimate risk: likely Cloudflare or lightweight protection (no major vendor confirmed). Historically targeted during GPU drops; UA rotation and headless toggle reduce signal at the margins but do not guarantee evasion. Automated purchasing likely violates NewEgg TOS. |

When new platforms are added (Phase 6), each must append a row to this table
with a documented risk assessment before the plugin is merged.

## Credentials and Secrets

Credentials must never be stored in `config.yml`, committed to the repository,
or written to log files at any log level.

The correct posture, enforced throughout Phase 1 and required for all plugins:

- Store credentials in environment variables only.
- Copy `.env.example` to `.env` and populate it locally; `.env` is gitignored
  and must never be committed.
- The `getpass` module or `os.environ.get()` are the approved reading patterns.
- If a credential is missing at runtime, log an error and skip the affected
  operation; do not fall back to a hardcoded default.

## Legal Scope and Disclaimer

ShopPyBot is provided for personal, non-commercial use only, on an "as is"
basis, without warranty of any kind, express or implied. Each contributor and
operator is solely responsible for ensuring their use complies with the Terms
of Service of every retailer they interact with and with applicable law. The
developer(s) accept no liability for any consequences arising from use of this
software or any derivative. This policy does not expand, limit, or supersede
the full Disclaimer in `README.md`.
