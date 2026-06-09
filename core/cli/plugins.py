"""handle_plugins_list: CLI plugins subcommand handler.

Imports only json and BotService -- never core.registry (MOD-02).
"""

import json

from core.service import BotService


def _format_plugins_table(rows: list) -> str:
    """Return a left-justified aligned text table for the given plugin rows.

    Each row is a dict with keys: name, domain_patterns, difficulty,
    requires_proxy, requires_captcha.
    Returns a no-plugins message when rows is empty.
    """
    if not rows:
        return "No plugins loaded."

    headers = ("Name", "Domain Patterns", "Difficulty", "Proxy", "CAPTCHA")
    data = [
        (
            r["name"],
            ", ".join(
                [r["domain_patterns"]]
                if isinstance(r["domain_patterns"], str)
                else list(r["domain_patterns"] or [])
            ),
            r["difficulty"],
            str(r["requires_proxy"]),
            str(r["requires_captcha"]),
        )
        for r in rows
    ]
    widths = [
        max(len(h), max(len(row[i]) for row in data))
        for i, h in enumerate(headers)
    ]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    lines = [fmt.format(*headers), "  ".join("-" * w for w in widths)]
    for row in data:
        lines.append(fmt.format(*row))
    return "\n".join(lines)


def handle_plugins_list(args, svc: BotService) -> int:
    """Print loaded plugins as a table or JSON."""
    rows = svc.list_plugins()
    if getattr(args, "json", False):
        print(json.dumps(rows, indent=2))
    else:
        print(_format_plugins_table(rows))
    return 0
