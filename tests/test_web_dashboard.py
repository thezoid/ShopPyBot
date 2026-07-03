"""test_web_dashboard.py: dashboard page rendering tests (Wave 0 scaffold)."""
import pytest
pytest.importorskip("fastapi")

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


@pytest.fixture
def mock_svc():
    svc = MagicMock()
    svc.get_status.return_value = {"running": False}
    svc.list_items.return_value = []
    return svc


@pytest.fixture
def client(mock_svc):
    from web import create_app
    return TestClient(create_app(mock_svc))


def test_dashboard_renders_controls_section(client):
    """GET / renders the Controls section heading."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Controls" in resp.text


def test_dashboard_renders_items_section(client):
    """GET / renders the Items section heading."""
    resp = client.get("/")
    assert "Items" in resp.text


def test_dashboard_renders_credentials_section(client):
    """GET / renders the Credentials section heading."""
    resp = client.get("/")
    assert "Credentials" in resp.text


def test_dashboard_renders_config_section(client):
    """GET / renders the Config section heading."""
    resp = client.get("/")
    assert "Config" in resp.text


def test_dashboard_renders_start_cta(client):
    """GET / includes the 'Start Bot' CTA copy from UI-SPEC."""
    resp = client.get("/")
    assert "Start Bot" in resp.text


def test_dashboard_renders_stop_cta(client):
    """GET / includes the 'Stop Bot' CTA copy from UI-SPEC."""
    resp = client.get("/")
    assert "Stop Bot" in resp.text


def test_dashboard_no_credential_value_in_html():
    """SC3 runtime guard: GET / never leaks a credential value into the HTML.

    Seeds a mock store that returns a KNOWN secret for a credential key.
    The rendered HTML must NOT contain that secret -- the template renders
    only name + Set/Not-set status, never a value (T-10-15).
    """
    from web import create_app
    KNOWN_SECRET = "SUPER_SECRET_TOKEN_12345"

    mock_store = MagicMock()
    mock_store.get.return_value = KNOWN_SECRET  # every key "has" this value

    svc = MagicMock()
    svc.get_status.return_value = {"running": False}
    svc.list_items.return_value = []

    with patch("core.credentials.get_store", return_value=mock_store):
        app = create_app(svc)
        client = TestClient(app)
        resp = client.get("/")

    assert resp.status_code == 200
    assert KNOWN_SECRET not in resp.text


def test_banner_renders_when_non_local(mock_svc):
    """MC-4 regression: banner HTML renders when is_non_local=True.

    Proves that 'reachable beyond localhost' text and 'banner-warning' class appear in
    the dashboard response when the app is bound to a non-local interface.
    """
    from web import create_app
    non_local_client = TestClient(create_app(mock_svc, is_non_local=True))
    resp = non_local_client.get("/")
    assert resp.status_code == 200
    assert "reachable beyond localhost" in resp.text
    assert "banner-warning" in resp.text


def test_banner_absent_when_local(mock_svc):
    """MC-4 regression: banner HTML is absent when is_non_local=False (default).

    Proves the {% if is_non_local %} conditional actually gates the banner -- the
    warning must NOT appear for local-only binds (Pitfall 5).
    """
    from web import create_app
    local_client = TestClient(create_app(mock_svc, is_non_local=False))
    resp = local_client.get("/")
    assert resp.status_code == 200
    assert "reachable beyond localhost" not in resp.text


def test_dashboard_no_platform_config_toggles(client):
    """GET / must NOT render per-platform enable checkboxes in the Config section.

    Per the config-scope discrepancy: AppConfig has no platform 'enabled' field.
    Only notifier toggles (sound, discord, email, sms) render -- not platform names.
    """
    resp = client.get("/")
    html = resp.text
    # Config section must not contain platform-name config controls
    # (the JS loadConfig() renders only WEB_ALLOWLIST keys which have no platform keys)
    platform_names = ["amazon", "bestbuy", "walmart", "target", "gamestop",
                      "squareenix", "newegg"]
    # The config-form-wrapper div is populated by JS from /api/config -- the
    # SSR HTML contains the empty wrapper, not rendered platform toggles.
    # Assert the static HTML template itself contains no platform config input.
    assert 'id="cfg-amazon"' not in html
    assert 'id="cfg-bestbuy"' not in html
    for platform in platform_names:
        assert f'name="{platform}"' not in html and f'data-key="{platform}"' not in html, (
            f"Platform config toggle for {platform!r} leaked into SSR HTML"
        )


# ---------------------------------------------------------------------------
# Phase 25 Wave 0 scaffold — RED until implementation lands in waves 1-2
# ---------------------------------------------------------------------------

def test_fouc_script_first_in_head(client):
    """FOUC inline script must be the first child element of <head>.

    The script must precede all <link> elements so the theme is applied before
    any CSS is loaded, preventing a flash-of-unstyled-content on cold load.
    """
    from html.parser import HTMLParser

    class HeadFirstChildParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self._in_head = False
            self._in_script = False
            self._first_tag = None
            self._script_data = []

        def handle_starttag(self, tag, attrs):
            if tag == "head":
                self._in_head = True
                return
            if self._in_head and self._first_tag is None:
                self._first_tag = tag
                if tag == "script":
                    self._in_script = True

        def handle_endtag(self, tag):
            if tag == "head":
                self._in_head = False
            if tag == "script":
                self._in_script = False

        def handle_data(self, data):
            if self._in_script:
                self._script_data.append(data)

        @property
        def script_body(self):
            return "".join(self._script_data)

    resp = client.get("/")
    assert resp.status_code == 200

    parser = HeadFirstChildParser()
    parser.feed(resp.text)

    assert parser._first_tag == "script", (
        f"First child of <head> is <{parser._first_tag}>, expected <script> (FOUC prevention missing)"
    )
    assert "localStorage" in parser.script_body, (
        "FOUC script does not reference localStorage (theme-read logic missing)"
    )


def test_css_link_order_in_head(client):
    """tokens.css, components.css, and dashboard.css <link> elements must be
    present and appear in that order (tokens before components before dashboard).
    """
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert "/static/tokens.css" in html, "tokens.css <link> missing from <head>"
    assert "/static/components.css" in html, "components.css <link> missing from <head>"
    assert "/static/dashboard.css" in html, "dashboard.css <link> missing from <head>"

    tokens_idx = html.index("/static/tokens.css")
    components_idx = html.index("/static/components.css")
    dashboard_idx = html.index("/static/dashboard.css")

    assert tokens_idx < components_idx < dashboard_idx, (
        f"CSS link order wrong: tokens={tokens_idx} components={components_idx} "
        f"dashboard={dashboard_idx} (expected tokens < components < dashboard)"
    )


def test_no_innerHTML_with_api_data(client):
    """CI regression: dashboard.html must not inject interpolated data via HTML sinks.

    The Phase 25 XSS fix replaced every ``innerHTML``/``insertAdjacentHTML`` sink that
    embedded API values with ``createElement``/``textContent``. This guard fails if any
    future change reintroduces a templated HTML-sink assignment, regardless of the source
    variable name (so a regression in loadConfig, loadItems, loadCredentials, etc. is caught).

    Static ``innerHTML = ''`` clears (no ``${}`` interpolation) remain allowed.
    """
    import re
    import pathlib

    html = (pathlib.Path(__file__).parent.parent / "web" / "templates" / "dashboard.html").read_text(encoding="utf-8")
    # Any inner/outerHTML assigned a string/template that interpolates a ${...} expression.
    assign_pattern = re.compile(r'(?:inner|outer)HTML\s*=\s*[`\'"].*?\$\{', re.DOTALL)
    # insertAdjacentHTML(...) whose argument interpolates a ${...} expression.
    insert_pattern = re.compile(r'insertAdjacentHTML\s*\([^)]*\$\{', re.DOTALL)
    matches = assign_pattern.findall(html) + insert_pattern.findall(html)
    assert not matches, f"interpolated HTML sink (innerHTML/outerHTML/insertAdjacentHTML) found: {matches}"


def test_no_external_urls_in_static(client):
    """No CSS file under web/static/ (including vendor/) may reference an external URL.

    Guards against accidental CDN references or @import url() calls being introduced
    into any committed CSS file (supply-chain threat T-25-02).
    Comments are stripped before scanning to avoid false positives on comment text.
    """
    import re
    import pathlib

    static_dir = pathlib.Path(__file__).parent.parent / "web" / "static"
    for css_file in static_dir.glob("**/*.css"):
        content = css_file.read_text(encoding="utf-8")
        # Strip block comments before scanning to avoid false positives on
        # comment text like "/* No @import url() */"
        content_no_comments = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        assert "url(http" not in content_no_comments, f"External URL in {css_file}"
        assert "@import url(" not in content_no_comments, f"External @import in {css_file}"


def test_uplot_served(client):
    """uPlot vendor JS must be served from /static/vendor/uplot.iife.min.js."""
    resp = client.get("/static/vendor/uplot.iife.min.js")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Phase 34 Plan 02 -- #log-plugin-filter dropdown (FC-01 completion)
# ---------------------------------------------------------------------------


def test_dashboard_log_plugin_filter_populated_from_platform_key(mock_svc):
    """GET / renders #log-plugin-filter with an option per platform_key (FC-01)."""
    from web import create_app

    mock_svc.list_plugins.return_value = [
        {"name": "AmazonPlugin", "platform_key": "amazon"},
        {"name": "BestBuyPlugin", "platform_key": "bestbuy"},
        {"name": "SquareEnixPlugin", "platform_key": "squareenix"},
    ]
    resp = TestClient(create_app(mock_svc)).get("/")
    assert resp.status_code == 200
    html = resp.text
    assert 'id="log-plugin-filter"' in html
    assert '<option value="">All plugins</option>' in html
    assert '<option value="amazon">amazon</option>' in html
    assert '<option value="bestbuy">bestbuy</option>' in html
    # Squareenix (no underscore) uses platform_key verbatim, never the class name.
    assert '<option value="squareenix">squareenix</option>' in html
    assert "SquareEnixPlugin" not in html


def test_dashboard_log_plugin_filter_skips_falsy_platform_key(mock_svc):
    """A plugin with platform_key=None renders no <option> (only the default)."""
    from web import create_app

    mock_svc.list_plugins.return_value = [
        {"name": "UnkeyedPlugin", "platform_key": None},
    ]
    resp = TestClient(create_app(mock_svc)).get("/")
    assert resp.status_code == 200
    html = resp.text
    select_start = html.index('id="log-plugin-filter"')
    select_end = html.index("</select>", select_start)
    select_html = html[select_start:select_end]
    assert select_html.count("<option") == 1, (
        f"Expected only the default 'All plugins' option, got: {select_html!r}"
    )


def test_dashboard_poll_logs_sets_plugin_param(client):
    """pollLogs() JS reads #log-plugin-filter and sets the plugin query param."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    poll_idx = html.index("async function pollLogs()")
    poll_end = html.index("\n    }", html.index("try {", poll_idx))
    poll_body = html[poll_idx:poll_end]
    assert "log-plugin-filter" in poll_body
    assert "params.set('plugin', plugin)" in poll_body


def test_dashboard_plugin_filter_change_wired_to_poll_logs(client):
    """#log-plugin-filter has a 'change' listener that calls pollLogs (mirrors level)."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    idx = html.index("getElementById('log-plugin-filter').addEventListener('change'")
    assert idx != -1
    snippet_end = html.index("});", idx)
    assert "pollLogs()" in html[idx:snippet_end]


# ---------------------------------------------------------------------------
# Phase 35 Plan 01 -- AF-01 SSR remove-button graceful degradation
# ---------------------------------------------------------------------------


def test_dashboard_ssr_remove_form_renders_independent_of_js(mock_svc):
    """SSR items row renders a real <form> POST to /items/remove (AF-01).

    Proves the remove control works even when the JS loadItems() render path
    never runs (or its fetch() rejects): the server-rendered form carries the
    item link as a hidden input and posts directly, no JS required.
    """
    from web import create_app

    mock_svc.list_items.return_value = [
        ("Widget", "https://ex.com/w", False, 1, False),
    ]
    resp = TestClient(create_app(mock_svc)).get("/")
    assert resp.status_code == 200
    html = resp.text
    assert '<form method="post" action="/items/remove"' in html
    assert 'name="link" value="https://ex.com/w"' in html
    assert 'class="btn-remove"' not in html
