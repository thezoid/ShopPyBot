"""handle_setup: CLI setup handler stub (plan 09-02 fills the body).

Provides _prompt_secret helper and handle_setup stub returning 0.
"""

import getpass
import sys

from core.credentials import get_store, SECRET_KEYS, migrate_from_env


def _prompt_secret(prompt: str) -> str | None:
    """Return secret string or None if user skips (empty input or EOF).

    Catches EOFError (closed stdin / CI) and GetPassWarning (redirected stdin)
    and treats both as a skip -- same as pressing Enter (RESEARCH Pattern 3).
    """
    try:
        val = getpass.getpass(prompt).strip()
    except (EOFError, getpass.GetPassWarning):
        return None
    return val or None


def handle_setup(args, svc) -> int:
    """Credential setup wizard.

    The --migrate branch is implemented here to preserve back-compat
    (shoppybot --migrate and shoppybot setup --migrate must both work).
    The interactive prompts + backend-write body is filled in plan 09-02.
    """
    if getattr(args, "migrate", False):
        store = get_store()
        migrated = migrate_from_env(store)
        for key in migrated:
            print(f"Migrated: {key}")   # key NAME only -- never the value (T-08-14)
        return 0
    # Stub: interactive prompt body is filled in plan 09-02.
    return 0
