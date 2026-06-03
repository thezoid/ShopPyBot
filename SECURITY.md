# Security Policy

## Supported Versions

The `master` branch is the only supported line for security fixes. Older tags
and branches do not receive patches. If you are running an older release, update
to the latest commit on `master` before reporting.

## Reporting a Vulnerability

**Do NOT file a public GitHub issue for security vulnerabilities.** Public issues
expose details before a fix is available, putting all users at risk.

Use one of these private channels:

1. **GitHub private security advisory (preferred):** Navigate to the Security
   tab of this repository and choose "Report a vulnerability". GitHub keeps the
   report private until coordinated disclosure.

2. **Direct email:** Send a report to
   `SECURITY_CONTACT_PLACEHOLDER@example.com`
   *(This is a placeholder. The maintainer must replace it with a real verified
   address before launch.)*

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
