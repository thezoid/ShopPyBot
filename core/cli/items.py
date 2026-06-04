"""handle_items_*: CLI items subcommand handlers.

Imports only sys and BotService -- never models/orchestrator/registry (MOD-02).
"""

import sys

from core.service import BotService


def _format_items_table(rows: list) -> str:
    """Return a left-justified aligned text table for the given item rows.

    Each row is a 5-tuple: (name, link, auto_buy, quantity, purchased).
    Returns a no-items message when rows is empty.
    """
    headers = ("Name", "URL", "Auto-Buy", "Qty", "Purchased")
    if not rows:
        return "No items tracked."
    widths = [
        max(len(h), max(len(str(r[i])) for r in rows))
        for i, h in enumerate(headers)
    ]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    lines = [fmt.format(*headers), "  ".join("-" * w for w in widths)]
    for r in rows:
        lines.append(fmt.format(r[0], r[1], bool(r[2]), r[3], bool(r[4])))
    return "\n".join(lines)


def handle_items_list(args, svc: BotService) -> int:
    """Print a text table of all tracked items."""
    print(_format_items_table(svc.list_items()))
    return 0


def handle_items_add(args, svc: BotService) -> int:
    """Add an item via BotService.add_item."""
    svc.add_item(args.name, args.url, args.auto_buy, args.quantity)
    print(f"Added: {args.name}")
    return 0


def handle_items_remove(args, svc: BotService) -> int:
    """Remove an item by URL via BotService.remove_item.

    Looks up the item name before deletion and exits 1 when the URL is not found.
    """
    rows = svc.list_items()
    match = next((r for r in rows if r[1] == args.url), None)
    if match is None:
        print(f"No item found with URL: {args.url}", file=sys.stderr)
        return 1
    svc.remove_item(args.url)
    print(f"Removed: {match[0]}")
    return 0
