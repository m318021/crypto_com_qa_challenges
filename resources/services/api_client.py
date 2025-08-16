import logging
from time import perf_counter
from typing import Any, Mapping, MutableMapping, Optional, Tuple, Union

import requests
from requests.adapters import HTTPAdapter
from urllib.parse import urljoin
from urllib3.util.retry import Retry
from urllib3.exceptions import InsecureRequestWarning
import urllib3

logger = logging.getLogger(__name__)


class APIError(requests.HTTPError):
    """Raised for unexpected HTTP responses from the API."""

    pass


class APIClient:
    def __init__(
        self,
        server: str,
        *,
        default_status: int = 200,
        retry_total: int = 8,
        backoff_factor: float = 0.5,
        status_forcelist: Tuple[int, ...] = (429, 500, 502, 503, 504),
        timeout: Union[float, Tuple[float, float]] = (5, 30),  # (connect, read)
        verify_ssl: bool = True,
        default_headers: Optional[Mapping[str, str]] = None,
        auth: Optional[requests.auth.AuthBase] = None,
        user_agent: str = "APIClient/1.0 (+requests)",
        proxies: Optional[Mapping[str, str]] = None,
    ) -> None:
        self.server = server if server.endswith("/") else server + "/"
        self.default_status = default_status
        self.timeout = timeout
        self.verify_ssl = verify_ssl

        retry = Retry(
            total=retry_total,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
            allowed_methods={"HEAD", "GET", "OPTIONS", "POST", "PUT", "DELETE", "PATCH"},
            raise_on_status=False,
            respect_retry_after_header=True,
        )

        self.session = requests.Session()
        adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=50)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.session.headers.update({"User-Agent": user_agent})
        if default_headers:
            self.session.headers.update(default_headers)
        if proxies:
            self.session.proxies.update(proxies)
        if auth:
            self.session.auth = auth

    def get(self, path: str, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs):
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs):
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs):
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs):
        return self.request("DELETE", path, **kwargs)

    def request(
        self,
        method: str,
        path: str = "/",
        *,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
        cookies: Optional[MutableMapping[str, str]] = None,
        json: Optional[Any] = None,
        data: Optional[Union[Mapping[str, Any], bytes]] = None,
        files: Optional[Mapping[str, Any]] = None,
        check_status: bool = True,
        expected_status: Optional[int] = None,
        return_json: bool = False,
        timeout: Optional[Union[float, Tuple[float, float]]] = None,
        stream: bool = False,
    ):

        url = urljoin(self.server, path.lstrip("/"))
        expected = expected_status if expected_status is not None else self.default_status
        timeout = timeout if timeout is not None else self.timeout

        if not self.verify_ssl:
            urllib3.disable_warnings(InsecureRequestWarning)

        start = perf_counter()
        try:
            resp = self.session.request(
                method=method.upper(),
                url=url,
                params=params,
                headers=headers,
                cookies=cookies,
                json=json if json is not None else None,
                data=None if json is not None else data,  # prefer JSON payloads
                files=files,
                timeout=timeout,
                verify=self.verify_ssl,
                stream=stream,
            )
        except requests.RequestException as e:
            elapsed_ms = int((perf_counter() - start) * 1000)
            logger.error("HTTP %s %s failed in %dms: %s", method.upper(), path, elapsed_ms, e)
            raise

        elapsed_ms = int((perf_counter() - start) * 1000)
        logger.debug(
            "HTTP %s %s -> %s in %dms",
            method.upper(),
            resp.request.path_url,
            resp.status_code,
            elapsed_ms,
        )

        if check_status and resp.status_code != expected:
            # Attach response text for easier debugging
            msg = f"Unexpected status {resp.status_code} (expected {expected}) " f"for {method.upper()} {resp.request.path_url}: {resp.text[:1000]}"
            err = APIError(msg, response=resp)
            logger.warning(msg)
            raise err

        if return_json:
            # Will raise ValueError if body is not JSON
            return resp.json()
        return resp

    def close(self) -> None:
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
