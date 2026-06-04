---
phase: 09
slug: cli-front-end
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-04
---

# Phase 09 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x (pytest-asyncio 1.3.0, asyncio_mode=auto) |
| **Config file** | pyproject.toml / pytest.ini (existing) |
| **Quick run command** | `pytest tests/test_cli.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_cli.py -q`
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd:verify-work`:** Full suite green (255 baseline + new CLI tests)
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | CLI-01 | argparse subparser scaffold; bare shoppybot + run both call BotService.start/run; main.py shim unchanged | unit | `pytest tests/test_cli.py -k "run or dispatch or main_shim" -q` | ❌ W0 | ⬜ pending |
| 09-02-01 | 02 | 2 | CLI-02 | setup prompts grouped keys via getpass (no echo), stores via get_store().set, confirms by name; backend written to config; --migrate alias | unit | `pytest tests/test_cli.py -k "setup or migrate" -q` | ❌ W0 | ⬜ pending |
| 09-03-01 | 03 | 3 | CLI-03 | items list/add/remove + config show/set route through BotService/config, never DB directly | unit | `pytest tests/test_cli.py -k "items or config" -q` | ❌ W0 | ⬜ pending |
| 09-03-02 | 03 | 3 | MOD-02 | grep guard: no orchestrator/registry/models calls from CLI modules bypassing BotService | grep | `pytest tests/test_cli_no_bypass.py -q` | ❌ W0 | ⬜ pending |
| 09-04-01 | 04 | 4 | CLI-04 | run/setup/items/config work with fastapi absent (sys.modules['fastapi']=None); web handler lazy-imports + prints install hint | unit | `pytest tests/test_cli_no_fastapi.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs indicative — planner finalizes exact plan/task numbering.*

---

## Wave 0 Requirements

- [ ] `tests/test_cli.py` — stubs for CLI-01/02/03 (argv-injection invocation, BotService mocked)
- [ ] `tests/test_cli_no_fastapi.py` — CLI-04 guard (monkeypatch sys.modules fastapi=None)
- [ ] `tests/test_cli_no_bypass.py` — MOD-02 grep guard for CLI modules
- [ ] `tests/conftest.py` — reuse existing BotService/config fixtures; add argv/capsys helpers as needed

*Existing pytest infrastructure covers framework; only new test files needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `shoppybot setup` interactive flow on Windows PowerShell | CLI-02 | getpass no-echo + interactive prompts can't be fully asserted in CI; piped-stdin path is tested but live terminal behavior is manual | On Windows PowerShell: run `shoppybot setup`, enter a value for one key, confirm no echo and "stored {KEY}" by name only |
| `shoppybot setup` interactive flow on Ubuntu terminal | CLI-02 | Same — live TTY behavior | On Ubuntu: `shoppybot setup`, verify masked entry + name-only confirmation |

*Cross-platform live-terminal checks roll into Phase 11 verification matrix.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
