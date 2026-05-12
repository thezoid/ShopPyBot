"""Compatibility shim. The legacy `config` dict has been replaced by AppConfig.

Importers should switch to:
    from config_schema import AppConfig
    app_config = AppConfig()

This module remains only to fail loudly if old import patterns survive.
"""
raise ImportError(
    "`from config import config` is no longer supported. "
    "Use `from config_schema import AppConfig` and instantiate `AppConfig()` instead."
)
