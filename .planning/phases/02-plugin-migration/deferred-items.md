# Phase 02 Deferred Items

Out-of-scope issues discovered during Phase 2 execution.

## D1: tests/test_utils.py imports non-existent `make_tiny` from `utils`

* **Discovered:** Plan 02-04, full-suite pytest run
* **Origin commit:** `0177274` (pre-Phase-1, initial repo state)
* **Symptom:** `ImportError: cannot import name 'make_tiny' from 'utils'`
* **Root cause:** `make_tiny` lives in `main.py`, not `utils.py`. The test
  file was authored before the entrypoint refactor and never updated.
* **Status:** Pre-existing, not caused by this plan. Test collection error
  blocks running the full suite without `--ignore`.
* **Suggested fix:** Either delete `tests/test_utils.py` (it tests live
  HTTP against tinyurl.com which is also poor practice) or move `make_tiny`
  to `utils.py` and update the import.

## D2: tests/test_models.py sqlite path errors

* **Discovered:** Plan 02-04, full-suite pytest run
* **Origin commit:** `0177274`
* **Symptom:** `sqlite3.OperationalError: unable to open database file` when
  running the two tests in `tests/test_models.py`. `data/` directory does
  not exist at test time, and `models.py` hardcodes `data/shop_py_bot.db`.
* **Status:** Pre-existing, not caused by this plan.
* **Suggested fix:** Either ensure `data/` exists in a fixture (mkdir) or
  parametrize `DB_PATH` so tests can point at `tmp_path`.

## Verification of "not caused by this plan"

`git log --all --oneline tests/test_utils.py tests/test_models.py` both
return only commit `0177274` as the introducing commit, predating all
Phase 1 and Phase 2 work.
