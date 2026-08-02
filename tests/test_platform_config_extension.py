"""Tests for CFG-02: generic per-platform config declaration without core edits.

Proves a plugin can declare a previously-undeclared platforms.<key> section that
loads and validates via RetailerPlugin.get_platform_config(model_cls) -- with
core/config_schema.py changed by nothing more than the single
model_config = ConfigDict(extra="allow") line on PlatformsConfig -- and that the
7 built-in platforms keep full strict validation.

CostcoPlatformConfig is defined here at TEST-MODULE scope (not inside the tmp
plugin file). core/registry.py:_discover_plugins loads plugin files via
importlib.util.spec_from_file_location + exec_module WITHOUT registering the
module in sys.modules or adding tmp_path to sys.path, so
importlib.import_module("shopbot_plugin_costco") would raise ModuleNotFoundError
(an import-machinery limitation, not a CFG-02 failure). The tmp plugin file only
needs to declare CostcoPlugin(platform_key="costco"); the model_cls under test
is passed in directly by the test.
"""

import pytest
import yaml
from pydantic import BaseModel, Field, ValidationError

from core.config_schema import AppConfig, PlatformsConfig
from core.registry import PluginRegistry


class CostcoPlatformConfig(BaseModel):
    """Test-module-scope model_cls for the fixture plugin's platforms.costco section."""

    delay_seconds: float = Field(default=10.0, ge=0.0)
    delay_jitter: float = Field(default=5.0, ge=0.0)


_COSTCO_PLUGIN_CODE = (
    "from core.plugin_base import RetailerPlugin\n"
    "\n"
    "\n"
    "class CostcoPlugin(RetailerPlugin):\n"
    "    domain_patterns = ['costco.com']\n"
    "    platform_key = 'costco'\n"
    "\n"
    "    async def check_availability(self, url):\n"
    "        return True\n"
    "\n"
    "    async def auto_buy(self, url):\n"
    "        return False\n"
)


def _build_costco_registry(tmp_path, platforms_section: dict) -> PluginRegistry:
    """Write the fixture plugin + a config.yml carrying platforms_section, build a registry.

    AppConfig.settings_customise_sources excludes init_settings from its source
    tuple (only env_settings + YamlConfigSettingsSource are wired in), so passing
    a "platforms" dict as an AppConfig(**kwargs) constructor argument is silently
    ignored. The established, working injection path throughout this codebase's
    test suite (tests/conftest.py, tests/test_config_schema.py) is a real
    yaml_file=<Path> pointing at a written config.yml -- used here for the same
    reason.
    """
    (tmp_path / "shopbot_plugin_costco.py").write_text(_COSTCO_PLUGIN_CODE)
    config_yml = tmp_path / "config.yml"
    config_yml.write_text(yaml.dump({"platforms": platforms_section}))
    cfg = AppConfig(yaml_file=config_yml)
    return PluginRegistry(cfg, tmp_path)


def test_new_plugin_platform_section_validates_without_core_edits(tmp_path):
    """A brand-new platforms.costco section loads + validates via get_platform_config."""
    registry = _build_costco_registry(tmp_path, {"costco": {"delay_seconds": 12.0}})
    plugin = registry._all_plugins[0]

    parsed = plugin.get_platform_config(CostcoPlatformConfig)

    assert parsed.delay_seconds == 12.0     # explicit YAML value validated
    assert parsed.delay_jitter == 5.0       # model default applied for unset field


def test_new_plugin_section_invalid_value_raises(tmp_path):
    """An undeclared section with an invalid value raises ValidationError, fail-loud."""
    registry = _build_costco_registry(tmp_path, {"costco": {"delay_seconds": -1}})
    plugin = registry._all_plugins[0]

    with pytest.raises(ValidationError):
        plugin.get_platform_config(CostcoPlatformConfig)


def test_known_platform_strict_validation_intact():
    """extra='allow' governs ONLY undeclared keys; the 7 declared platforms stay strict."""
    with pytest.raises(ValidationError):
        PlatformsConfig(**{"amazon": {"delay_seconds": -5}})


def test_get_platform_config_defaults_when_section_absent(tmp_path):
    """A plugin whose platform_key has no matching section gets model_cls() defaults."""
    registry = _build_costco_registry(tmp_path, {})  # no costco section at all
    plugin = registry._all_plugins[0]

    parsed = plugin.get_platform_config(CostcoPlatformConfig)

    assert parsed.delay_seconds == 10.0
    assert parsed.delay_jitter == 5.0


def test_get_platform_config_mismatched_model_raises_type_error(tmp_path):
    """WR-02: a platform_key collision with a section already validated against a
    DIFFERENT model_cls must fail loudly (TypeError), not silently return
    model_cls() defaults and discard the real, already-validated config."""
    registry = _build_costco_registry(tmp_path, {"amazon": {"delay_seconds": 77.0}})
    plugin = registry._all_plugins[0]
    plugin.platform_key = "amazon"  # collide with a built-in, already-validated section

    with pytest.raises(TypeError):
        plugin.get_platform_config(CostcoPlatformConfig)
