import pytest
import logging
import configparser

from resources.services.rest_api import RestAPI
from helpers.config_manager import CONFIGS

logger = logging.getLogger(__name__)

REST_ENDPOINTS = {
    "prod": "https://api.crypto.com/exchange/v1/",
    "uat":  "https://uat-api.3ona.co/exchange/v1/",
}
WS_MARKET_ENDPOINTS = {
    "prod": "wss://stream.crypto.com/exchange/v1/market",
    "uat":  "wss://uat-stream.3ona.co/exchange/v1/market",
}

# ---------- 通用小工具：同時支援 dict / SectionProxy / ConfigParser ----------
def _cfg_get(cfg, key, default=None):
    """從 cfg 取 key：
       - dict: cfg.get(key, default)
       - SectionProxy: cfg.get(key, fallback=default)
       - ConfigParser: cfg.get('env', key, fallback=default)
    """
    if cfg is None:
        return default
    if isinstance(cfg, dict):
        return cfg.get(key, default)
    if isinstance(cfg, configparser.SectionProxy):
        return cfg.get(key, fallback=default)
    if isinstance(cfg, configparser.ConfigParser):
        if cfg.has_section("env"):
            return cfg.get("env", key, fallback=default)
        return default
    return default

def _pick_instrument(cfg) -> str:
    for k in ("instrument_name", "instrument", "symbol"):
        v = _cfg_get(cfg, k, None)
        if v:
            return str(v).strip()
    return "BTCUSD-PERP"

def _to_int(val, default: int) -> int:
    try:
        return int(str(val).strip())
    except Exception:
        return default

def _sanitize_env(val) -> str:
    env = (str(val).strip().lower() if val is not None else "prod")
    if env not in REST_ENDPOINTS:
        raise ValueError(f"Unknown env: {env}. Use 'prod' or 'uat'.")
    return env

def _sanitize_book_type(val) -> str:
    x = (str(val).strip().upper() if val is not None else "SNAPSHOT_AND_UPDATE")
    return x if x in ("SNAPSHOT", "SNAPSHOT_AND_UPDATE") else "SNAPSHOT_AND_UPDATE"

def _resolve_urls(env: str) -> dict:
    return {
        "rest_base": REST_ENDPOINTS[env],
        "ws_market_url": WS_MARKET_ENDPOINTS[env],
    }

def pytest_addoption(parser):
    parser.addoption("--env", action="store", default=None, help="prod|uat")
    parser.addoption("--instrument", action="store", default=None, help="e.g. BTCUSD-PERP")
    parser.addoption("--depth", action="store", default=None, help="10|50|150 ...")
    parser.addoption("--book-type", action="store", default=None, help="SNAPSHOT or SNAPSHOT_AND_UPDATE")
    parser.addoption("--book-freq", action="store", default=None, help="delta freq ms, e.g. 10|100")
    parser.addoption("--server", action="store", default=None, help="Override REST/WS base. ws(s):// for WS, http(s):// for REST")
    parser.addoption("--cafile", action="store", default=None, help="Path to custom CA bundle (PEM)")
    parser.addoption("--insecure", action="store_true", help="Disable TLS verification (NOT for prod)")

@pytest.fixture(scope="session")
def app_cfg(pytestconfig):
    # 允許 CONFIGS["RUN_INI"] 是 dict / SectionProxy / ConfigParser
    ini_cfg = CONFIGS.get("RUN_INI")

    # 先取 INI 值，再允許 CLI 覆蓋
    env_val   = _sanitize_env(pytestconfig.getoption("--env") or _cfg_get(ini_cfg, "env", "prod"))
    instr_val = pytestconfig.getoption("--instrument") or _pick_instrument(ini_cfg)
    depth_val = _to_int(pytestconfig.getoption("--depth") or _cfg_get(ini_cfg, "depth", 50), 50)
    btype_val = _sanitize_book_type(pytestconfig.getoption("--book-type") or _cfg_get(ini_cfg, "book_subscription_type", "SNAPSHOT_AND_UPDATE"))
    bfreq_val = _to_int(pytestconfig.getoption("--book-freq") or _cfg_get(ini_cfg, "book_update_frequency", 10), 10)

    urls = _resolve_urls(env_val)

    # 可選：臨時覆蓋 REST/WS base
    server_override = pytestconfig.getoption("--server")
    if server_override:
        s = str(server_override).strip()
        if s.startswith(("ws://", "wss://")):
            urls["ws_market_url"] = s
        elif s.startswith(("http://", "https://")):
            if not s.endswith("/"):
                s += "/"
            urls["rest_base"] = s
        else:
            logger.warning("Unknown --server scheme: %s (ignored)", s)

    cfg = {
        "env": env_val,
        "instrument_name": instr_val or "BTCUSD-PERP",
        "depth": depth_val,
        "book_subscription_type": btype_val,
        "book_update_frequency": bfreq_val,
        "rest_base": urls["rest_base"],
        "ws_market_url": urls["ws_market_url"],
    }

    logger.info(
        "[CFG] env=%s instrument=%s depth=%s book_type=%s book_freq=%sms rest=%s ws=%s",
        cfg["env"], cfg["instrument_name"], cfg["depth"],
        cfg["book_subscription_type"], cfg["book_update_frequency"],
        cfg["rest_base"], cfg["ws_market_url"]
    )
    return cfg

@pytest.fixture(scope="session")
def rest_api(app_cfg):
    return RestAPI(
        server=app_cfg["rest_base"],
        insecure=app_cfg.get("insecure", False),
        cafile=app_cfg.get("cafile"),
    )

@pytest.fixture(scope="session")
def instrument_name(app_cfg) -> str:
    return app_cfg.get("instrument_name") or "BTCUSD-PERP"