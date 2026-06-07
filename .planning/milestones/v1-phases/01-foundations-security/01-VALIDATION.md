---
phase: 1
slug: foundations-security
status: ready
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-01
updated: 2026-06-02
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.4 (pytest-asyncio 1.3.0) |
| **Config file** | `pyproject.toml` (created in plan 01, `[tool.pytest.ini_options]`, `asyncio_mode = "auto"`) |
| **Quick run command** | `python -m pytest tests/test_plugin_base.py tests/test_config_schema.py tests/test_logger.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds (offline; network test monkeypatched/skipped) |

---

## Sampling Rate

- **After every task commit:** Run the quick run command (or the single test file for that task)
- **After every plan wave:** Run the full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | — (infra) | T-01-02 | Fixtures write only synthetic config to tmp_path | unit | `python -c "import tomllib; ..."` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 1 | — (infra) | T-01-02 | DB writes redirected to tmp_path | unit | `python -m pytest tests/conftest.py --collect-only -q` | ❌ W0 | ⬜ pending |
| 01-01-03 | 01 | 1 | — (infra) | T-01-01 | Network call monkeypatched; offline deterministic | unit | `python -m pytest tests/test_utils.py tests/test_models.py tests/test_config.py -q` | ✅ (repair) | ⬜ pending |
| 01-02-01 | 02 | 2 | CORE-01, CORE-02 | T-01-ABC / T-01-VER | ABC enforces abstract methods at instantiation | unit | `python -c "from core.plugin_base import ...; assert __abstractmethods__ == {...}"` | ❌ W0 | ⬜ pending |
| 01-02-02 | 02 | 2 | CORE-01, CORE-02 | T-01-ABC | Incomplete subclass raises TypeError; no-op defaults | unit | `python -m pytest tests/test_plugin_base.py -x -q` | ❌ W0 | ⬜ pending |
| 01-03-01 | 03 | 2 | CORE-05, CORE-06, CORE-07, SEC-01 | T-01-CFG / T-01-CRED / T-01-CFGPATH | Validation at startup; no credential fields; env precedence; absolute path | unit | `python -c "from core.config_schema import AppConfig; ..."` | ❌ W0 | ⬜ pending |
| 01-03-02 | 03 | 2 | CORE-05, CORE-06, CORE-07, SEC-01 | T-01-CFG / T-01-CRED | Missing field -> ValidationError; legacy key -> warning; env override | unit | `python -m pytest tests/test_config_schema.py -x -q` | ❌ W0 | ⬜ pending |
| 01-04-01 | 04 | 2 | INFRA-01 | T-01-SC | Pinned deps, no duplicates, gated installs | unit | `python -c "lines=...; assert no duplicates and all pinned"` | ✅ (repair) | ⬜ pending |
| 01-04-02 | 04 | 2 | INFRA-02 | T-01-LOG / T-01-LOGERR | Logging level cached at import; specific exception handling | unit | `python -c "import logger; assert _LOGGING_LEVEL; 'open(' not in writeLog src"` | ✅ (repair) | ⬜ pending |
| 01-04-03 | 04 | 2 | INFRA-02 | T-01-LOG | Zero config.yml re-reads during writeLog | unit | `python -m pytest tests/test_logger.py -x -q` | ❌ W0 | ⬜ pending |
| 01-05-01 | 05 | 3 | SEC-03, SEC-04, SEC-05, INFRA-03 | T-01-WD / T-01-DWS / T-01-STDERR | No disable-web-security; CDP webdriver patch; real UA; Service log_output | source | `python -c "src=open('main.py').read(); assert ... ; ast.parse(src)"` | ✅ (in-place) | ⬜ pending |
| 01-05-02 | 05 | 3 | SEC-01, SEC-02 | T-01-CVV / T-01-ENV / T-01-LOGLEAK | Env-var credentials; getpass CVV; AppConfig startup; no creds in logs | source | `python -c "src=open('main.py').read(); assert getpass and os.environ and no config['app']"` | ✅ (in-place) | ⬜ pending |
| 01-05-03 | 05 | 3 | SEC-01, SEC-06 | T-01-ENV | Credential-free sample; .env.example; README disclaimer | source | `python -c "yaml load sample; assert no app; .env.example; README disclaimer"` | ✅ (in-place) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — pytest + asyncio config, requires-python ">=3.11" (plan 01 task 1)
- [ ] `tests/conftest.py` — shared `tmp_config_yml` + `tmp_data_dir` fixtures (plan 01 task 2)
- [ ] Repair `tests/test_utils.py` — fix `make_tiny` import (from main), monkeypatch network (plan 01 task 3)
- [ ] Repair `tests/test_models.py` — use `tmp_data_dir` fixture for DB path (plan 01 task 3)
- [ ] Repair `tests/test_config.py` — isolate config.py module-level load (plan 01 task 3)
- [ ] `tests/test_plugin_base.py` — stubs for CORE-01, CORE-02 (plan 02 task 2)
- [ ] `tests/test_config_schema.py` — stubs for CORE-05, CORE-06, CORE-07, SEC-01 (plan 03 task 2)
- [ ] `tests/test_logger.py` — stub for INFRA-02 (plan 04 task 3)

Note: new test files are created in their owning implementation plans (task-level TDD), because each test needs its target module to exist. Plan 01 establishes pytest config + fixtures + repairs the pre-existing broken suite so all later plans can attach automated verification.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Bot actually launches Chrome with hardened options | SEC-03/04/05 | Requires a real Chrome binary + display; CDP effect observable only in a live browser | Run `python main.py` with a valid config.yml; in DevTools console `navigator.webdriver` should be `undefined`; UA should show no "HeadlessChrome" |
| getpass hides CVV input in a real terminal | SEC-02 | TTY behavior not assertable in pytest | Run the bot interactively; confirm CVV input is not echoed and does not appear in `logs/` |
| Package legitimacy (nodriver, pydantic-settings) | INFRA-01 | slopcheck blocked; PyPI page review is human judgment | Blocking human-verify checkpoint in plan 04 |

*Source-assertion tasks (plan 05) use `open(file).read()` substring + ast.parse checks because the behavior lives in an entrypoint that needs a real browser to run end-to-end.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-02
