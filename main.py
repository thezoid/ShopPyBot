import sys
import asyncio
import getpass
from models import initialize_db, add_items
from pydantic import ValidationError
from core.config_schema import AppConfig
from core.orchestrator import async_main
from logger import setup_logger, writeLog


def collect_cvv():
    """Collect CVV via hidden input at runtime. Never echoes or stores to disk (SEC-02)."""
    try:
        cvv = getpass.getpass("Enter CVV (input hidden): ").strip()
    except getpass.GetPassWarning:
        print("WARNING: CVV echo suppression unavailable in this terminal", file=sys.stderr)
        raise SystemExit("Cannot collect CVV securely. Run in an interactive terminal.")
    if not cvv:
        raise SystemExit("CVV is required for auto-buy. Exiting.")
    return cvv


def main():
    writeLog("Starting main function", "INFO")

    # Validate config at startup; exit cleanly on schema error (CORE-05)
    try:
        cfg = AppConfig()
    except ValidationError as e:
        print(f"Configuration error -- fix config.yml:\n{e}")
        raise SystemExit(1)

    # Initialize the database and add items from config
    initialize_db()
    items = [
        (item.name, item.link, item.auto_buy, item.quantity, False)
        for item in cfg.available.items
    ]
    add_items(items)

    # SEC-01/02: collect BestBuy CVV from getpass BEFORE asyncio.run() (D-03 / Pitfall 6).
    # Only prompt if not in test_mode AND at least one BestBuy item has auto_buy enabled.
    # In test_mode the purchase step is skipped, so blocking on a getpass prompt would
    # break CI and violate the test_mode contract (WR-02).
    needs_bb_autobuy = (
        not cfg.debug.test_mode
        and any("bestbuy.com" in item.link and item.auto_buy for item in cfg.available.items)
    )
    cvv = collect_cvv() if needs_bb_autobuy else None

    asyncio.run(async_main(cfg, cvv))


if __name__ == "__main__":
    logger = setup_logger()
    main()
