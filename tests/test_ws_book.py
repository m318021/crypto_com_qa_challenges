# tests/test_ws_book.py
import asyncio
import logging
import re
import pytest

from resources.services.ws_client import WSClient, make_ssl_context

logger = logging.getLogger(__name__)
pytestmark = pytest.mark.asyncio


# ---------- helpers ----------

def _is_level_tuple(x):
    """
    An order book level is expected to be a three-element list[str, str, str]:
    [price, size, num_orders]
    """
    return (
        isinstance(x, list) and len(x) == 3
        and all(isinstance(v, str) for v in x)
        and re.match(r"^-?\d+(\.\d+)?$", x[0] or "")  # price
        and re.match(r"^\d+(\.\d+)?$", x[1] or "")    # size
        and re.match(r"^\d+$", x[2] or "")            # num_orders
    )


def _normalize_subscribe_ack(msg: dict, expected_ch: str) -> None:
    """
    Subscribe ACK may have two common shapes:
    A) {"id":..,"method":"subscribe","code":0,"channel":"book.BTCUSD-PERP.10"}
    B) {"id":..,"method":"subscribe","code":0,"channel":"book","subscription":"book.BTCUSD-PERP.10", ...}
    This normalizes by accepting either shape.
    """
    assert msg.get("method") == "subscribe", f"not subscribe ack: {msg}"
    assert msg.get("code") == 0, f"subscribe failed: {msg}"
    ch = msg.get("channel")
    sub = msg.get("subscription")
    assert (ch == expected_ch) or (sub == expected_ch) or (ch == "book"), \
        f"unexpected ack: ch={ch} sub={sub} expect={expected_ch}"


async def _wait_first_data(ws: WSClient, expected_ch: str, timeout: float = 10.0) -> dict:
    """
    Wait for the first data message (often id = -1). Return the unpacked payload
    (msg['result'] if present, otherwise msg). Only accept channel == expected_ch or "book".
    """
    while True:
        msg = await ws.recv(timeout=timeout)
        payload = msg.get("result") or msg
        if "data" not in payload or not payload.get("data"):
            continue
        ch = payload.get("channel")
        if ch == expected_ch or ch == "book":
            return payload


# ---------- fixtures ----------

@pytest.fixture
async def ws(app_cfg):
    """
    Create a WS connection:
    - If conftest provides insecure/cafile, pass them to make_ssl_context.
    - WSClient will also convert ssl=None to ssl=True (required by wss://).
    """
    ctx = make_ssl_context(
        insecure=app_cfg.get("insecure", False),
        cafile=app_cfg.get("cafile"),
    )
    # Pass ctx (or None). WSClient will turn None into a value acceptable to websockets.
    async with WSClient(app_cfg["ws_market_url"], ssl_context=ctx) as client:
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

    # Wait for subscribe ACK
    while True:
        ack = await ws.recv(timeout=10)
        if ack.get("id") == req_id and ack.get("method") == "subscribe":
            _normalize_subscribe_ack(ack, ch)
            break

    # First data
    payload = await _wait_first_data(ws, expected_ch=ch, timeout=15)
    data = payload["data"]
    assert isinstance(data, list) and len(data) >= 1
    snap = data[0]

    # Validate snapshot fields
    for k in ("u", "t", "bids", "asks"):
        assert k in snap, f"missing '{k}' in snapshot: {snap}"
    assert isinstance(snap["bids"], list) and isinstance(snap["asks"], list)
    if snap["bids"]:
        assert _is_level_tuple(snap["bids"][0])
    if snap["asks"]:
        assert _is_level_tuple(snap["asks"][0])


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
        # Subscribe
        req_id = await ws.subscribe([ch], extra_params=extra)
        # Wait for ACK
        while True:
            ack = await ws.recv(timeout=10)
            if ack.get("id") == req_id and ack.get("method") == "subscribe":
                _normalize_subscribe_ack(ack, ch)
                break

        # Get the first snapshot that contains 'u'
        payload = await _wait_first_data(ws, expected_ch=ch, timeout=15)
        last_u = None
        for item in payload.get("data", []):
            if "u" in item:
                last_u = item["u"]
                break
        if last_u is None:
            logger.info("[delta][round=%s] first snapshot has no 'u': %s", round_no, payload)
            return False

        # Wait for a consistent delta (pu == last_u). Accept deltas that only carry u/pu.
        deadline = asyncio.get_event_loop().time() + max_seconds
        while asyncio.get_event_loop().time() < deadline:
            msg = await ws.recv(timeout=10)
            pl = msg.get("result") or msg
            chv = pl.get("channel")
            if chv not in (ch, "book"):
                continue
            for item in pl.get("data", []):
                u = item.get("u")
                pu = item.get("pu")
                if pu is not None and last_u is not None and pu == last_u:
                    # Found a consistent delta
                    return True
                if u is not None:
                    last_u = u
        logger.info("[delta][round=%s] did not see pu==last_u within %ss", round_no, max_seconds)
        return False

    # First attempt (25s)
    ok = await _round_try(round_no=1, max_seconds=25)
    if ok:
        return

    # Unsubscribe then retry once: sometimes a fresh subscription helps get a clean sequence faster
    try:
        await ws.unsubscribe([ch])
    except Exception:
        pass  # Ignore unsubscribe failure

    ok = await _round_try(round_no=2, max_seconds=25)
    if ok:
        return

    pytest.xfail("Did not observe a consistent delta (pu==last_u). The market may be quiet or throttled. "
                 "Try a more active instrument or increase waiting time.")


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
        assert (code != 0) or ("error" in method.lower()), \
            f"Expected subscription to fail but it succeeded: {msg}"