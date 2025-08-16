import asyncio
import logging
import re
from typing import Any, Dict, Iterable, Optional
from resources.services.ws_client import WSClient, make_ssl_context

logger = logging.getLogger(__name__)

# ---------- shape & parsing helpers ----------


def is_level_tuple(x: Any) -> bool:
    """
    Order book level is a three-element list[str, str, str]: [price, size, num_orders]
    """
    return (
        isinstance(x, list)
        and len(x) == 3
        and all(isinstance(v, str) for v in x)
        and re.match(r"^-?\d+(\.\d+)?$", x[0] or "")  # price
        and re.match(r"^\d+(\.\d+)?$", x[1] or "")  # size
        and re.match(r"^\d+$", x[2] or "")  # num_orders
    )


def assert_subscribe_ack(msg: Dict[str, Any], expected_ch: str) -> None:
    """
    Subscribe ACK may have two shapes:
      A) {"id":..,"method":"subscribe","code":0,"channel":"book.BTCUSD-PERP.10"}
      B) {"id":..,"method":"subscribe","code":0,"channel":"book","subscription":"book.BTCUSD-PERP.10", ...}
    Accept either shape.
    """
    assert msg.get("method") == "subscribe", f"not subscribe ack: {msg}"
    assert msg.get("code") == 0, f"subscribe failed: {msg}"
    ch = msg.get("channel")
    sub = msg.get("subscription")
    assert (ch == expected_ch) or (sub == expected_ch) or (ch == "book"), f"unexpected ack: ch={ch} sub={sub} expect={expected_ch}"


async def wait_first_data(ws: WSClient, expected_ch: str, timeout: float = 10.0) -> Dict[str, Any]:
    """
    Wait for the first data message (often id = -1).
    Return the unpacked payload (msg['result'] if present, otherwise msg).
    Only accept channel == expected_ch or "book".
    """
    while True:
        msg = await ws.recv(timeout=timeout)
        payload = msg.get("result") or msg
        if "data" not in payload or not payload.get("data"):
            continue
        ch = payload.get("channel")
        if ch == expected_ch or ch == "book":
            return payload


async def wait_subscribe_ack(ws: WSClient, req_id: int, expected_ch: str, timeout: float = 10.0) -> None:
    """Block until we see the subscribe ACK for the given request id."""
    while True:
        ack = await ws.recv(timeout=timeout)
        if ack.get("id") == req_id and ack.get("method") == "subscribe":
            assert_subscribe_ack(ack, expected_ch)
            return


async def find_consistent_delta(ws: WSClient, channels: Iterable[str], last_u: Optional[int], max_seconds: float) -> bool:
    """
    Search for a delta where pu == last_u (allow updates that only carry u/pu).
    Return True if found within max_seconds; otherwise False.
    """
    deadline = asyncio.get_event_loop().time() + max_seconds
    channels = set(channels)
    while asyncio.get_event_loop().time() < deadline:
        msg = await ws.recv(timeout=10)
        payload = msg.get("result") or msg
        chv = payload.get("channel")
        if chv not in channels and chv != "book":
            continue
        for item in payload.get("data", []):
            u = item.get("u")
            pu = item.get("pu")
            if pu is not None and last_u is not None and pu == last_u:
                return True
            if u is not None:
                last_u = u
    return False


# ---------- fixtures factory ----------


async def ws_client_from_app_cfg(app_cfg) -> WSClient:
    """
    Create a WSClient using cafile/insecure options from app_cfg.
    WSClient internally converts ssl=None to ssl=True for wss://.
    """
    ctx = make_ssl_context(
        insecure=app_cfg.get("insecure", False),
        cafile=app_cfg.get("cafile"),
    )
    return WSClient(app_cfg["ws_market_url"], ssl_context=ctx)
