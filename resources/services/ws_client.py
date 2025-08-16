import asyncio
import json
import time
import logging
import ssl
import websockets

try:
    import certifi
except Exception:
    certifi = None

logger = logging.getLogger(__name__)


def make_ssl_context(insecure: bool = False, cafile: str | None = None) -> ssl.SSLContext | None:
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    if cafile:
        return ssl.create_default_context(cafile=cafile)
    if certifi:
        return ssl.create_default_context(cafile=certifi.where())
    # return None  # ← Allow returning None, but __aenter__ will convert it to True
    return None


class WSClient:
    def __init__(self, url: str, connect_sleep_secs: float = 1.0, ssl_context: ssl.SSLContext | None = None):
        self.url = url
        self.ws = None
        self.connect_sleep_secs = connect_sleep_secs
        self._recv_task = None
        self._msg_queue = asyncio.Queue()
        self._running = False
        self.ssl_context = ssl_context

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)

    async def __aenter__(self):
        # 🔐 Key point: if using wss:// and ssl_context is None, set it to True (let websockets auto-create one)
        ssl_param = self.ssl_context if self.ssl_context is not None else True
        self.ws = await websockets.connect(self.url, ping_interval=None, ssl=ssl_param)
        await asyncio.sleep(self.connect_sleep_secs)
        self._running = True
        self._recv_task = asyncio.create_task(self._recv_loop())
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._running = False
        if self._recv_task:
            self._recv_task.cancel()
        if self.ws:
            await self.ws.close()

    async def _recv_loop(self):
        try:
            while self._running:
                raw = await self.ws.recv()
                msg = json.loads(raw)
                if msg.get("method") == "public/heartbeat":
                    await self.respond_heartbeat(msg.get("id"))
                else:
                    await self._msg_queue.put(msg)
        except asyncio.CancelledError:
            pass

    async def respond_heartbeat(self, hb_id: int):
        await self.ws.send(json.dumps({"id": hb_id, "method": "public/respond-heartbeat"}))

    async def subscribe(self, channels, extra_params: dict | None = None, req_id: int | None = None):
        if req_id is None:
            req_id = self._now_ms()
        params = {"channels": channels}
        if extra_params:
            params.update(extra_params)
        await self.ws.send(json.dumps({"id": req_id, "method": "subscribe", "params": params, "nonce": self._now_ms()}))
        return req_id

    async def unsubscribe(self, channels, req_id: int | None = None):
        if req_id is None:
            req_id = self._now_ms()
        await self.ws.send(json.dumps({"id": req_id, "method": "unsubscribe", "params": {"channels": channels}, "nonce": self._now_ms()}))
        return req_id

    async def recv(self, timeout: float | None = None):
        return await asyncio.wait_for(self._msg_queue.get(), timeout=timeout)