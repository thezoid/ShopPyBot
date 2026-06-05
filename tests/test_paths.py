"""Tests for core/paths.py (XPLAT-01).

Covers: OS-appropriate resolution, SHOPBOT_DATA_DIR env override (per-call),
and a no-hardcoded-separator guard across core/ + logger.py + models.py + utils.py.
"""

from pathlib import Path


def test_data_dir_is_absolute(monkeypatch):
    """data_dir() returns an absolute Path when SHOPBOT_DATA_DIR is not set."""
    monkeypatch.delenv("SHOPBOT_DATA_DIR", raising=False)
    from core.paths import data_dir

    result = data_dir()
    assert isinstance(result, Path)
    assert result.is_absolute()


def test_config_path_under_data_dir(monkeypatch):
    """config_path() == data_dir() / 'config.yml'."""
    monkeypatch.delenv("SHOPBOT_DATA_DIR", raising=False)
    from core.paths import config_path, data_dir

    assert config_path() == data_dir() / "config.yml"


def test_log_dir_is_absolute(monkeypatch):
    """log_dir() returns an absolute Path when SHOPBOT_DATA_DIR is not set."""
    monkeypatch.delenv("SHOPBOT_DATA_DIR", raising=False)
    from core.paths import log_dir

    result = log_dir()
    assert isinstance(result, Path)
    assert result.is_absolute()


def test_env_override(monkeypatch, tmp_path):
    """SHOPBOT_DATA_DIR overrides data_dir(); re-read on every call (not cached at import)."""
    override = tmp_path / "override"
    monkeypatch.setenv("SHOPBOT_DATA_DIR", str(override))
    from core.paths import data_dir

    assert data_dir() == override


def test_log_dir_env_override(monkeypatch, tmp_path):
    """With SHOPBOT_DATA_DIR set, log_dir() == override / 'logs'."""
    override = tmp_path / "mydata"
    monkeypatch.setenv("SHOPBOT_DATA_DIR", str(override))
    from core.paths import log_dir

    assert log_dir() == override / "logs"


def test_no_hardcoded_separators():
    """No source file in core/, logger.py, models.py, utils.py uses bare string path separators."""
    src_files = list(Path("core").rglob("*.py")) + [
        Path("logger.py"),
        Path("models.py"),
        Path("utils.py"),
    ]
    bad_patterns = ['"data/', "'data/", '"logs/', "'logs/"]
    violations = []
    for f in src_files:
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if any(pat in line for pat in bad_patterns):
                violations.append(f"{f}:{i}: {line.strip()}")
    assert violations == [], "Hardcoded path separators found:\n" + "\n".join(violations)
