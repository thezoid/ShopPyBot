#!/usr/bin/env python3
"""Prove a built ShopPyBot wheel is a working ShopPyBot (PKG-05).

Installs the one wheel in --wheel-dir, with the ``web`` extra, into a fresh
virtualenv and runs five assertions in the cheapest-failing-first order locked by
37-CONTEXT.md, so a regression names its own layer: (1) ``shoppybot --help``
exits 0, (2) eight core modules import, (3) the data files ship AND a sound
resolves at runtime, (4) the bundled plugin root holds seven plugins, (5)
``shoppybot web`` actually serves. Standard library only, deliberately: it runs
before anything in the clean environment is trusted and it must behave
identically in CI and on a laptop.

The clean environment gets the wheel and its own declared dependencies, nothing
else. It never reads a pinned dev requirements file and never installs the
project from source with ``-e``; an install that sees either proves nothing,
which is the most important property this script has.
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import venv
import zipfile
from pathlib import Path
from typing import NamedTuple

# Five of these eight were unimportable before Phase 37; one call each names the culprit.
MODULES = (
    "core.service", "core.orchestrator", "core.registry", "core.config_schema",
    "core.captcha", "web", "utils", "models",
)
DATA_PREFIXES = ("web/static/", "web/templates/", "core/sounds/")
EXPECTED_PLUGINS = 7
SOUND_FILE = "notification.wav"
WEB_TIMEOUT = 30.0
POLL_INTERVAL = 0.5
PROBE_TIMEOUT = 120
INSTALL_TIMEOUT = 900

SOUND_PROBE = (
    "import os, sys, utils; d = str(utils.SOUNDS_DIR); print('SOUNDS_DIR=' + d);"
    f"sys.exit(0 if os.path.isfile(os.path.join(d, {SOUND_FILE!r})) else 3)"
)
PLUGIN_PROBE = (
    "from core.paths import bundled_plugins_dir; d = bundled_plugins_dir();"
    "print('PLUGIN_DIR=' + str(d));"
    "print('PLUGIN_COUNT=' + str(len(sorted(d.glob('shopbot_plugin_*.py')))))"
)


class Result(NamedTuple):
    """Outcome of one assertion; `detail` carries captured subprocess output."""
    ok: bool
    message: str
    detail: str = ""


class Probe(NamedTuple):
    """Handles onto the clean environment that every assertion drives."""
    wheel: Path
    venv_dir: Path
    python: Path
    console: Path
    env: dict


def venv_bin(venv_dir: Path, name: str) -> Path:
    """Path to an executable inside a created venv, on either platform."""
    if os.name == "nt":
        return venv_dir / "Scripts" / f"{name}.exe"
    return venv_dir / "bin" / name


def child_env(data_dir: Path) -> dict:
    """Throwaway data dir, null keyring backend (no D-Bus probe on headless Linux),
    the test job's dummy SDL drivers, and no PYTHONPATH leak from the caller."""
    env = dict(os.environ)
    for leaky in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(leaky, None)
    env["SHOPBOT_DATA_DIR"] = str(data_dir)
    env["PYTHON_KEYRING_BACKEND"] = "keyring.backends.null.Keyring"
    env["SDL_AUDIODRIVER"] = "dummy"
    env["SDL_VIDEODRIVER"] = "dummy"
    return env


def run(probe: Probe, cmd: list, timeout: int = PROBE_TIMEOUT):
    """Run in the clean env, cwd outside the repo so a nearby checkout cannot shadow."""
    return subprocess.run(cmd, env=probe.env, cwd=str(probe.venv_dir),
                          capture_output=True, text=True, timeout=timeout)


def run_python(probe: Probe, code: str):
    """Run one snippet under `-I`, which also keeps cwd off sys.path."""
    return run(probe, [str(probe.python), "-I", "-c", code])


def fmt(proc) -> str:
    return f"stdout:\n{proc.stdout.strip()}\nstderr:\n{proc.stderr.strip()}"


def marker(proc, key: str) -> str:
    """The `key=value` line a probe printed, ignoring any log noise around it."""
    for line in proc.stdout.splitlines():
        if line.startswith(f"{key}="):
            return line.strip()
    return ""


def resolve_wheel(wheel_dir: Path) -> Path:
    """The one wheel in wheel_dir; never a hardcoded name, release-please bumps it."""
    matches = sorted(glob.glob(str(wheel_dir / "*.whl")))
    if len(matches) != 1:
        raise SystemExit(f"expected exactly one .whl in {wheel_dir}, "
                         f"found {len(matches)}: {matches}")
    return Path(matches[0]).resolve()


def prepare(wheel: Path, venv_dir: Path) -> Probe:
    """Create a bare venv and install ONLY the wheel plus its declared deps."""
    if venv_dir.exists():  # reuse the flag, but never delete a non-venv directory
        if not (venv_dir / "pyvenv.cfg").is_file():
            raise SystemExit(f"refusing to remove {venv_dir}: no pyvenv.cfg, not a virtualenv")
        shutil.rmtree(venv_dir)
    venv.EnvBuilder(with_pip=True, clear=True).create(str(venv_dir))
    data_dir = venv_dir / "shopbot-data"
    data_dir.mkdir(parents=True, exist_ok=True)
    probe = Probe(wheel=wheel, venv_dir=venv_dir,
                  python=venv_bin(venv_dir, "python"),
                  console=venv_bin(venv_dir, "shoppybot"),
                  env=child_env(data_dir))
    install = run(probe, [str(probe.python), "-m", "pip", "install", f"{wheel}[web]"],
                  timeout=INSTALL_TIMEOUT)
    if install.returncode != 0:
        raise SystemExit(f"installing {wheel.name} into {venv_dir} failed:\n{fmt(install)}")
    return probe


def assert_console_script(probe: Probe) -> Result:
    """1. The exact command that failed on master before this phase."""
    proc = run(probe, [str(probe.console), "--help"])
    if proc.returncode != 0:
        return Result(False, f"`shoppybot --help` exited {proc.returncode}", fmt(proc))
    return Result(True, "`shoppybot --help` exits 0")


def assert_imports(probe: Probe) -> Result:
    """2. One interpreter call per module, so every failure is named not inferred."""
    failures = []
    for module in MODULES:
        proc = run_python(probe, f"import {module}")
        if proc.returncode != 0:
            tail = proc.stderr.strip().splitlines()
            failures.append(f"  {module}: {tail[-1] if tail else 'no stderr'}")
    if failures:
        return Result(False, f"{len(failures)} of {len(MODULES)} modules failed to import",
                      "\n".join(failures))
    return Result(True, f"all {len(MODULES)} modules import: {', '.join(MODULES)}")


def assert_data_files(probe: Probe) -> Result:
    """3. Shipping a file and resolving one are different claims; both must hold.
    The zip half proves the package-data globs, the runtime half proves
    importlib.resources finds it; a dropped `core.sounds` marker passes only one."""
    with zipfile.ZipFile(probe.wheel) as zf:
        names = zf.namelist()
    # Per-prefix counts, so the CI log records numbers rather than a boolean.
    counts = {p: sum(1 for n in names if n.startswith(p)) for p in DATA_PREFIXES}
    shipped = ", ".join(f"{p} {n}" for p, n in counts.items())
    empty = [p for p, n in counts.items() if n == 0]
    if empty:
        return Result(False, f"wheel ships nothing under {empty}", f"counts: {shipped}")
    proc = run_python(probe, SOUND_PROBE)
    resolved = marker(proc, "SOUNDS_DIR")
    if proc.returncode != 0:
        return Result(False, f"{SOUND_FILE} does not resolve at runtime", fmt(proc))
    if "site-packages" not in resolved:
        return Result(False, f"sounds resolved outside the clean install: {resolved}", fmt(proc))
    return Result(True, f"wheel entries [{shipped}]; {SOUND_FILE} found under {resolved}")


def assert_bundled_plugins(probe: Probe) -> Result:
    """4. Exactly seven, not at least: a higher count means the plugin root grew
    something unexpected, and Phase 43's discovery work needs to know."""
    proc = run_python(probe, PLUGIN_PROBE)
    if proc.returncode != 0:
        return Result(False, "bundled_plugins_dir() raised", fmt(proc))
    count = marker(proc, "PLUGIN_COUNT").partition("=")[2]
    where = marker(proc, "PLUGIN_DIR").partition("=")[2]
    if count != str(EXPECTED_PLUGINS):
        return Result(False, f"expected {EXPECTED_PLUGINS} shopbot_plugin_*.py, "
                             f"found {count or '?'} in {where}", fmt(proc))
    return Result(True, f"bundled_plugins_dir() holds exactly {count} plugins at {where}")


def try_get(url: str):
    """Status for url, or None if nothing is listening. Any status counts, 4xx
    included: the claim is that the app serves, not that a route answers."""
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, OSError):
        return None


def poll_http(url: str, child) -> tuple:
    """Poll until served, until the child dies, or until the deadline."""
    deadline = time.monotonic() + WEB_TIMEOUT
    while time.monotonic() < deadline:
        if child.poll() is not None:
            return False, f"process exited with code {child.returncode} before serving"
        status = try_get(url)
        if status is not None:
            return True, f"HTTP {status}"
        time.sleep(POLL_INTERVAL)
    return False, f"no HTTP response within {WEB_TIMEOUT:.0f}s"


def stop(child) -> None:
    """Terminate, wait with a timeout, kill if the wait expires."""
    if child.poll() is not None:
        return
    child.terminate()
    try:
        child.wait(timeout=10)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=10)


def assert_web_serves(probe: Probe) -> Result:
    """5. Readiness is an actual HTTP GET, never the printed dashboard line:
    core/cli/web.py prints that line with flush=True BEFORE create_app() runs, so
    a StaticFiles RuntimeError lands after the print. Child output is captured
    because the port-shift notice and any traceback both go there."""
    # Port 0 then read the assignment back, so concurrent matrix legs cannot collide.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
    out_path, err_path = probe.venv_dir / "web-stdout.log", probe.venv_dir / "web-stderr.log"
    cmd = [str(probe.console), "web", "--port", str(port)]
    with open(out_path, "w") as out, open(err_path, "w") as err:
        child = subprocess.Popen(cmd, stdout=out, stderr=err,
                                 env=probe.env, cwd=str(probe.venv_dir))
        try:
            served, why = poll_http(f"http://127.0.0.1:{port}/", child)
        finally:
            stop(child)
    if not served:
        return Result(False, f"`shoppybot web` did not serve on port {port}: {why}",
                      f"stdout:\n{out_path.read_text(errors='replace').strip()}\n"
                      f"stderr:\n{err_path.read_text(errors='replace').strip()}")
    return Result(True, f"`shoppybot web` serves on port {port} ({why})")


# The locked order, as data rather than control flow: CI's first line names the layer.
ASSERTIONS: tuple = (
    ("`shoppybot --help` exits 0", assert_console_script),
    ("every core module imports", assert_imports),
    ("data files ship and a sound resolves", assert_data_files),
    ("the bundled plugin root is intact", assert_bundled_plugins),
    ("`shoppybot web` starts and serves", assert_web_serves),
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Verify a built ShopPyBot wheel.")
    parser.add_argument("--wheel-dir", default="dist",
                        help="directory holding exactly one .whl (default: dist)")
    parser.add_argument("--venv", required=True,
                        help="directory to create the clean environment in")
    args = parser.parse_args(argv)
    wheel = resolve_wheel(Path(args.wheel_dir).resolve())
    venv_dir = Path(args.venv).resolve()
    print(f"wheel : {wheel}\nvenv  : {venv_dir}")
    probe = prepare(wheel, venv_dir)
    for number, (name, check) in enumerate(ASSERTIONS, start=1):
        result = check(probe)
        if not result.ok:
            print(f"FAIL {number}: {name}\n       {result.message}\n{result.detail}")
            return 1
        print(f"PASS {number}: {result.message}")
    print(f"all {len(ASSERTIONS)} assertions passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
