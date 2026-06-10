---
phase: 16-price-monitoring
plan: "04"
subsystem: cli
tags: [price-monitoring, cli, items, price-history, tdd]

dependency_graph:
  requires:
    - phase: 16-price-monitoring
      plan: "03"
      provides: BotService.get_price_history(name, limit)
  provides:
    - handle_items_price_history + _format_price_history_table in core/cli/items.py
    - price-history subparser leaf under items_sub (name + --limit, default 10)
    - PRICE-06: shoppybot items price-history <name> CLI command
  affects:
    - core/cli/items.py
    - core/cli/__init__.py
    - tests/test_cli_price_history.py

tech_stack:
  added: []
  patterns:
    - "Clone _format_items_table width-alignment pattern for price history table"
    - "price_cents -> $X.XX via f'${r[0] / 100:.2f}'"
    - "handler(args, svc) -> int contract mirroring all other items handlers"
    - "MOD-02: core/cli/items.py imports only sys + BotService"

key_files:
  created:
    - tests/test_cli_price_history.py
  modified:
    - core/cli/items.py
    - core/cli/__init__.py

decisions:
  - "Case-sensitive name matching consistent with existing items commands; no-history message covers a miss (Pitfall 8)"
  - "limit is argparse type=int; no additional validation needed in handler (T-16-CLI-SQLI boundary at BotService)"
  - "_format_price_history_table is a standalone private helper; no shared formatter module (single use-case)"

metrics:
  duration: 5min
  completed: 2026-06-10
  tasks: 3
  files: 3
---

# Phase 16 Plan 04: CLI price-history Leaf Summary

`shoppybot items price-history <name>` delivered: left-aligned $X.XX table via `BotService.get_price_history`, `--limit N` (default 10), no-history fallback message, no network call; PRICE-06 closed.

## Performance

- **Duration:** ~5 min
- **Started:** 2026-06-10T00:07:54Z
- **Completed:** 2026-06-10T00:12:33Z
- **Tasks:** 3 (RED + GREEN handler/formatter + GREEN subparser wiring)
- **Files modified:** 3

## Accomplishments

- `tests/test_cli_price_history.py`: 4 RED tests committed first (TDD gate); covers stdout table content, no-item message, --limit dispatch, no network side-effects
- `core/cli/items.py`: `_format_price_history_table(name, rows)` left-aligned with width-computed columns (Price/Currency/Recorded At); formats price_cents as `$X.XX`; empty rows returns `"No price history recorded for: {name}"`. `handle_items_price_history(args, svc) -> int` delegates to formatter + `svc.get_price_history(args.name, args.limit)`; MOD-02 boundary preserved
- `core/cli/__init__.py`: `handle_items_price_history` added to import line; `ph_p = items_sub.add_parser("price-history", ...)` with positional `name` and `--limit type=int default=10`; `set_defaults(func=handle_items_price_history)` dispatch wired
- Full suite: 522 passed, 2 skipped (up from 518; 4 new tests)

## Task Commits

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 (RED) | Failing CLI price-history tests | `45e26c5` | tests/test_cli_price_history.py |
| 2 (GREEN) | Handler + table formatter | `b71f29b` | core/cli/items.py |
| 3 (GREEN) | Wire price-history subparser leaf | `1a28db7` | core/cli/__init__.py |

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None. Handler is fully wired to BotService.get_price_history; formatter produces real output.

## Threat Surface Scan

No new trust boundaries beyond those in the plan's threat register. Mitigations applied:

| Threat | Mitigation Applied |
|--------|-------------------|
| T-16-CLI-SQLI | limit is argparse type=int; name/limit passed to BotService.get_price_history which uses Plan-01 parameterized queries |
| T-16-CLI-NET | Read-only, no network; test_cli_price_history_no_network asserts run/start not called |
| T-16-SC | No packages installed this phase |

## TDD Gate Compliance

- RED gate: `test(16-04)` commit `45e26c5` present
- GREEN gate: `feat(16-04)` commits `b71f29b` and `1a28db7` present after RED

## Self-Check: PASSED

- `core/cli/items.py` contains `handle_items_price_history`: FOUND
- `core/cli/items.py` contains `_format_price_history_table`: FOUND
- `core/cli/__init__.py` contains `price-history`: FOUND
- `tests/test_cli_price_history.py` exists: FOUND
- Commit `45e26c5` (RED): FOUND
- Commit `b71f29b` (Task 2): FOUND
- Commit `1a28db7` (Task 3): FOUND
- 522 passed, 2 skipped: VERIFIED
