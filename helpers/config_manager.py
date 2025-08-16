import json
import logging
from configparser import ConfigParser
from functools import lru_cache
from helpers.project_paths import (
    RUN_INI_PATH,
    TEST_DATA_REST_CANDLESTICK_PATH,
)
from typing import Union

logger = logging.getLogger(__name__)


# ----- Lazy Loading Functions -----
@lru_cache()
def get_config(path: str, encoding="utf-8") -> ConfigParser:
    """Loads an INI configuration file lazily to prevent FileNotFoundError."""
    config = ConfigParser()
    try:
        config.read(path, encoding=encoding)
        return config
    except FileNotFoundError:
        logger.warning(f"Configuration file not found: {path}")
        return None


# ----- Lazy Loading Functions -----
@lru_cache()
def get_json(path: str, encoding: str = "utf-8") -> Union[dict, list]:
    """Lazily load a JSON file, return {} if not found or parse error."""
    try:
        with open(path, "r", encoding=encoding) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning(f"JSON file not found or invalid: {path}")
        return {}


# ----- Centralized Configuration Management (Lazy Loading) -----
CONFIGS = {
    "RUN_INI": lambda: get_config(RUN_INI_PATH),
}

JSON_DATA = {
    "TEST_DATA_REST_CANDLESTICK": get_json(TEST_DATA_REST_CANDLESTICK_PATH),
}
