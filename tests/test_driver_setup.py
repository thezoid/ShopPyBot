from unittest.mock import patch, MagicMock
import pathlib


def test_no_stdout_monkey_patch_in_source():
    src = pathlib.Path("driver.py").read_text()
    assert "sys.stdout = open" not in src, "INFRA-03: no sys.stdout monkey-patch"
    assert "sys.stderr = open" not in src, "INFRA-03: no sys.stderr monkey-patch"


@patch("driver.webdriver.Chrome")
@patch("driver.Service")
def test_no_disable_web_security(mock_service, mock_chrome, tmp_path):
    from driver import build_driver
    build_driver("/fake/chromedriver", log_path=str(tmp_path / "cd.log"))
    _, kwargs = mock_chrome.call_args
    opts = kwargs["options"]
    assert "--disable-web-security" not in opts.arguments


@patch("driver.webdriver.Chrome")
@patch("driver.Service")
def test_real_user_agent_set(mock_service, mock_chrome, tmp_path):
    from driver import build_driver
    build_driver("/fake/chromedriver", log_path=str(tmp_path / "cd.log"))
    _, kwargs = mock_chrome.call_args
    opts = kwargs["options"]
    ua_args = [a for a in opts.arguments if a.startswith("--user-agent=")]
    assert len(ua_args) == 1, f"expected 1 user-agent arg, got {ua_args}"
    ua = ua_args[0]
    assert "Chrome/" in ua
    assert "Selenium" not in ua
    assert "HeadlessChrome" not in ua


@patch("driver.webdriver.Chrome")
@patch("driver.Service")
def test_cdp_webdriver_hide_called(mock_service, mock_chrome, tmp_path):
    fake_driver = MagicMock()
    mock_chrome.return_value = fake_driver
    from driver import build_driver
    build_driver("/fake/chromedriver", log_path=str(tmp_path / "cd.log"))
    fake_driver.execute_cdp_cmd.assert_called_once()
    call_args = fake_driver.execute_cdp_cmd.call_args
    assert call_args.args[0] == "Page.addScriptToEvaluateOnNewDocument"
    source = call_args.args[1]["source"]
    assert "navigator.webdriver" in source


@patch("driver.webdriver.Chrome")
@patch("driver.Service")
def test_service_uses_log_path(mock_service, mock_chrome, tmp_path):
    from driver import build_driver
    log = str(tmp_path / "cd.log")
    build_driver("/fake/chromedriver", log_path=log)
    _, kwargs = mock_service.call_args
    assert kwargs.get("log_path") == log, f"Service log_path missing or wrong: {kwargs}"


# ---------- Phase 6 D-04 / ANTI-02: headless=new + UA rotation ----------


def test_defaultUserAgentsIsNonEmptyListOfStrings():
    from driver import DEFAULT_USER_AGENTS
    assert isinstance(DEFAULT_USER_AGENTS, list)
    assert len(DEFAULT_USER_AGENTS) >= 5
    for ua in DEFAULT_USER_AGENTS:
        assert isinstance(ua, str)
        assert "Chrome/" in ua


@patch("driver.webdriver.Chrome")
@patch("driver.Service")
def test_buildDriverHeadlessNewFlagWhenEnabled(mock_service, mock_chrome, tmp_path):
    from driver import build_driver
    build_driver("/fake/chromedriver", log_path=str(tmp_path / "cd.log"), headless=True)
    _, kwargs = mock_chrome.call_args
    opts = kwargs["options"]
    assert "--headless=new" in opts.arguments
    assert "--headless" not in opts.arguments


@patch("driver.webdriver.Chrome")
@patch("driver.Service")
def test_buildDriverNoHeadlessFlagByDefault(mock_service, mock_chrome, tmp_path):
    from driver import build_driver
    build_driver("/fake/chromedriver", log_path=str(tmp_path / "cd.log"))
    _, kwargs = mock_chrome.call_args
    opts = kwargs["options"]
    assert "--headless=new" not in opts.arguments
    assert "--headless" not in opts.arguments


@patch("driver.webdriver.Chrome")
@patch("driver.Service")
def test_userAgentRotation(mock_service, mock_chrome, tmp_path, monkeypatch):
    from driver import build_driver
    pool = iter(["UA-AAA", "UA-BBB"])
    monkeypatch.setattr("driver.random.choice", lambda seq: next(pool))
    build_driver("/fake/chromedriver", log_path=str(tmp_path / "cd1.log"))
    opts1 = mock_chrome.call_args.kwargs["options"]
    ua1 = [a for a in opts1.arguments if a.startswith("--user-agent=")][0]
    build_driver("/fake/chromedriver", log_path=str(tmp_path / "cd2.log"))
    opts2 = mock_chrome.call_args.kwargs["options"]
    ua2 = [a for a in opts2.arguments if a.startswith("--user-agent=")][0]
    assert ua1 == "--user-agent=UA-AAA"
    assert ua2 == "--user-agent=UA-BBB"
    assert ua1 != ua2


@patch("driver.webdriver.Chrome")
@patch("driver.Service")
def test_userAgentsKwargOverride(mock_service, mock_chrome, tmp_path):
    from driver import build_driver
    build_driver(
        "/fake/chromedriver",
        log_path=str(tmp_path / "cd.log"),
        user_agents=["UA-X"],
    )
    opts = mock_chrome.call_args.kwargs["options"]
    ua_args = [a for a in opts.arguments if a.startswith("--user-agent=")]
    assert ua_args == ["--user-agent=UA-X"]
