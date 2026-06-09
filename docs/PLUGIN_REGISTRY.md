# Plugin Registry Table Specification

**This file is the in-repo specification for the ShopPyBot plugin registry table.**

The actual registry lives on the project's GitHub wiki, not in this repository.
A maintainer creates and updates the wiki page manually when a plugin PR is merged.
Do not edit the wiki page structure without first updating this spec.

> **In-repo vs. GitHub wiki:** This file (`docs/PLUGIN_REGISTRY.md`) defines what
> the wiki table must contain. The live registry page is maintained separately on the
> GitHub wiki by a project maintainer. The wiki is not part of this repository and
> cannot be updated via a pull request.

## Required Registry Table Columns

Every row in the wiki registry table must supply all nine of the following fields.
Maintainers who populate the wiki page should reject plugin entries that omit any
required field.

| Column | Description |
|--------|-------------|
| **name** | The plugin class name (e.g. `AmazonPlugin`). Must be unique across all registered plugins. |
| **platform** | Human-readable retailer name (e.g. `Amazon`, `Best Buy`). |
| **domain patterns** | The value of the plugin's `domain_patterns` class attribute: a comma-separated list of hostname substrings used for URL routing (e.g. `amazon.com, amazon.co.uk, amazon.ca`). |
| **maintainer** | GitHub username of the plugin author or current maintainer. |
| **anti-detection difficulty** | One of `easy`, `medium`, or `hard`. Mirrors the plugin's `difficulty` class attribute. `easy` means minimal bot-detection countermeasures are required; `hard` means aggressive fingerprinting, CAPTCHA, or WAF challenges are expected. |
| **methods implemented** | Comma-separated list of `RetailerPlugin` methods the plugin overrides beyond the two required ones (e.g. `setup, teardown, login, detect_captcha`). Write `—` if only the two required methods are implemented. |
| **last-verified** | ISO 8601 date (`YYYY-MM-DD`) the plugin was last confirmed working against the live retail site. Maintainers update this field when re-testing a plugin. |
| **proxy-required** | `Yes` or `No`. Mirrors the plugin's `requires_proxy` class attribute. `Yes` means the plugin will not function correctly without a proxy configured. |
| **captcha-required** | `Yes` or `No`. Mirrors the plugin's `requires_captcha` class attribute. `Yes` means the plugin relies on a CAPTCHA solver (e.g. 2captcha integration) to complete purchases. |

## Example Row

The table below shows one correctly formed registry entry using the built-in Amazon
plugin as reference. Maintainers should follow this format exactly.

| name | platform | domain patterns | maintainer | anti-detection difficulty | methods implemented | last-verified | proxy-required | captcha-required |
|------|----------|-----------------|------------|---------------------------|---------------------|---------------|----------------|------------------|
| AmazonPlugin | Amazon | amazon.com, amazon.co.uk, amazon.ca | maintainer-username | hard | setup, teardown, login, detect_captcha | 2026-06-09 | No | No |

## Population Process

When a plugin PR is merged, the maintainer who approves the PR is responsible for:

1. Opening the project's GitHub wiki.
2. Navigating to (or creating) the `Plugin Registry` page.
3. Adding a new row to the registry table with all nine required fields sourced from
   the merged plugin's class definition and PR metadata.
4. Setting `last-verified` to the merge date.

The wiki page does not exist automatically. A maintainer must create it the first time
a community plugin is merged.

## Keeping the Registry Current

- Update `last-verified` whenever a plugin is re-tested against a live retail site.
- Update `anti-detection difficulty`, `proxy-required`, and `captcha-required` if a
  retailer's bot-detection posture changes.
- Remove a plugin's row from the wiki if the plugin is archived or deleted.
- When a plugin's class attributes change, the PR author must supply the updated row
  values in the PR description (see `.github/PULL_REQUEST_TEMPLATE.md`).
