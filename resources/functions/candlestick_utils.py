from decimal import Decimal
from helpers.config_manager import JSON_DATA

TD = JSON_DATA["TEST_DATA_REST_CANDLESTICK"]
ALIASES = TD.get("aliases", {})


def norm_tf(tf: str) -> str:
    """Convert 5m/1h/1D into M5/H1/D1; if no mapping found, return original value"""
    return ALIASES.get(tf, tf)


# ---- interval mapping (milliseconds) ----
_INTERVAL_MS = {
    "M1": 60 * 1000,
    "M5": 5 * 60 * 1000,
    "M15": 15 * 60 * 1000,
    "M30": 30 * 60 * 1000,
    "H1": 60 * 60 * 1000,
    "H2": 2 * 60 * 60 * 1000,
    "H4": 4 * 60 * 60 * 1000,
    "H12": 12 * 60 * 60 * 1000,
    "D1": 24 * 60 * 60 * 1000,
    "D7": 7 * 24 * 60 * 60 * 1000,
    "D14": 14 * 24 * 60 * 60 * 1000,
    # Month candle length is not fixed; use 30 days approximation
    # and allow one interval tolerance in time-window validation
    "1M": 30 * 24 * 60 * 60 * 1000,
}


def interval_ms(timeframe_norm: str) -> int:
    """Convert normalized timeframe (M5/H1/D1/1M) into milliseconds; fallback = 60s"""
    return _INTERVAL_MS.get(timeframe_norm, 60 * 1000)


# --- small helpers ---
def D(x):
    return Decimal(str(x))


def assert_ohlc_ok(c):
    o, h, l, v, cl = D(c["o"]), D(c["h"]), D(c["l"]), D(c["v"]), D(c["c"])
    assert h >= l, f"h({h}) < l({l})"
    assert h >= o >= l, f"o({o}) not in [{l},{h}]"
    assert h >= cl >= l, f"c({cl}) not in [{l},{h}]"
    assert v >= 0, f"v({v}) < 0"


def assert_sorted_by_t(data):
    ts = [int(x["t"]) for x in data]
    assert ts == sorted(ts), "timestamps not ascending"


def extract_result(body: dict) -> dict:
    """
    Handle both API result formats:
    1) {"result": {...}}
    2) {"result": [{...}]}
    """
    r = body.get("result")
    if isinstance(r, list):
        assert len(r) > 0, f"empty result list: {body}"
        return r[0]
    if isinstance(r, dict):
        return r
    raise AssertionError(f"unexpected result type: {type(r)}; body={body}")


def assert_time_in_window_with_alignment(t_ms: int, start_ts: int, end_ts: int, tf_ms: int):
    """
    Allow alignment offset: t can be earlier than start_ts by one timeframe
    (aligned to the candle open time).
    """
    lower = start_ts - tf_ms
    assert lower <= t_ms <= end_ts, f"t={t_ms} out of [{start_ts}, {end_ts}] (allowing -{tf_ms}ms alignment)"


# --- test data prepared as list[tuple] for parametrize ---
VALID_CASES = [tuple(x) for x in TD["valid_cases"]]
TIME_RANGE_CASES = [tuple(x) for x in TD["time_range_cases"]]
