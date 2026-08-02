"""Port auto-increment for `shoppybot web`.

IMPORTANT: every test resolves `core.cli.web` from sys.modules INSIDE the test
body. tests/test_cli_no_fastapi.py purges that module from sys.modules to force
its lazy-import guard to fire, so an import-time binding here would hold a stale
module object while monkeypatch targets the fresh one -- passing in isolation and
failing in a full-suite run.

The pure helpers need no fastapi (core.cli.web imports only socket and sys at
module level, the CLI-04 invariant); handle_web tests importorskip individually.
"""

import socket

import pytest


def _web():
    """The live core.cli.web module object, whatever sys.modules holds right now."""
    from core.cli import web
    return web


def _args(**kw):
    base = {"host": "127.0.0.1", "port": 8000, "open_browser": False}
    base.update(kw)
    return type("args", (), base)()


# ---------------------------------------------------------------------------
# find_open_port
# ---------------------------------------------------------------------------

def test_returns_start_port_when_free(monkeypatch):
    """A free requested port is returned unchanged -- no gratuitous increment."""
    web = _web()
    monkeypatch.setattr(web, "_is_port_free", lambda host, port: True)
    assert web.find_open_port("127.0.0.1", 8000) == 8000


def test_skips_busy_ports(monkeypatch):
    """Scanning walks upward past busy ports and stops at the first free one."""
    web = _web()
    busy = {8000, 8001, 8002}
    monkeypatch.setattr(web, "_is_port_free", lambda host, port: port not in busy)
    assert web.find_open_port("127.0.0.1", 8000) == 8003


def test_returns_none_when_scan_exhausted(monkeypatch):
    """Every candidate busy -> None, so the caller can fail loudly."""
    web = _web()
    monkeypatch.setattr(web, "_is_port_free", lambda host, port: False)
    assert web.find_open_port("127.0.0.1", 8000) is None


def test_scan_window_is_bounded(monkeypatch):
    """The scan probes exactly PORT_SCAN_ATTEMPTS candidates, never unbounded."""
    web = _web()
    probed = []

    def record(host, port):
        probed.append(port)
        return False

    monkeypatch.setattr(web, "_is_port_free", record)
    web.find_open_port("127.0.0.1", 8000)
    assert probed == list(range(8000, 8000 + web.PORT_SCAN_ATTEMPTS))


def test_does_not_exceed_max_port(monkeypatch):
    """Scanning near the top of the range stops at 65535 instead of overflowing."""
    web = _web()
    monkeypatch.setattr(web, "_is_port_free", lambda host, port: False)
    assert web.find_open_port("127.0.0.1", 65530) is None


def test_real_socket_is_detected_as_busy():
    """Integration: a port this test owns is skipped by a real bind probe."""
    web = _web()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as held:
        held.bind(("127.0.0.1", 0))          # let the OS pick a free port
        held.listen(1)
        taken = held.getsockname()[1]
        chosen = web.find_open_port("127.0.0.1", taken)
        assert chosen is not None
        assert chosen != taken
        assert chosen > taken


# ---------------------------------------------------------------------------
# browse_host
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("host, expected", [
    ("0.0.0.0", "127.0.0.1"),
    ("::", "127.0.0.1"),
    ("", "127.0.0.1"),
    ("127.0.0.1", "127.0.0.1"),
    ("192.168.1.5", "192.168.1.5"),
])
def test_browse_host_maps_wildcards(host, expected):
    """Wildcard binds are not addressable, so the printed URL uses loopback."""
    assert _web().browse_host(host) == expected


# ---------------------------------------------------------------------------
# handle_web wiring
# ---------------------------------------------------------------------------

def test_handle_web_serves_on_fallback_port(capsys, monkeypatch):
    """When the requested port is busy, uvicorn is handed the fallback port."""
    pytest.importorskip("fastapi")
    import uvicorn
    from unittest.mock import MagicMock
    web = _web()

    captured = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: captured.update(kw))
    monkeypatch.setattr(web, "find_open_port", lambda host, port: 8007)

    assert web.handle_web(_args(), MagicMock()) == 0
    assert captured["port"] == 8007

    out = capsys.readouterr()
    assert "8000 is already in use" in out.err
    assert "serving on 8007" in out.err
    assert "http://127.0.0.1:8007/" in out.out


def test_handle_web_quiet_when_requested_port_free(capsys, monkeypatch):
    """No in-use warning when the requested port was available."""
    pytest.importorskip("fastapi")
    import uvicorn
    from unittest.mock import MagicMock
    web = _web()

    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: None)
    monkeypatch.setattr(web, "find_open_port", lambda host, port: port)

    assert web.handle_web(_args(), MagicMock()) == 0
    out = capsys.readouterr()
    assert "already in use" not in out.err
    assert "http://127.0.0.1:8000/" in out.out


def test_handle_web_exits_1_when_no_port_free(capsys, monkeypatch):
    """Exhausted scan returns exit code 1 and never starts uvicorn."""
    pytest.importorskip("fastapi")
    import uvicorn
    from unittest.mock import MagicMock
    web = _web()

    ran = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: ran.append(kw))
    monkeypatch.setattr(web, "find_open_port", lambda host, port: None)

    assert web.handle_web(_args(), MagicMock()) == 1
    assert ran == []
    assert "No free port found" in capsys.readouterr().err


def test_handle_web_does_not_open_browser_by_default(monkeypatch):
    """--open is opt-in: the default path never launches a browser."""
    pytest.importorskip("fastapi")
    import uvicorn
    from unittest.mock import MagicMock
    web = _web()

    opened = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: None)
    monkeypatch.setattr(web, "find_open_port", lambda host, port: port)
    monkeypatch.setattr(web, "_open_when_up", lambda url, **kw: opened.append(url))

    web.handle_web(_args(), MagicMock())
    assert opened == []


def test_handle_web_opens_browser_with_flag(monkeypatch):
    """--open passes the resolved URL, including a fallback port, to the opener."""
    pytest.importorskip("fastapi")
    import uvicorn
    from unittest.mock import MagicMock
    web = _web()

    opened = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: None)
    monkeypatch.setattr(web, "find_open_port", lambda host, port: 8003)
    monkeypatch.setattr(web, "_open_when_up", lambda url, **kw: opened.append(url))

    web.handle_web(_args(open_browser=True), MagicMock())
    assert opened == ["http://127.0.0.1:8003/"]


def test_handle_web_open_url_uses_loopback_for_wildcard_bind(monkeypatch):
    """A 0.0.0.0 bind is advertised as 127.0.0.1, which is actually browsable."""
    pytest.importorskip("fastapi")
    import uvicorn
    from unittest.mock import MagicMock
    web = _web()

    opened = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: None)
    monkeypatch.setattr(web, "find_open_port", lambda host, port: port)
    monkeypatch.setattr(web, "_open_when_up", lambda url, **kw: opened.append(url))

    web.handle_web(_args(host="0.0.0.0", open_browser=True), MagicMock())
    assert opened == ["http://127.0.0.1:8000/"]
