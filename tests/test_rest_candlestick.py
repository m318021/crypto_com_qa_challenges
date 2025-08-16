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


# ======================
#        正向案例
# ======================
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


# 最近一小時窗口（允許對齊誤差一個 timeframe）
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


# 大 count 邊界（實際上限以服務行為為準：只斷言 <= 要求值）
def test_large_count_limit(rest_api, instrument_name):
    case = TD["limits"]["large_count"]
    timeframe = norm_tf(case["timeframe"])

    resp = rest_api.get_candlestick({"instrument_name": instrument_name, "timeframe": timeframe, "count": case["count"]})
    assert resp.status_code == 200, f"unexpected http {resp.status_code}, body={resp.text}"
    body = resp.json()
    assert body.get("code") == 0, f"unexpected code: {body}"

    data = extract_result(body)["data"]
    assert 0 < len(data) <= case["count"]


# ======================
#        負向案例
# ======================
@pytest.mark.negative
def test_invalid_timeframe(rest_api, instrument_name):
    # 預期 400，APIClient 會 raise APIError
    case = TD["negatives"]["invalid_timeframe"]
    with pytest.raises(APIError) as e:
        rest_api.get_candlestick(
            {
                "instrument_name": instrument_name,
                "timeframe": case["timeframe"],
                "count": case["count"],
            }
        )
    # 訊息可能因環境略異，做關鍵字比對
    assert "Invalid request" in str(e.value) or "400" in str(e.value)


@pytest.mark.negative
def test_count_zero(rest_api, instrument_name):
    # 預期 400，APIClient 會 raise APIError
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
    此情境在部分環境會回 200 + code=0 + data=[]
    因此以「空資料」為通過條件。
    """
    case = TD["negatives"]["start_after_end"]
    timeframe = norm_tf(case["timeframe"])
    now = int(time.time() * 1000)
    start_ts, end_ts = now, now - 3600_000  # 故意顛倒

    resp = rest_api.get_candlestick(
        {
            "instrument_name": instrument_name,
            "timeframe": timeframe,
            "count": case["count"],
            "start_ts": start_ts,
            "end_ts": end_ts,
        }
    )
    # 不強制檢查 http code；只要 body 正確且 data 為空即可
    body = resp.json()
    # 有些環境仍會回 0
    assert "result" in body, f"unexpected body: {body}"
    result = extract_result(body)
    assert "data" in result
    assert result["data"] == [], f"expected empty data, got {result['data']}"


@pytest.mark.negative
def test_invalid_instrument(rest_api):
    """
    有的環境會回 400（APIError），有的回 200 + code != 0 或 data=[]。
    兩者皆接受。
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
        # 400 情境：視為通過
        assert "400" in str(e) or "Invalid" in str(e)
        return

    # 沒丟例外 -> 驗證回傳內文
    body = resp.json()
    if body.get("code", 1) != 0:
        assert body["code"] != 0  # 非 0 視為錯誤（通過）
    else:
        # code=0 但 data 可能為空（也接受）
        result = extract_result(body)
        assert result.get("data", []) == []
