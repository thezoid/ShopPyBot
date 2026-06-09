# Pull Request

## Summary

Describe what this PR changes and why. Keep it concise: what problem does it solve
or what feature does it add?

## Checklist

Work through each item before requesting review. For non-plugin PRs, mark
plugin-specific items **N/A** with a brief note.

- [ ] **RetailerPlugin ABC compliance:** The plugin class subclasses `RetailerPlugin`
  from `core.plugin_base` and provides concrete implementations of both required
  async methods: `check_availability(self, url: str) -> bool` and
  `auto_buy(self, url: str) -> bool`.

- [ ] **Naming convention:** The plugin file is named `shopbot_plugin_<name>.py`
  and lives in the `plugins/` directory. Files not matching this pattern are never
  loaded by the registry.

- [ ] **`domain_patterns` attribute:** The plugin class defines a `domain_patterns`
  class attribute (list of strings) that correctly identifies the target retailer's
  hostnames. The registry uses substring matching against the URL hostname.

- [ ] **Test file included and suite is green:** A pytest test file
  (e.g. `tests/test_shopbot_plugin_<name>.py`) is included and covers at minimum
  ABC compliance. The full suite passes locally:

  ```sh
  python -m pytest tests/ -q
  ```

- [ ] **Anti-detection metadata declared:** The plugin class sets all three
  required class attributes (see `plugins/PLUGIN_DEV.md` section 2):

  - `difficulty = "easy"` | `"medium"` | `"hard"`
  - `requires_proxy = True` | `False`
  - `requires_captcha = True` | `False`

  Provide the values below in the Plugin Metadata section so the maintainer
  can update the wiki registry when this PR is merged.

- [ ] **No secrets or credentials committed:** All credentials (email, password,
  API keys, tokens) are read from environment variables at runtime. Nothing
  sensitive is hardcoded in the plugin file, in `config.yml`, or in any committed
  file. `.env` is gitignored and is not committed.

- [ ] **Conventional Commits:** All commits in this PR follow the format
  `type(scope): description` (types: `feat`, `fix`, `docs`, `refactor`, `test`,
  `chore`). See [CONTRIBUTING.md](../CONTRIBUTING.md) for details.

## Plugin Metadata

For plugin PRs, fill in all three fields. For non-plugin PRs, write "N/A" on each line.

difficulty: <!-- easy / medium / hard -->
requires_proxy: <!-- true / false -->
requires_captcha: <!-- true / false -->
