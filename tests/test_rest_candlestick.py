import time
import pytest
from resources.services.api_client import APIError
from resources.functions.candlestick_utils import TD
from resources.functions.candlestick_utils import (
    norm_tf,
    interval_ms,
    assert_ohlc_ok,
    assert_sorted_by_t,
    extract_result,
    assert_time_in_window_with_alignment,
)
from helpers.test_data_loader import VALID_CASES, TIME_RANGE_CASES

# Positive Cases
@pytest.mark.parametrize("tf_str,count", VALID_CASES)
def test_valid_cases(rest_api, instrument_name, tf_str, count):
    timeframe = norm_tf(tf_str)
    resp = rest_api.get_candlestick({"instrument_name": instrument_name, "timeframe": timeframe, "count": count})
    assert resp.status_code == 200, f"unexpected http {resp.status_code}, body={resp.text}"
    body = resp.json()
    assert body.get("code") == 0, f"unexpected code: {body}"

    result = extract_result(body)
    assert result["interval"] == timeframe

    data = result["data"]
    assert 0 < len(data) <= count
    assert_sorted_by_t(data)
    for c in data:
        for k in ("t", "o", "h", "l", "c", "v"):
            assert k in c, f"missing key {k}"
        assert_ohlc_ok(c)


# Recent 1-hour window (allowing 1 timeframe misalignment tolerance)
@pytest.mark.parametrize("tf_str,count", TIME_RANGE_CASES)
def test_time_window_recent_hour(rest_api, instrument_name, tf_str, count):
    end_ts = int(time.time() * 1000)
    start_ts = end_ts - 60 * 60 * 1000
    timeframe = norm_tf(tf_str)

    resp = rest_api.get_candlestick(
        {"instrument_name": instrument_name, "timeframe": timeframe, "start_ts": start_ts, "end_ts": end_ts, "count": count}
    )
    assert resp.status_code == 200, f"unexpected http {resp.status_code}, body={resp.text}"
    body = resp.json()
    assert body.get("code") == 0, f"unexpected code: {body}"

    data = extract_result(body)["data"]
    assert_sorted_by_t(data)
    tf_ms = interval_ms(timeframe)
    for c in data:
        t = int(c["t"])
        assert_time_in_window_with_alignment(t, start_ts, end_ts, tf_ms)
        assert_ohlc_ok(c)


# Large count boundary (actual upper limit depends on server behavior: only assert <= requested count)
def test_large_count_limit(rest_api, instrument_name):
    case = TD["limits"]["large_count"]
    timeframe = norm_tf(case["timeframe"])

    resp = rest_api.get_candlestick({"instrument_name": instrument_name, "timeframe": timeframe, "count": case["count"]})
    assert resp.status_code == 200, f"unexpected http {resp.status_code}, body={resp.text}"
    body = resp.json()
    assert body.get("code") == 0, f"unexpected code: {body}"

    data = extract_result(body)["data"]
    assert 0 < len(data) <= case["count"]

# Negative Cases
@pytest.mark.negative
def test_invalid_timeframe(rest_api, instrument_name):
    # Expect HTTP 400, APIClient should raise APIError
    case = TD["negatives"]["invalid_timeframe"]
    with pytest.raises(APIError) as e:
        rest_api.get_candlestick(
            {
                "instrument_name": instrument_name,
                "timeframe": case["timeframe"],
                "count": case["count"],
            }
        )
    # Message may vary by environment, so check by keyword
    assert "Invalid request" in str(e.value) or "400" in str(e.value)


@pytest.mark.negative
def test_count_zero(rest_api, instrument_name):
    # Expect HTTP 400, APIClient should raise APIError
    case = TD["negatives"]["count_zero"]
    timeframe = norm_tf(case["timeframe"])
    with pytest.raises(APIError) as e:
        rest_api.get_candlestick(
            {
                "instrument_name": instrument_name,
                "timeframe": timeframe,
                "count": case["count"],
            }
        )
    assert "Count must be positive" in str(e.value) or "400" in str(e.value)


@pytest.mark.negative
def test_start_after_end(rest_api, instrument_name):
    """
    In some environments, this scenario returns 200 + code=0 + data=[].
    So the condition "empty data" is considered as pass.
    """
    case = TD["negatives"]["start_after_end"]
    timeframe = norm_tf(case["timeframe"])
    now = int(time.time() * 1000)
    start_ts, end_ts = now, now - 3600_000  # intentionally inverted

    resp = rest_api.get_candlestick(
        {
            "instrument_name": instrument_name,
            "timeframe": timeframe,
            "count": case["count"],
            "start_ts": start_ts,
            "end_ts": end_ts,
        }
    )
    # Do not force http code check; just ensure body is valid and data is empty
    body = resp.json()
    # Some environments still return code=0
    assert "result" in body, f"unexpected body: {body}"
    result = extract_result(body)
    assert "data" in result
    assert result["data"] == [], f"expected empty data, got {result['data']}"


@pytest.mark.negative
def test_invalid_instrument(rest_api):
    """
    Some environments return 400 (APIError),
    others return 200 + code != 0 or data=[].
    Both are acceptable.
    """
    bad = TD["negatives"]["invalid_instrument_literal"]
    try:
        resp = rest_api.get_candlestick(
            {
                "instrument_name": bad,
                "timeframe": "M5",
                "count": 5,
            }
        )
    except APIError as e:
        # 400 case: considered pass
        assert "400" in str(e) or "Invalid" in str(e)
        return

    # If no exception raised -> validate response body
    body = resp.json()
    if body.get("code", 1) != 0:
        assert body["code"] != 0  # non-zero means error (pass)
    else:
        # code=0 but data might be empty (also acceptable)
        result = extract_result(body)
        assert result.get("data", []) == []


# Additional negative case (direct invalid instrument test)
@pytest.mark.negative
def test_invalid_instrument_direct(rest_api, instrument_name="ETHUSD-PERP111"):
    """
    Directly test an invalid instrument (ETHUSD-PERP111).
    Expect either APIError(400) or code != 0 in response.
    """
    bad_instrument = "ETHUSD-PERP111"
    try:
        resp = rest_api.get_candlestick(
            {
                "instrument_name": bad_instrument,
                "timeframe": "M5",
                "count": 25,
            }
        )
    except APIError as e:
        # Expected: server returns HTTP 400
        assert "400" in str(e) or "Invalid" in str(e)
        return

    # If API did not raise, check response body
    body = resp.json()
    assert body.get("code", 1) != 0, f"unexpected success: {body}"
