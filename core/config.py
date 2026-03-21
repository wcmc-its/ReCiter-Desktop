"""Configuration management — loads default + user config."""

import os
import yaml
from pathlib import Path
from typing import Any, Dict

_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "default_config.yaml"
_USER_CONFIG_DIR = Path.home() / ".reciter-desktop"
_USER_CONFIG_PATH = _USER_CONFIG_DIR / "config.yaml"


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning a new dict."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config() -> Dict[str, Any]:
    """Load default config, overlaid with user config if it exists."""
    with open(_DEFAULT_CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)

    if _USER_CONFIG_PATH.exists():
        with open(_USER_CONFIG_PATH, "r") as f:
            user_config = yaml.safe_load(f) or {}
        config = _deep_merge(config, user_config)

    return config


def save_user_config(updates: Dict[str, Any]) -> None:
    """Save user-specific configuration overrides."""
    _USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    existing = {}
    if _USER_CONFIG_PATH.exists():
        with open(_USER_CONFIG_PATH, "r") as f:
            existing = yaml.safe_load(f) or {}

    merged = _deep_merge(existing, updates)
    with open(_USER_CONFIG_PATH, "w") as f:
        yaml.dump(merged, f, default_flow_style=False, sort_keys=False)


def is_configured() -> bool:
    """Check if the user has completed initial setup."""
    if not _USER_CONFIG_PATH.exists():
        return False
    config = load_config()
    inst = config.get("institution", {})
    return bool(inst.get("institution_label"))
