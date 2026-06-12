"""REL-04: CI guard -- no committed session files + sessions dir gitignored.

Asserts that:
- No data/sessions/*.bin session file is tracked by git (T-23-07)
- data/sessions/ is covered by .gitignore via the existing data/* rule (T-23-08)

Tests skip (not fail) when git is unavailable or .gitignore is absent, so the
suite stays green in non-git environments.
"""

import subprocess
from pathlib import Path

import pytest


def test_no_committed_session_files():
    """No data/sessions/*.bin file is git-tracked."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "data/sessions/"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        pytest.skip("git not available in this environment")

    if result.returncode != 0:
        # git failed (e.g. not a repo); skip rather than silently pass
        pytest.skip(f"git ls-files exited {result.returncode}: {result.stderr.strip()}")

    # Empty stdout from a successful git call means no tracked files -- that is correct.
    # Match ANY file under data/sessions/ (not only .bin): orphaned .tmp files from a
    # crashed mkstemp write would also not be gitignored and must be caught.
    tracked = [line for line in result.stdout.splitlines() if line.strip()]
    assert tracked == [], (
        f"Session files are git-tracked (must never be committed): {tracked}"
    )


def test_sessions_dir_gitignored():
    """data/sessions/ is covered by .gitignore.

    The existing 'data/*' rule on line 8 of .gitignore covers data/sessions/.
    A future reordering that removes this rule would break REL-04 silently
    without this assertion.
    """
    gitignore_path = Path(".gitignore")
    if not gitignore_path.exists():
        pytest.skip(".gitignore not present in this environment")

    content = gitignore_path.read_text()
    # data/* is the source of coverage for data/sessions/; accept data/sessions as fallback
    assert "data/*" in content or "data/sessions" in content, (
        "Neither 'data/*' nor 'data/sessions' found in .gitignore -- "
        "data/sessions/ is not gitignored; encrypted session files would leak into commits"
    )
