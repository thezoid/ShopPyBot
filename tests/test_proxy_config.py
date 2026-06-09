"""Unit tests for ProxyConfig (ANTI-04 config surface).

Tests the ProxyConfig Pydantic model and its nesting under AppConfig.
Covers defaults, YAML parsing, credential-bearing URL preservation,
and field presence assertions.
"""

from pathlib import Path

import pytest
import yaml

from core.config_schema import AppConfig, ProxyConfig


def _write_config(tmp_path: Path, data: dict) -> Path:
    f = tmp_path / "config.yml"
    f.write_text(yaml.dump(data))
    return f


def test_proxyconfig_defaults():
    """ANTI-04: AppConfig() with no proxy section returns disabled-by-default ProxyConfig."""
    cfg = AppConfig(yaml_file=_write_config(
        Path(__import__("tempfile").mkdtemp()),
        {"available": {"items": []}},
    ))
    assert cfg.proxy.enabled is False
    assert cfg.proxy.urls == []
    assert cfg.proxy.max_failures == 3
    assert cfg.proxy.cooldown_secs == 300.0


def test_proxyconfig_parses_from_yaml(tmp_path):
    """ANTI-04: proxy section in YAML is fully parsed into ProxyConfig."""
    data = {
        "available": {"items": []},
        "proxy": {
            "enabled": True,
            "urls": [
                "http://proxy1.example.com:8080",
                "socks5://proxy2.example.com:1080",
            ],
            "max_failures": 5,
            "cooldown_secs": 120,
        },
    }
    cfg = AppConfig(yaml_file=_write_config(tmp_path, data))
    assert cfg.proxy.enabled is True
    assert len(cfg.proxy.urls) == 2
    assert cfg.proxy.urls[0] == "http://proxy1.example.com:8080"
    assert cfg.proxy.urls[1] == "socks5://proxy2.example.com:1080"
    assert cfg.proxy.max_failures == 5
    assert cfg.proxy.cooldown_secs == 120.0


def test_proxyconfig_urls_with_creds_parse(tmp_path):
    """ANTI-04 / T-13-05: credential-bearing URL survives into cfg.proxy.urls unchanged."""
    data = {
        "available": {"items": []},
        "proxy": {
            "enabled": True,
            "urls": ["http://u:p@1.2.3.4:8080"],
        },
    }
    cfg = AppConfig(yaml_file=_write_config(tmp_path, data))
    assert cfg.proxy.urls == ["http://u:p@1.2.3.4:8080"]


def test_appconfig_has_proxy_field(tmp_path):
    """ANTI-04: AppConfig exposes a .proxy attribute of type ProxyConfig."""
    cfg = AppConfig(yaml_file=_write_config(tmp_path, {"available": {"items": []}}))
    assert hasattr(cfg, "proxy")
    assert isinstance(cfg.proxy, ProxyConfig)
