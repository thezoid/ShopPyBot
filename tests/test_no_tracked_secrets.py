"""RH-01: CI guard -- no sensitive path is git-tracked + .gitignore covers them.

Asserts that:
- No config.yml, data/*.db, *creds.bin, or *sessions/*.bin file is tracked by git
- .gitignore covers the sensitive path set (config.yml, data/*)

Fast local complement to the full-history gitleaks CI job (.github/workflows/gitleaks.yml).
Tests skip (not fail) when git is unavailable or .gitignore is absent, so the
suite stays green in non-git environments -- mirrors tests/test_no_committed_sessions.py.
"""

import subprocess
from pathlib import Path

import pytest

# Anchor to repo root regardless of pytest invocation directory (IN-02).
_REPO_ROOT = Path(__file__).resolve().parent.parent

_SENSITIVE_PATH_CHECKS = [
    "config.yml",
    "data/",
    "*.db",
    "*creds.bin",
    "*sessions/*.bin",
]


def test_no_tracked_sensitive_paths():
    """No sensitive path (config.yml, data/*.db, *creds.bin, sessions/*.bin) is git-tracked."""
    try:
        result = subprocess.run(
            ["git", "-C", str(_REPO_ROOT), "ls-files"] + _SENSITIVE_PATH_CHECKS,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        pytest.skip("git not available in this environment")

    if result.returncode != 0:
        # git failed (e.g. not a repo); skip rather than silently pass
        pytest.skip(f"git ls-files exited {result.returncode}: {result.stderr.strip()}")

    tracked = [line for line in result.stdout.splitlines() if line.strip()]
    assert tracked == [], (
        f"Sensitive paths are git-tracked (must never be committed): {tracked}"
    )


def test_gitignore_covers_sensitive_paths():
    """.gitignore covers config.yml and data/* (source of coverage for db + creds + sessions)."""
    gitignore_path = _REPO_ROOT / ".gitignore"
    if not gitignore_path.exists():
        pytest.skip(".gitignore not present in this environment")

    content = gitignore_path.read_text()
    assert "/config.yml" in content or "config.yml" in content, (
        "Neither '/config.yml' nor 'config.yml' found in .gitignore -- "
        "config.yml is not gitignored; a populated config file could leak into commits"
    )
    assert "data/*" in content, (
        "'data/*' not found in .gitignore -- "
        "data/*.db, data/creds.bin, data/sessions/*.bin would not be gitignored"
    )
