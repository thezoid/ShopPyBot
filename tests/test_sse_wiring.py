"""test_sse_wiring.py: Phase 29 Wave 0 RED scaffold — SSE client wiring assertions.

Static template assertions via TestClient GET / against the rendered dashboard.html.
Each test maps to one automatable W29-Ax assertion from 29-RESEARCH.md.

These tests MUST FAIL (RED) at Wave 0 because the SSE wiring (EventSource block,
renderStatus extraction, no-dup guard, indicator element) is NOT yet present in
dashboard.html. They turn GREEN as Plans 02 and 03 land each piece.

5 live criteria are inherently manual UAT (DevTools one-stream observation, 1-2s
update timing, no-dup boundary, reconnect behavior, fallback-path polling). They
are NOT automated here per 29-VALIDATION.md.

Does NOT duplicate:
- test_no_innerHTML_with_api_data (lives in test_web_dashboard.py; scans full file)
- test_no_hardcoded_hex_in_components (lives in test_design_system.py)
"""
import re
import pytest
pytest.importorskip("fastapi")

from unittest.mock import MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def mock_svc():
    svc = MagicMock()
    svc.get_status.return_value = {"running": False, "uptime_secs": 0, "plugins": {}}
    svc.list_items.return_value = []
    return svc


@pytest.fixture
def client(mock_svc):
    from web import create_app
    return TestClient(create_app(mock_svc))


# ---------------------------------------------------------------------------
# W29-A1: EventSource constructor present
# ---------------------------------------------------------------------------

def test_eventsource_constructed(client):
    """GET / HTML contains `new EventSource('/api/events')` (W29-A1).

    RED until Plan 02/03 adds the SSE wiring block.
    """
    resp = client.get("/")
    assert resp.status_code == 200
    assert "new EventSource('/api/events')" in resp.text


# ---------------------------------------------------------------------------
# W29-A2: Named status event listener
# ---------------------------------------------------------------------------

def test_named_status_listener(client):
    """GET / HTML contains `addEventListener('status'` (W29-A2).

    Named events require addEventListener, not onmessage.
    RED until Plan 02/03 adds the SSE addEventListener block.
    """
    resp = client.get("/")
    assert resp.status_code == 200
    assert "addEventListener('status'" in resp.text


# ---------------------------------------------------------------------------
# W29-A3: Named log event listener
# ---------------------------------------------------------------------------

def test_named_log_listener(client):
    """GET / HTML contains `addEventListener('log'` (W29-A3).

    RED until Plan 02/03 adds the SSE addEventListener block.
    """
    resp = client.get("/")
    assert resp.status_code == 200
    assert "addEventListener('log'" in resp.text


# ---------------------------------------------------------------------------
# Anti-pattern guard (Pitfall 1 from 29-RESEARCH.md)
# Named events NEVER fire onmessage — assert it is absent from the template.
# This test is expected to PASS at Wave 0 (no onmessage exists today) and must
# remain GREEN through all subsequent plans.
# ---------------------------------------------------------------------------

def test_no_onmessage_for_named_events(client):
    """GET / HTML does NOT use `es.onmessage` for SSE events (anti-pattern guard).

    Named events (`event: status` / `event: log`) route only to addEventListener
    listeners, never to onmessage. Presence of .onmessage in the SSE block would
    be a silent bug (events delivered but handler never called).
    GREEN at Wave 0 (not yet present); must stay GREEN through Plan 02/03.
    """
    resp = client.get("/")
    assert resp.status_code == 200
    assert ".onmessage" not in resp.text


# ---------------------------------------------------------------------------
# W29-A4: Feature-detect guard present
# ---------------------------------------------------------------------------

def test_feature_detect_present(client):
    """GET / HTML contains `typeof EventSource` feature-detect block (W29-A4).

    The feature-detect gates SSE wiring vs. polling fallback.
    RED until Plan 02/03 adds the feature-detect block.
    """
    resp = client.get("/")
    assert resp.status_code == 200
    assert "typeof EventSource" in resp.text


# ---------------------------------------------------------------------------
# W29-A5: renderStatus shared render function present
# ---------------------------------------------------------------------------

def test_render_status_extracted(client):
    """GET / HTML contains `renderStatus` function (W29-A5).

    renderStatus(data) is extracted from pollStatus so both the SSE status
    handler and the polling fallback share one source of truth for DOM updates.
    RED until Plan 02 extracts renderStatus from pollStatus.
    """
    resp = client.get("/")
    assert resp.status_code == 200
    assert "renderStatus" in resp.text


# ---------------------------------------------------------------------------
# W29-A6: No-dup guard variable present
# ---------------------------------------------------------------------------

def test_no_dup_guard_present(client):
    """GET / HTML contains `_lastLogLine` no-dup guard (W29-A6).

    The guard skips a log line identical to the immediately-preceding one,
    preventing the backfill/SSE boundary overlap from duplicating lines.
    RED until Plan 03 adds the no-dup guard to appendLogLine.
    """
    resp = client.get("/")
    assert resp.status_code == 200
    assert "_lastLogLine" in resp.text


# ---------------------------------------------------------------------------
# W29-A7: Live/Reconnecting indicator element present
# ---------------------------------------------------------------------------

def test_indicator_element_present(client):
    """GET / HTML contains `id="sse-indicator"` element in the sticky header (W29-A7).

    The element must exist in HTML before the JS setIndicator() function references
    it; missing element causes null-pointer errors on onopen/onerror callbacks.
    RED until Plan 03 adds the <span id="sse-indicator"> to the app-header.
    """
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'id="sse-indicator"' in resp.text


# ---------------------------------------------------------------------------
# W29-A11: setInterval calls ONLY inside the else fallback branch
# ---------------------------------------------------------------------------

def test_setinterval_only_in_fallback(client):
    """setInterval(pollStatus and setInterval(pollLogs only appear inside the
    `else` branch of the typeof EventSource feature-detect (W29-A11).

    Criterion 1: no polling fires on the SSE-active path. The feature-detect
    must gate the setInterval calls to the `else` (no-EventSource) branch only.

    Strategy: find `typeof EventSource` in resp.text; locate the first `else`
    token after it; assert both setInterval(pollStatus and setInterval(pollLogs
    appear ONLY after that else index. If either setInterval appears before the
    else index, the SSE-active path would also start polling.

    RED at Wave 0: setInterval calls exist at module top-level (before any
    feature-detect) in the current template. Will turn GREEN when Plan 02/03
    moves them inside the else branch.
    """
    resp = client.get("/")
    assert resp.status_code == 200
    text = resp.text

    # Locate the typeof EventSource feature-detect block.
    detect_idx = text.find("typeof EventSource")
    assert detect_idx != -1, "typeof EventSource feature-detect not found in page"

    # Find the first `else` token AFTER the feature-detect.
    sub = text[detect_idx:]
    else_match = re.search(r'\belse\b', sub)
    assert else_match is not None, "No `else` branch found after typeof EventSource"
    else_abs_idx = detect_idx + else_match.start()

    # Both setInterval calls must appear AFTER the else branch start.
    poll_status_idx = text.find("setInterval(pollStatus", else_abs_idx)
    poll_logs_idx = text.find("setInterval(pollLogs", else_abs_idx)

    assert poll_status_idx != -1, (
        "setInterval(pollStatus not found after the else branch of typeof EventSource; "
        "it must be in the fallback branch only"
    )
    assert poll_logs_idx != -1, (
        "setInterval(pollLogs not found after the else branch of typeof EventSource; "
        "it must be in the fallback branch only"
    )

    # Confirm neither setInterval appears BEFORE the else (which would mean it is
    # on the SSE-active path or at module top-level outside the feature-detect).
    early_poll_status = text.find("setInterval(pollStatus")
    early_poll_logs = text.find("setInterval(pollLogs")

    assert early_poll_status >= else_abs_idx, (
        f"setInterval(pollStatus found at index {early_poll_status}, "
        f"which is before the else branch at {else_abs_idx}; "
        "polling must not fire on the SSE-active path"
    )
    assert early_poll_logs >= else_abs_idx, (
        f"setInterval(pollLogs found at index {early_poll_logs}, "
        f"which is before the else branch at {else_abs_idx}; "
        "polling must not fire on the SSE-active path"
    )
