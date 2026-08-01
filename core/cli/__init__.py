"""core/cli: argparse parser and set_defaults(func=...) dispatch for shoppybot CLI.

build_parser() returns the fully-wired ArgumentParser. main() (in core/service.py)
calls build_parser() + parse_known_args() then dispatches via args.func.
"""

import argparse
import sys

from core.cli.run import handle_run
from core.cli.setup import handle_setup, handle_setup_checkout_profile
from core.cli.items import handle_items_list, handle_items_add, handle_items_remove, handle_items_price_history
from core.cli.config_cmd import handle_config_show, handle_config_set
from core.cli.web import handle_web
from core.cli.plugins import handle_plugins_list
from core.cli.status import handle_status


def build_parser() -> argparse.ArgumentParser:
    """Return the ArgumentParser for the shoppybot CLI.

    Top-level --migrate is kept as a back-compat alias for 'setup --migrate'
    (RESEARCH Pattern 2 / Pitfall 2). Bare invocation (no subcommand) leaves
    args.func as None; core/service.py:main() treats that as 'run'.
    """
    parser = argparse.ArgumentParser(
        prog="shoppybot",
        description="ShopPyBot: automated availability checker and buyer.",
    )
    parser.set_defaults(func=None)
    # Back-compat alias: top-level --migrate -> setup --migrate (T-09-03)
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Import env-var secrets into the active backend (alias for 'setup --migrate').",
    )

    sub = parser.add_subparsers(dest="command")

    # --- run ---
    run_p = sub.add_parser("run", help="Start the bot (default).")
    run_p.set_defaults(func=handle_run)
    run_p.add_argument(
        "--monitor-only",
        action="store_true",
        default=False,
        dest="monitor_only",
        help="Run in monitor-only mode: check availability and alert but never place orders.",
    )

    # --- setup ---
    setup_p = sub.add_parser("setup", help="Store credentials and select backend.")
    setup_p.add_argument(
        "--migrate",
        action="store_true",
        help="Import env-var secrets into the active backend.",
    )
    setup_p.add_argument(
        "--checkout-profile",
        action="store_true",
        default=False,
        dest="checkout_profile",
        help="Configure shipping/billing address profile (9 address keys; no card/CVV).",
    )
    setup_p.set_defaults(func=handle_setup)

    # BUY-07 criterion 1: accept `shoppybot setup checkout-profile` (sub-action form).
    # The --checkout-profile flag above continues to work (both forms are valid).
    setup_sub = setup_p.add_subparsers(dest="setup_command")
    cp_p = setup_sub.add_parser(
        "checkout-profile",
        help="Configure shipping/billing address profile (9 address keys; no card/CVV).",
    )
    cp_p.set_defaults(func=handle_setup_checkout_profile)

    def _require_subcommand(parent_parser):
        """Return a func handler that prints parent usage and exits 2.

        Used as the set_defaults(func=...) value on group parsers (items, config)
        so that invoking the group name without a leaf subcommand exits with a
        usage error instead of falling through to the bare-run default (WR-06).
        """
        def _handler(args, svc):  # noqa: ARG001
            parent_parser.print_help(sys.stderr)
            return 2
        return _handler

    # --- items ---
    items_p = sub.add_parser("items", help="Manage tracked items.")
    items_sub = items_p.add_subparsers(dest="items_command")

    list_p = items_sub.add_parser("list", help="List all tracked items.")
    list_p.set_defaults(func=handle_items_list)

    add_p = items_sub.add_parser("add", help="Add an item to track.")
    add_p.add_argument("--name", required=True, help="Display name for the item.")
    add_p.add_argument("--url", required=True, help="Product URL.")
    add_p.add_argument(
        "--auto-buy",
        action="store_true",
        default=False,
        help="Enable auto-buy when available.",
    )
    add_p.add_argument(
        "--quantity",
        type=int,
        default=1,
        help="Quantity to purchase (default: 1).",
    )
    add_p.set_defaults(func=handle_items_add)

    remove_p = items_sub.add_parser("remove", help="Remove a tracked item by URL.")
    remove_p.add_argument("--url", required=True, help="Product URL to remove.")
    remove_p.set_defaults(func=handle_items_remove)

    ph_p = items_sub.add_parser("price-history", help="Show recorded price history for an item.")
    ph_p.add_argument("name", help="Item name.")
    ph_p.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of recent prices to show (default: 10).",
    )
    ph_p.set_defaults(func=handle_items_price_history)

    # Bare `shoppybot items` (no leaf) must print usage and exit 2, not start the bot.
    items_p.set_defaults(func=_require_subcommand(items_p))

    # --- config ---
    config_p = sub.add_parser("config", help="View or update bot settings.")
    config_sub = config_p.add_subparsers(dest="config_command")

    show_p = config_sub.add_parser("show", help="Print the current effective config.")
    show_p.set_defaults(func=handle_config_show)

    set_p = config_sub.add_parser(
        "set",
        help="Update an allowlisted config key.",
        description=(
            "Update an allowlisted config key in config.yml. "
            "Note: comments and custom formatting in config.yml are not preserved "
            "after a 'config set' -- the file is rewritten with standard YAML formatting."
        ),
    )
    set_p.add_argument("key", help="Config key (test_mode, logging_level).")
    set_p.add_argument("value", help="New value.")
    set_p.set_defaults(func=handle_config_set)

    # Bare `shoppybot config` (no leaf) must print usage and exit 2, not start the bot.
    config_p.set_defaults(func=_require_subcommand(config_p))

    # --- plugins ---
    plugins_p = sub.add_parser("plugins", help="Inspect locally loaded plugins.")
    plugins_sub = plugins_p.add_subparsers(dest="plugins_command")

    plugins_list_p = plugins_sub.add_parser("list", help="List all loaded plugins.")
    plugins_list_p.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Emit output as JSON instead of a text table.",
    )
    plugins_list_p.set_defaults(func=handle_plugins_list)

    # Bare `shoppybot plugins` (no leaf) must print usage and exit 2, not start the bot.
    plugins_p.set_defaults(func=_require_subcommand(plugins_p))

    # --- status ---
    status_p = sub.add_parser(
        "status",
        help=(
            "Show per-plugin health status (in-process state; "
            "use /status endpoint for the live running process)."
        ),
    )
    status_p.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Emit output as JSON instead of a text table.",
    )
    status_p.set_defaults(func=handle_status)

    # --- web ---
    web_p = sub.add_parser(
        "web", help="Start the web UI (requires pip install .[web])."
    )
    web_p.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address (default 127.0.0.1; non-local prints a security warning).",
    )
    web_p.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Bind port (default 8000; if busy, the next free port is used).",
    )
    web_p.add_argument(
        "--open",
        dest="open_browser",
        action="store_true",
        help="Open the dashboard in the default browser once the server starts.",
    )
    web_p.set_defaults(func=handle_web)

    return parser
