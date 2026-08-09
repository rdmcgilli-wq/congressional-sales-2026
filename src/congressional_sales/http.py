"""Shared HTTP client: per-host token bucket, retries. Every source module
goes through get_json/get_text so rate limiting is enforced in one place."""

from __future__ import annotations

import threading
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import DEFAULT_RATE_LIMIT, RATE_LIMITS, USER_AGENT

_lock = threading.Lock()
_last_call: dict[str, float] = {}


class RateLimitedError(RuntimeError):
    """429/5xx from upstream -- retryable."""


def _throttle(host: str) -> None:
    rate = RATE_LIMITS.get(host, DEFAULT_RATE_LIMIT)
    min_gap = 1.0 / rate
    with _lock:
        now = time.monotonic()
        wait = min_gap - (now - _last_call.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        _last_call[host] = time.monotonic()


_client: httpx.Client | None = None


def client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
        )
    return _client


@retry(
    retry=retry_if_exception_type((RateLimitedError, httpx.TransportError)),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(4),
    reraise=True,
)
def _request(url: str, params: dict[str, Any] | None, headers: dict[str, str] | None) -> httpx.Response:
    host = urlparse(url).netloc
    _throttle(host)
    resp = client().get(url, params=params, headers=headers)
    if resp.status_code == 429 or resp.status_code >= 500:
        raise RateLimitedError(f"{resp.status_code} from {host}")
    resp.raise_for_status()
    return resp


def get_json(url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    return _request(url, params, headers).json()


def get_text(url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> str:
    return _request(url, params, headers).text


def get_bytes(url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> bytes:
    return _request(url, params, headers).content
