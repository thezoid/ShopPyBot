"""Runtime CVV collection (SEC-02, D-04, D-05).

CVVs are prompted via getpass.getpass at startup, held only in process memory,
and never logged or persisted. Non-TTY launches hard-fail by default; opt-in
env-var path requires SHOPBOT_ALLOW_CVV_ENV=true.
"""
import getpass
import os
import sys


def collect_cvvs(app_config) -> dict[str, str]:
    """Return {platform_name: cvv} for enabled platforms with at least one auto_buy item.

    Called once at startup before the polling loop. No CVV is ever logged.
    """
    needed = [
        name for name, plat in app_config.platforms.items()
        if plat.enabled and any(item.auto_buy for item in app_config.available.items)
    ]
    if not needed:
        return {}

    if not sys.stdin.isatty():
        return _collectFromEnv(needed) if _envOptInEnabled() else _exitNonTty()

    cvvs: dict[str, str] = {}
    for name in needed:
        cvvs[name] = getpass.getpass(f"Enter CVV for {name}: ")
        if not cvvs[name]:
            sys.stderr.write(f"ERROR: empty CVV for {name}; aborting.\n")
            sys.exit(1)
    return cvvs


def _envOptInEnabled() -> bool:
    return os.environ.get("SHOPBOT_ALLOW_CVV_ENV", "").lower() == "true"


def _collectFromEnv(needed: list[str]) -> dict[str, str]:
    cvvs: dict[str, str] = {}
    for name in needed:
        envKey = f"SHOPBOT_{name.upper()}_CVV"
        val = os.environ.get(envKey)
        if not val:
            sys.stderr.write(
                f"ERROR: {envKey} is required because SHOPBOT_ALLOW_CVV_ENV=true and "
                f"stdin is not a TTY. Set the env var or remove auto_buy from "
                f"{name} items.\n"
            )
            sys.exit(1)
        cvvs[name] = val
    return cvvs


def _exitNonTty() -> None:
    sys.stderr.write(
        "ERROR: auto_buy is enabled but stdin is not a TTY (this happens when running "
        "from an IDE Run button or under cron/systemd). Either run interactively, or set "
        "SHOPBOT_ALLOW_CVV_ENV=true and supply SHOPBOT_<PLATFORM>_CVV env vars (visible "
        "in /proc/<pid>/environ: trusted infrastructure only).\n"
    )
    sys.exit(1)
