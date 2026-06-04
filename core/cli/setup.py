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
    """Credential setup wizard. Stub -- plan 09-02 implements the full body."""
    # Stub: return 0 so the CLI dispatch wiring tests pass.
    # plan 09-02 will implement: migrate branch, secret prompts, backend write.
    return 0
