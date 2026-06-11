"""handle_run: CLI run handler (CLI-01).

Collects CVV only when needed (bestbuy auto_buy in non-test_mode),
then delegates to BotService.run(cvv). No bot logic lives here.
"""

import sys
import getpass


def handle_run(args, svc) -> int:
    """Start the bot (blocking). Collects CVV when the gate condition is met.

    CVV gate mirrors main.py:main() logic (SEC-02):
    - Only fires when test_mode is False AND at least one bestbuy.com item
      has auto_buy enabled.
    - getpass is used so the CVV is never echoed (T-09-01).
    - EOFError/GetPassWarning (non-interactive stdin) returns 1 (T-09-02).
    """
    cfg = svc.get_config()
    if getattr(args, "monitor_only", False):
        # WR-02: mutates the config instance in-place. This works because
        # svc.get_config() returns the live internal reference, so svc.run()
        # sees the mutation via the same object. If BotService.get_config()
        # is ever changed to return a defensive copy, this mutation would be
        # silently dropped; the correct fix would be to pass monitor_only as
        # a parameter to svc.run() instead.
        cfg.debug.monitor_only = True
    needs_cvv = (
        not cfg.debug.test_mode
        and not cfg.debug.monitor_only
        and any(
            "bestbuy.com" in item.link and item.auto_buy
            for item in cfg.available.items
        )
    )
    cvv = None
    if needs_cvv:
        try:
            cvv = getpass.getpass("Enter CVV (input hidden): ").strip() or None
        except (EOFError, getpass.GetPassWarning):
            print(
                "WARNING: CVV echo suppression unavailable in this terminal",
                file=sys.stderr,
            )
            return 1
    svc.run(cvv)
    return 0
