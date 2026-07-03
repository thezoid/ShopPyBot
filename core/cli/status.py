"""handle_status: CLI status subcommand handler.

Imports only json and BotService -- never core.registry (MOD-02, no network).
This handler reads svc.get_status() only (in-process BotService state).

Limitation: invoking `shoppybot status` in a separate process from the running
bot shows running=False because BotService is instantiated fresh in main().
For the live running-process state use the web /status endpoint instead
(Pattern 8 from Phase 24 research).
"""

import json

from core.service import BotService


def _format_status_table(status: dict) -> str:
    """Return a left-justified aligned text table for plugin health status.

    Renders a running/uptime header then a per-plugin table. Returns a
    no-data fallback when the plugins dict is empty.
    """
    running = status.get("running", False)
    uptime = status.get("uptime_secs", 0.0)
    plugins = status.get("plugins", {})
    header = f"running={running}  uptime={uptime:.1f}s"
    if not plugins:
        return f"{header}\nNo plugin data yet."
    col_headers = ("Name", "Status", "Last Heartbeat", "Errors", "Checked", "Orders")
    data = [
        (
            name,
            rec.get("status", "idle"),
            (f"{rec['heartbeat_age_secs']}s ago" if rec.get("heartbeat_age_secs") is not None else "never"),
            str(rec.get("consecutive_errors", 0)),
            str(rec.get("items_checked", 0)),
            str(rec.get("orders_confirmed", 0)),
        )
        for name, rec in plugins.items()
    ]
    widths = [
        max(len(h), max(len(row[i]) for row in data))
        for i, h in enumerate(col_headers)
    ]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    lines = [header, fmt.format(*col_headers), "  ".join("-" * w for w in widths)]
    for row in data:
        lines.append(fmt.format(*row))
    return "\n".join(lines)


def handle_status(args, svc: BotService) -> int:
    """Print per-plugin health status as table or JSON."""
    status = svc.get_status()
    if getattr(args, "json", False):
        print(json.dumps(status, indent=2))
    else:
        print(_format_status_table(status))
    return 0
