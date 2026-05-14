# Pull Request

Thanks for contributing. Please read [CONTRIBUTING.md](../CONTRIBUTING.md) before
opening the PR if you have not already.

<!-- Keep the PR focused: one feature, one fix, or one plugin per PR. -->

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

<!-- Skip this whole block if your PR does not add or modify a plugin. -->

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

- [ ] anti-detection risk declared in the plugin module docstring
- [ ] Updated per-platform risk row in [SECURITY.md](../SECURITY.md) if adding a new platform

## Security and credentials

- [ ] No credentials, API keys, CVVs, or PII included in this PR
- [ ] No `config.yml` with real values committed
- [ ] If this PR fixes a security issue, the disclosure flow in [SECURITY.md](../SECURITY.md) was followed first

## Manual test plan

List the exact commands or clicks a reviewer can run to validate the change.
