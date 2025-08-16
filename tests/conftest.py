import os
import pytest

from helpers.config_manager import JSON_DATA
from resources.utils.root_endpoint_utils import get_rest_base
from resources.services.rest_api import RestAPI

# ---- 路徑與預設 ----
DEFAULT_INSTRUMENT = os.getenv("INSTRUMENT_NAME", "BTCUSD-PERP")


# ---- pytest 命令列參數 ----
def pytest_addoption(parser):
    parser.addoption(
        "--rest-env",
        action="store",
        default="prod",  # prod | uat
        help="REST environment to use: prod | uat",
    )
    parser.addoption(
        "--instrument",
        action="store",
        default=None,  # 若未提供，落到 DEFAULT_INSTRUMENT
        help=f"Instrument name to query (default: {DEFAULT_INSTRUMENT})",
    )


# ---- 基本 fixture ----
@pytest.fixture(scope="session")
def rest_base_url(pytestconfig):
    env = pytestconfig.getoption("--rest-env")
    return get_rest_base(env=env)


@pytest.fixture(scope="session")
def rest_api(rest_base_url):
    """提供依環境切換的 RestAPI 實例。"""
    # 若你的 RestAPI 仍是不帶參數版本，可改為 return RestAPI()
    return RestAPI(base_url=rest_base_url)


@pytest.fixture(scope="session")
def instrument_name(pytestconfig):
    """命令列優先，否則使用環境變數預設。"""
    return pytestconfig.getoption("--instrument") or DEFAULT_INSTRUMENT


# ---- 測資與 timeframe 轉換 ----
@pytest.fixture(scope="session")
def td():
    return JSON_DATA["TEST_DATA_REST_CANDLESTICK"]


@pytest.fixture(scope="session")
def alias(td):
    """timeframe 別名表：新制 -> legacy（例如 5m -> M5）。"""
    return td.get("aliases", {})


def _normalize_tf(tf: str, alias_map: dict) -> str:
    """將 5m/1h/1D 轉換為 M5/H1/D1；找不到就原樣回傳。"""
    return alias_map.get(tf, tf)


@pytest.fixture(scope="session")
def norm_tf(alias):
    """呼叫方式：norm_tf('5m') -> 'M5'"""
    return lambda tf: _normalize_tf(tf, alias)


# 若之後需要自動參數化，可在此擴充
def pytest_generate_tests(metafunc):
    pass
