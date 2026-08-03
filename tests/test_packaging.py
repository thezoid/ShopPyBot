"""In-tree packaging guards for PKG-01 (data files must ship with the wheel).

Covers:
  - utils.SOUNDS_DIR resolves to a real directory (PKG-01)
  - that directory holds notification, available, and buy as .wav or .mp3 (PKG-01)
  - the resolved path really is the core/sounds package, not a stale repo-relative path
  - the six web/static and web/templates data files exist under the web package (PKG-01)

These assertions are the in-tree half. They prove the data files exist where the
code looks for them, so a future refactor cannot quietly move or delete them. The
wheel-content half (proving those same files are packaged) lands as a CI job in
plan 37-04.
"""

import os
from pathlib import Path

import utils
import web

SOUND_NAMES = ("notification", "available", "buy")
SOUND_SUFFIXES = (".wav", ".mp3")

# Every non-Python file create_app() serves. StaticFiles mounts web/static and the
# Jinja2 loader reads web/templates; both are resolved relative to the web package.
WEB_DATA_FILES = (
    "static/components.css",
    "static/dashboard.css",
    "static/tokens.css",
    "static/vendor/uplot.iife.min.js",
    "static/vendor/uplot.min.css",
    "templates/dashboard.html",
)


def test_sounds_dir_exists():
    """utils.SOUNDS_DIR must point at a real directory."""
    assert os.path.isdir(utils.SOUNDS_DIR), (
        f"SOUNDS_DIR does not exist or is not a directory: {utils.SOUNDS_DIR}"
    )


def test_sounds_dir_is_the_core_sounds_package():
    """SOUNDS_DIR must resolve inside core/sounds, not a repo-relative sounds/ dir."""
    parts = Path(utils.SOUNDS_DIR).resolve().parts
    assert parts[-2:] == ("core", "sounds"), (
        f"SOUNDS_DIR should end with core/sounds, got: {utils.SOUNDS_DIR}"
    )


def test_sounds_dir_holds_every_alert_sound():
    """Each alert name resolves to a playable file utils.play_sound would find."""
    present = set(os.listdir(utils.SOUNDS_DIR))
    for name in SOUND_NAMES:
        candidates = {f"{name}{suffix}" for suffix in SOUND_SUFFIXES}
        assert candidates & present, (
            f"no {name}.mp3 or {name}.wav in {utils.SOUNDS_DIR}; found: {sorted(present)}"
        )


def test_web_data_files_exist_under_the_web_package():
    """All six static/template files must live inside the web package directory."""
    web_dir = Path(web.__file__).parent
    missing = [rel for rel in WEB_DATA_FILES if not (web_dir / rel).is_file()]
    assert not missing, f"missing web data files under {web_dir}: {missing}"
