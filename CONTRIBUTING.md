# Contributing to ShopPyBot

Thank you for your interest in contributing. This document covers the
contribution process, code standards, and the plugin submission checklist.
For all plugin-specific technical detail (ABC contract, DOM selection,
config access, credential handling), see
[plugins/PLUGIN_DEV.md](plugins/PLUGIN_DEV.md). This document links to
that guide and does not duplicate its content.

## Code of Conduct

All contributors are expected to follow the project's
[Code of Conduct](CODE_OF_CONDUCT.md). Please read it before participating.

## Security Issues

Do not report security vulnerabilities in public GitHub issues. Follow the
private disclosure process described in [SECURITY.md](SECURITY.md).

## Getting Started

### Workflow

1. **Fork** the repository and clone your fork locally.
2. **Create a branch** from `master` with a descriptive name, for example
   `feat/plugin-walmart` or `fix/bestbuy-checkout`.
3. **Implement** your change. Keep commits small and focused; one logical
   change per commit.
4. **Test** by running the full suite locally before opening a PR:
   ```sh
   python -m pytest tests/ -q
   ```
5. **Open a pull request** against `master` with a clear description of what
   was changed and why.

### Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): short description under 72 characters

Optional body explaining why, not just what.
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

### Style Rules

- PEP 8 compliance required for all Python files.
- Variable and function names: `snake_case`.
- Maximum function length: 30 lines. Maximum file length: 300 lines.
- No new runtime dependencies without written justification in the PR
  explaining why no existing dependency covers the need.

## Contributing a Plugin

The full plugin technical how-to (naming convention, ABC methods, DOM
selection, config access, credential handling, and testing patterns) lives
in [plugins/PLUGIN_DEV.md](plugins/PLUGIN_DEV.md). Read that guide first.

Every new-plugin PR must also satisfy the Plugin Submission Checklist below.

## Plugin Submission Checklist

Before opening a plugin PR, verify each item:

- [ ] **File naming:** Plugin file is named `shopbot_plugin_<name>.py` and
      lives in the `plugins/` directory. Files that do not match this pattern
      are never loaded by the registry.
- [ ] **RetailerPlugin ABC compliance:** Plugin class subclasses
      `RetailerPlugin` from `core.plugin_base` and provides concrete
      implementations of both required async methods:
      `check_availability(self, url: str) -> bool` and
      `auto_buy(self, url: str) -> bool`.
- [ ] **`domain_patterns` attribute:** Plugin class defines a `domain_patterns`
      class attribute (list of strings) that correctly identifies the target
      retailer's hostnames. The registry uses substring matching against the
      URL hostname.
- [ ] **Test file included:** A pytest test file (for example
      `tests/test_shopbot_plugin_<name>.py`) is shipped with the plugin and
      covers at minimum ABC compliance. The full suite must be green:
      ```sh
      python -m pytest tests/ -q
      ```
- [ ] **Anti-detection metadata declared:** The plugin class declares all three
      required class attributes (see [plugins/PLUGIN_DEV.md](plugins/PLUGIN_DEV.md)
      section 2 for the full ABC contract):
      - `difficulty`: one of `"easy"`, `"medium"`, or `"hard"` — reflects the
        anti-detection effort required to operate reliably on this retailer.
      - `requires_proxy`: `True` or `False` — set `True` if the plugin will not
        function correctly without a proxy configured in `config.yml`.
      - `requires_captcha`: `True` or `False` — set `True` if the plugin relies
        on the CAPTCHA solver integration to complete purchases.

      These three values are also used to populate the plugin's row in the wiki
      registry (see [docs/PLUGIN_REGISTRY.md](docs/PLUGIN_REGISTRY.md)). Ensure
      the PR description includes the row values so the maintainer can update the
      wiki when the PR is merged.
- [ ] **No secrets or credentials committed:** All credentials (email,
      password, API keys, tokens) are read from environment variables at
      runtime. Nothing sensitive is hardcoded in the plugin file, in
      `config.yml`, or in any committed file. See
      [plugins/PLUGIN_DEV.md](plugins/PLUGIN_DEV.md) section 6 for the
      approved pattern.
