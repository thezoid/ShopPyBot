# Deferred Items — Phase 01 Foundations + Security

Items discovered during execution that are out of scope for the current plan.

## From Plan 01-01

### Pre-existing pytest collection errors

Discovered while running `pytest -q` at the end of Plan 01-01. Both errors exist on master before any task in 01-01 ran (verified via `git stash`).

1. `tests/test_config.py` — `FileNotFoundError: config.yml` on collection. `config.py` calls `load_config()` at import time, which requires `config.yml` in the cwd. Will be resolved by Plan 01-03 (Pydantic config schema) which deletes this file per 01-CONTEXT note: "to be deleted in Plan 03; do not import from it".

2. `tests/test_utils.py` — `ImportError: cannot import name 'make_tiny' from 'utils'`. `utils.py` has no `make_tiny` function. Test was stale before this plan. Recommendation: delete the test or implement `make_tiny`, deferred to a later plan.

### Pre-existing dependency conflict warnings

`pip install -r requirements.txt` emits conflict warnings about a globally-installed `seleniumbase 4.33.11` package in the user's environment. Not caused by this plan's requirements file. Recommend developers use a fresh venv per CLAUDE.md instructions.
