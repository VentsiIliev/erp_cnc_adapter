"""Configuration persistence - Save and load config changes."""

import json
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Configuration file location
CONFIG_FILE = Path(__file__).resolve().parent.parent.parent / "config.json"


def load_user_config() -> Dict[str, Any]:
    """
    Load user configuration from config.json file.

    Returns:
        Dictionary with user config overrides, or empty dict if file doesn't exist
    """
    if not CONFIG_FILE.exists():
        logger.debug("No user config file found at: %s", CONFIG_FILE)
        return {}

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        logger.info("Loaded user config from: %s", CONFIG_FILE)
        return config
    except Exception as e:
        logger.error("Error loading user config from %s: %s", CONFIG_FILE, e)
        return {}


def save_user_config(config_dict: Dict[str, Any]) -> bool:
    """
    Save user configuration to config.json file.

    Args:
        config_dict: Dictionary with config values to save

    Returns:
        True if saved successfully, False otherwise
    """
    try:
        # Ensure parent directory exists
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Write config with pretty formatting
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)

        logger.info("Saved user config to: %s", CONFIG_FILE)
        return True
    except Exception as e:
        logger.error("Error saving user config to %s: %s", CONFIG_FILE, e)
        return False


def get_persisted_config() -> Dict[str, Any]:
    """
    Get the currently persisted configuration.

    Returns:
        Dictionary with persisted config values
    """
    return load_user_config()


def update_persisted_config(updates: Dict[str, Any]) -> bool:
    """
    Update persisted configuration with new values.

    Args:
        updates: Dictionary with config values to update

    Returns:
        True if saved successfully, False otherwise
    """
    # Load existing config
    config = load_user_config()

    # Update with new values
    config.update(updates)

    # Save back to file
    return save_user_config(config)

