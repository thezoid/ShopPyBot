---
phase: 1
slug: foundations-security
asvs_level: 1
threats_total: 16
threats_closed: 16
threats_open: 0
status: secured
register_authored_at_plan_time: true
audited: 2026-06-02
---

# Phase 1 — Foundations + Security Audit

**Audit Date:** 2026-06-02
**ASVS Level:** 1
**Auditor:** gsd-security-auditor (gsd-secure-phase)
**Threats Total:** 16 | **Closed:** 16 | **Open:** 0

---

## Threat Verification Table

| Threat ID | Category | Component | Disposition | Status | Evidence |
|-----------|----------|-----------|-------------|--------|----------|
| T-01-01 | Tampering | test_make_tiny live network | mitigate | CLOSED | tests/test_utils.py:17 — `monkeypatch.setattr(main_module.requests, "get", lambda url: mock_response)`; offline deterministic |
| T-01-02 | Info Disclosure | test fixtures writing config | accept | CLOSED | tests/conftest.py:8-16 — fixture writes only synthetic non-secret data (debug, available, platforms) to tmp_path; no credential fields present |
| T-01-ABC | Tampering | RetailerPlugin contract | mitigate | CLOSED | core/plugin_base.py:13,19 — `@abstractmethod` on `check_availability` and `auto_buy`; instantiation of non-concrete subclass raises `TypeError` |
| T-01-VER | Spoofing | PLUGIN_API_VERSION | mitigate | CLOSED | core/plugin_base.py:3 — `PLUGIN_API_VERSION = 1` at module level, before class body; not a class attribute |
| T-01-CFG | Tampering/DoS | config.yml malformed input | mitigate | CLOSED | core/config_schema.py:63-114; main.py:56-60 — `AppConfig()` in try/except `ValidationError`; prints field path, raises `SystemExit(1)` |
| T-01-CRED | Info Disclosure | credentials in config.yml | mitigate | CLOSED | core/config_schema.py:18-20,86-100 — no credential fields on any model; `warn_legacy_keys` emits `DeprecationWarning` on legacy keys; env_settings takes precedence |
| T-01-CFGPATH | Spoofing | CWD-relative yaml load | mitigate | CLOSED | core/config_schema.py:16 — `_DEFAULT_YAML_PATH = Path(__file__).parent.parent / "config.yml"` (absolute); config_schema.py:113 — `getattr(_yaml_path_local, "active", _DEFAULT_YAML_PATH)` — no silent default-fallthrough; CR-03 threading.local fix applied |
| T-01-SC | Tampering | nodriver/pydantic-settings supply chain | mitigate | CLOSED | requirements.txt:1-12 — all 12 packages pinned with `==`; no floating versions; `nodriver==0.50.3`, `pydantic-settings[yaml]==2.14.0` |
| T-01-LOG | Info Disclosure | per-call config.yml read in loop | mitigate | CLOSED | logger.py:10,20 — `_CONFIG_PATH` resolved at module level; `_LOGGING_LEVEL` loaded once via `_load_logging_level()` at import time; `writeLog` reads only `_LOGGING_LEVEL` (line 27), no file I/O per call |
| T-01-LOGERR | Tampering | logger swallowing config errors | mitigate | CLOSED | logger.py:17 — `except (FileNotFoundError, KeyError, TypeError):` — specific exception types only; no bare `except:` |
| T-01-WD | Spoofing | navigator.webdriver leak | mitigate | CLOSED | main.py:103-106 — `driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"})` before first `driver.get()` |
| T-01-DWS | Spoofing | --disable-web-security fingerprint | mitigate | CLOSED | main.py:76 — comment confirms removal; grep of `--disable-web-security` finds only the removal comment, no active flag; real UA set at main.py:78-82 |
| T-01-CVV | Info Disclosure | CVV on disk/in logs | mitigate | CLOSED | main.py:40-49 — `collect_cvv()` uses `getpass.getpass`; raises `SystemExit` on `GetPassWarning` or empty; main.py:125-129 — WR-02 fix: `needs_bb_autobuy` requires `not test_mode` as first condition; CVV never passed to `writeLog` |
| T-01-ENV | Info Disclosure | credentials in config.yml | mitigate | CLOSED | main.py:171-172 — `os.environ.get("BB_EMAIL")`, `os.environ.get("BB_PASSWORD")`; sample.config.yml has no credential fields (verified: no `app:` key, no email/password values); .env.example:6-9 documents all four env vars |
| T-01-STDERR | Tampering | sys.stdout devnull hiding exceptions | mitigate | CLOSED | main.py:96 — `Service(driver_path, log_output=subprocess.DEVNULL)`; grep of `sys.stdout =` in main.py returns no matches |
| T-01-LOGLEAK | Info Disclosure | credential/CVV passed to writeLog | mitigate | CLOSED | main.py: no `writeLog` call includes `email`, `password`, or `cvv` variable as argument; amazon_bot.py:85,97 — logs exception object `{e}`, not the credential variable; bestbuy_bot.py: no credential/CVV in any writeLog call |

---

## Accepted Risks Log

| Threat ID | Rationale |
|-----------|-----------|
| T-01-02 | test fixtures write only synthetic config (no secrets, no real credentials); tmp_path is ephemeral; accepted by design |

---

## Unregistered Flags

None. No new attack surface detected during this audit beyond the registered threat register.

---

## Pre-existing Deferred Issues (not Phase 1 scope)

These were identified in code review and explicitly deferred. They are not open threats against the Phase 1 register.

| Item | File | Description | Deferred To |
|------|------|-------------|-------------|
| CR-01 | main.py:34 | `make_tiny` uses plaintext HTTP to tinyurl.com | Phase 2 / backlog |
| CR-04 | models.py:4 | No `os.makedirs` guard before `sqlite3.connect`; crashes on fresh clone without `data/` | Phase 2 / backlog |
| WR-01 | main.py | `make_tiny` has no error handling on network failure | Phase 2 / backlog |
| WR-03 | bestbuy_bot.py | Silent exception swallowing in auto-buy flow | Phase 2 / backlog |

---

_Generated by gsd-secure-phase audit. Implementation files were read-only during this audit._
