# Contributing to ShopPyBot

Thanks for your interest in contributing. ShopPyBot is a plugin-first retail
availability bot. This document covers the contributor workflow: how to fork,
branch, commit, test, and submit a plugin or a core change.

## Before you start

Read the [Disclaimer in README.md](README.md) before writing any code that
interacts with a retailer. ShopPyBot is built for personal use; automating
purchases may violate a retailer's Terms of Service and can result in account
suspension. By contributing, you accept that risk for your own test accounts
and you do not enable it for anyone else.

Found a security bug? Do NOT open a public GitHub issue. Follow the
responsible disclosure path in [SECURITY.md](SECURITY.md).

## Development workflow

1. Fork the repository on GitHub.
2. Clone your fork and create a topic branch from `master`:

   ```sh
   git clone https://github.com/<your-user>/ShopPyBot.git
   cd ShopPyBot
   git checkout -b feat/my-change
   ```

3. Set up a local environment:

   ```sh
   python -m venv .venv
   .venv\Scripts\activate          # Windows
   source .venv/bin/activate        # macOS / Linux
   pip install -r requirements.txt
   ```

4. Make your changes. Add or extend tests in `tests/` alongside the code.
5. Run the full test suite locally. All tests must pass:

   ```sh
   pytest
   ```

6. Commit using the convention below.
7. Push your fork and open a pull request (PR) against `master` on the
   upstream repository.

Keep PRs focused. One feature, one fix, or one plugin per PR. Unrelated
refactors belong in a separate PR.

## Commit message convention

Format: `type(scope): description`

Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`.

Subject under 72 characters. Describe why, not just what. Reference an issue
number when one exists.

Examples:

```
feat(plugin-walmart): add availability check via product API
fix(registry): handle missing domain_pattern attribute gracefully
docs(contributing): add plugin submission checklist
test(plugin-amazon): cover OTP timeout path
refactor(driver): collapse two near-identical build paths
chore(deps): pin selenium to 4.21.0
```

Do not mention AI tools or generated authorship in commit metadata.

## Tests

- `pytest` is the test runner; tests live in `tests/`.
- New code requires tests. Bug fixes require a regression test that fails
  before the fix and passes after.
- Prefer RED-before-GREEN: write the failing test first, then the
  implementation. The git history should show the failing test commit before
  the implementation commit.
- No test may spawn a real Chrome browser. Stub `driver.build_driver` with a
  sentinel object. See `tests/test_plugins_amazon.py` for the pattern.
- Run `pytest -x -q` before opening a PR.

## Contributing a plugin

The technical contract for a plugin (ABC methods, registry rules, naming, the
`domain_pattern` matcher, driver construction, anti-patterns) is documented in
[plugins/PLUGIN_DEV.md](plugins/PLUGIN_DEV.md). Read it first. It is the
authoritative reference. This section covers only the PR workflow.

To onboard a new retailer:

1. Copy `plugins/example_plugin.py` to `plugins/shopbot_plugin_<platform>.py`.
2. Implement `check_availability` and `auto_buy` against your retailer.
3. Declare `domain_pattern` as a non-empty `list[str]` of lowercase hostnames.
4. Add tests at `tests/test_plugins_<platform>.py` (import test, ABC compliance
   test, mocked routing test).
5. Document the anti-detection risk in your plugin's class docstring.
6. Open a PR using the checklist below.

### Plugin Submission Checklist

Copy this block into your PR description and check each item before requesting
review.

- [ ] Filename matches `plugins/shopbot_plugin_<platform>.py`
- [ ] Exactly one `RetailerPlugin` subclass in the file
- [ ] Subclasses `RetailerPlugin` from `plugin_base`
- [ ] Implements `check_availability(self, url) -> bool`
- [ ] Implements `auto_buy(self, url, config) -> bool`
- [ ] Declares `domain_pattern: list[str]` (a list, not a single string)
- [ ] Driver is constructed inside `__init__` via `build_driver` (never at
      module scope)
- [ ] Tests added at `tests/test_plugins_<platform>.py` covering: import,
      ABC compliance, mocked URL routing
- [ ] Anti-detection risk declared in the class docstring (e.g.,
      "PerimeterX/HUMAN Security risk", "Akamai blocks headless Selenium")
- [ ] No credentials, secrets, cookies, session tokens, or PII in any commit
- [ ] `pytest -x -q` passes locally

## Reporting bugs and requesting features

File a GitHub issue using the appropriate template. Templates pre-fill the
fields reviewers need (repro steps, retailer, environment). Provide logs
with credentials and addresses redacted.

Security issues: do NOT file publicly. See [SECURITY.md](SECURITY.md).

## Code style

ShopPyBot follows the conventions enforced in the existing codebase:

- Small functions with early returns and guard clauses.
- No new abstractions or configuration knobs without a concrete use case.
- No emojis in source files or commit messages.
- No `from config import config`; the legacy singleton was retired in
  Phase 1.
- Log via `writeLog(message, type)` from `logger`; never `print` to stdout.
