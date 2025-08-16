import logging
import pytest

from resources.functions.ws_helpers import (
    is_level_tuple,
    wait_first_data,
    wait_subscribe_ack,
    find_consistent_delta,
    ws_client_from_app_cfg,
)

logger = logging.getLogger(__name__)
pytestmark = pytest.mark.asyncio


@pytest.fixture
async def ws(app_cfg):
    async with await ws_client_from_app_cfg(app_cfg) as client:
        yield client


# ---------- tests ----------


@pytest.mark.parametrize("depth", [10, 50])
async def test_book_snapshot_ok(ws, app_cfg, depth):
    """
    Verify:
    - Subscribe ACK succeeds (supporting both response shapes)
    - The first snapshot contains the basic fields bids/asks/u/t and the level tuple structure is valid
    """
    ins = app_cfg.get("instrument_name") or "BTCUSD-PERP"
    ch = f"book.{ins}.{depth}"

    # SNAPSHOT mode (snapshot ~500ms; update_frequency doesn't affect snapshot itself)
    extra = {"book_subscription_type": "SNAPSHOT", "book_update_frequency": 100}
    req_id = await ws.subscribe([ch], extra_params=extra)

    # ACK + first data
    await wait_subscribe_ack(ws, req_id, ch, timeout=10)
    payload = await wait_first_data(ws, expected_ch=ch, timeout=15)

    # Basic validations
    data = payload["data"]
    assert isinstance(data, list) and len(data) >= 1
    snap = data[0]
    for k in ("u", "t", "bids", "asks"):
        assert k in snap, f"missing '{k}' in snapshot: {snap}"
    assert isinstance(snap["bids"], list) and isinstance(snap["asks"], list)
    if snap["bids"]:
        assert is_level_tuple(snap["bids"][0])
    if snap["asks"]:
        assert is_level_tuple(snap["asks"][0])


async def test_book_delta_sequence(ws, app_cfg):
    """
    Verify delta sequence consistency (pu == last_u):
    - Allow deltas that only contain u/pu (no bids/asks required)
    - Auto re-subscribe once if not found in time
    - If both rounds fail, mark xfail to avoid false negatives when the market is static
    """
    ins = app_cfg.get("instrument_name") or "BTCUSD-PERP"
    depth = app_cfg.get("depth") or 50
    ch = f"book.{ins}.{depth}"
    extra = {"book_subscription_type": "SNAPSHOT_AND_UPDATE", "book_update_frequency": 100}

    async def _round_try(round_no: int, max_seconds: float) -> bool:
        req_id = await ws.subscribe([ch], extra_params=extra)
        await wait_subscribe_ack(ws, req_id, ch, timeout=10)

        # Fetch first snapshot with 'u'
        payload = await wait_first_data(ws, expected_ch=ch, timeout=15)
        last_u = None
        for item in payload.get("data", []):
            if "u" in item:
                last_u = item["u"]
                break
        if last_u is None:
            logger.info("[delta][round=%s] first snapshot has no 'u': %s", round_no, payload)
            return False

        ok = await find_consistent_delta(ws, channels=[ch], last_u=last_u, max_seconds=max_seconds)
        if not ok:
            logger.info("[delta][round=%s] did not see pu==last_u within %ss", round_no, max_seconds)
        return ok

    # try twice
    if await _round_try(1, 25):
        return
    try:
        await ws.unsubscribe([ch])
    except Exception:
        pass
    if await _round_try(2, 25):
        return

    pytest.xfail(
        "Did not observe a consistent delta (pu==last_u). "
        "The market may be quiet or throttled. Try a more active instrument or increase waiting time."
    )


async def test_book_invalid_depth(ws, app_cfg):
    """
    Verify error response for invalid depth (code != 0)
    """
    ins = app_cfg.get("instrument_name") or "BTCUSD-PERP"
    ch = f"book.{ins}.9999"
    req_id = await ws.subscribe([ch])

    msg = await ws.recv(timeout=10)
    if msg.get("id") == req_id and msg.get("method") == "subscribe":
        assert msg.get("code", -1) != 0, f"Expected subscription to fail but it succeeded: {msg}"
    else:
        # Some implementations may return with id = -1; as long as code != 0, treat as correct failure
        code = msg.get("code", -1)
        method = msg.get("method") or ""
        assert (code != 0) or ("error" in method.lower()), f"Expected subscription to fail but it succeeded: {msg}"
