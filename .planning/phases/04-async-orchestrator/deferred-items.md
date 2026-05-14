# Phase 04 Deferred Items

## Pre-existing issues observed during 04-05 execution (out of scope)

- `tests/test_utils.py` imports `make_tiny` from `utils` but `make_tiny` lives in `main.py`.
  This was broken before Phase 4. Suggest moving `make_tiny` into `utils.py` in a future doc
  or refactor plan, or updating the import.
- Python 3.14 environment lacks `selenium`, `pygame`, and `pytest-asyncio` installed in
  site-packages, so `py -3.13` is required to run the full suite. Not a code issue.
