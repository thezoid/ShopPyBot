"""Tests for core/paths.py (XPLAT-01, PKG-06).

Covers: OS-appropriate resolution, SHOPBOT_DATA_DIR env override (per-call),
a no-hardcoded-separator guard across core/ + logger.py + models.py + utils.py,
and the bundled_plugins_dir() seam (behavior preservation, override
independence, contents, and a no-inline-path guard).
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
    repo_root = Path(__file__).parent.parent
    src_files = (
        list((repo_root / "core").rglob("*.py"))
        + list((repo_root / "web").rglob("*.py"))
        + [
            repo_root / "logger.py",
            repo_root / "models.py",
            repo_root / "utils.py",
        ]
    )
    # Non-empty guard: fails loudly if anchor is wrong and yields zero files.
    assert len(src_files) > 0, "separator guard scanned zero files -- check __file__ anchor"
    # Optional coverage check: a known file must be present.
    assert repo_root / "core" / "paths.py" in src_files, (
        "core/paths.py missing from scanned set -- rglob anchor may be wrong"
    )
    bad_patterns = ['"data/', "'data/", '"logs/', "'logs/"]
    violations = []
    for f in src_files:
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if any(pat in line for pat in bad_patterns):
                violations.append(f"{f}:{i}: {line.strip()}")
    assert violations == [], "Hardcoded path separators found:\n" + "\n".join(violations)


# ---------------------------------------------------------------------------
# bundled_plugins_dir() -- PKG-06, the named seam Phase 43 (EXT-03) builds on
# ---------------------------------------------------------------------------


def test_bundled_plugins_dir_preserves_inline_expression():
    """The accessor returns exactly what the removed inline expression returned.

    Prior to PKG-06 the bundled root was computed twice as a bare expression:
    `Path(__file__).parent.parent / "plugins"` in core/orchestrator.py and in
    core/service.py. Both are anchored on a module inside core/, so this test
    reconstructs that expression from the real prior source files rather than
    from a hardcoded path, making it a byte-for-byte refactor proof.
    """
    import core.orchestrator
    import core.service
    from core.paths import bundled_plugins_dir

    expected_from_orchestrator = Path(core.orchestrator.__file__).parent.parent / "plugins"
    expected_from_service = Path(core.service.__file__).parent.parent / "plugins"

    assert bundled_plugins_dir() == expected_from_orchestrator
    assert bundled_plugins_dir() == expected_from_service


def test_bundled_plugins_dir_ignores_repo_root_override(monkeypatch, tmp_path):
    """_REPO_ROOT_OVERRIDE cannot move the bundled plugin root (T-37-10).

    The override relocates the legacy *data* root for tests. Every .py file
    under the bundled root is exec_module'd by core.registry._discover_plugins,
    so a monkeypatchable module global must not be able to redirect it.
    """
    import core.paths
    from core.paths import bundled_plugins_dir, data_dir

    before = bundled_plugins_dir()
    data_dir_before = data_dir()

    monkeypatch.setattr(core.paths, "_REPO_ROOT_OVERRIDE", tmp_path)

    assert core.paths._repo_root() == tmp_path, "override did not take effect -- test is vacuous"
    assert bundled_plugins_dir() == before, (
        f"repo-root override moved the bundled plugin root: {bundled_plugins_dir()} != {before}"
    )
    assert tmp_path not in bundled_plugins_dir().parents
    assert data_dir() == data_dir_before, "override must not disturb data_dir() either"


def test_bundled_plugins_dir_contains_seven_plugins():
    """The returned directory exists and holds exactly the 7 bundled plugins."""
    from core.paths import bundled_plugins_dir

    d = bundled_plugins_dir()
    assert d.is_dir(), f"bundled plugin root does not exist: {d}"

    found = sorted(p.name for p in d.glob("shopbot_plugin_*.py"))
    assert len(found) == 7, f"expected 7 bundled plugins, found {len(found)}: {found}"
    assert found == [
        "shopbot_plugin_amazon.py",
        "shopbot_plugin_bestbuy.py",
        "shopbot_plugin_gamestop.py",
        "shopbot_plugin_newegg.py",
        "shopbot_plugin_squareenix.py",
        "shopbot_plugin_target.py",
        "shopbot_plugin_walmart.py",
    ]


def test_no_production_module_computes_a_plugin_path():
    """Only core/paths.py may compute a bundled plugin path (Phase 43 criterion 5).

    Mirrors the scanning style of test_no_hardcoded_separators. Flags any
    production line that both walks up with parent.parent and names the plugins
    directory, which is the inline expression this seam replaced.
    """
    repo_root = Path(__file__).parent.parent
    paths_module = repo_root / "core" / "paths.py"
    src_files = [
        f
        for f in (
            list((repo_root / "core").rglob("*.py"))
            + list((repo_root / "web").rglob("*.py"))
            + [
                repo_root / "logger.py",
                repo_root / "models.py",
                repo_root / "utils.py",
                repo_root / "main.py",
            ]
        )
        if f != paths_module
    ]
    # Non-empty guard: fails loudly if the anchor is wrong and yields zero files.
    assert len(src_files) > 0, "plugin-path guard scanned zero files -- check __file__ anchor"
    # Coverage check: the two files this seam was extracted from must be scanned.
    assert repo_root / "core" / "orchestrator.py" in src_files, (
        "core/orchestrator.py missing from scanned set -- rglob anchor may be wrong"
    )
    assert repo_root / "core" / "service.py" in src_files, (
        "core/service.py missing from scanned set -- rglob anchor may be wrong"
    )
    assert paths_module not in src_files, "core/paths.py must be excluded, it owns the seam"

    violations = []
    for f in src_files:
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            names_plugins = '"plugins"' in line or "'plugins'" in line
            if "parent.parent" in line and names_plugins:
                violations.append(f"{f}:{i}: {line.strip()}")
    assert violations == [], (
        "Bundled plugin path computed outside core/paths.py -- "
        "call core.paths.bundled_plugins_dir() instead:\n" + "\n".join(violations)
    )
