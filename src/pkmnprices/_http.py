from __future__ import annotations

import asyncio
import random
import time
from typing import Any

import httpx

from ._endpoints import Request
from .errors import (
    APIConnectionError,
    PkmnPricesError,
    RateLimitError,
    RateLimitInfo,
    create_api_error,
)

_RETRYABLE_STATUS = {500, 502, 503, 504}
_BASE_BACKOFF = 0.5
_MAX_BACKOFF = 8.0


def _int_header(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _rate_limit(headers: httpx.Headers) -> RateLimitInfo:
    return RateLimitInfo(
        credits_charged=_int_header(headers.get("x-credits-charged")),
        credits_limit=_int_header(headers.get("x-credits-limit")),
        rate_limit=_int_header(headers.get("x-rate-limit")),
        rate_remaining=_int_header(headers.get("x-rate-remaining")),
    )


def _retry_after(headers: httpx.Headers) -> float | None:
    raw = headers.get("retry-after")
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _handle(response: httpx.Response, path: str) -> Any:
    rate_limit = _rate_limit(response.headers)

    if response.is_success:
        if not response.content:
            return None
        return response.json()

    body: Any = None
    try:
        body = response.json()
    except ValueError:
        body = None

    has_error = isinstance(body, dict) and isinstance(body.get("error"), dict)
    code = body["error"]["code"] if has_error else "unknown"
    message = (
        body["error"]["message"]
        if has_error
        else f"Request to {path} failed with status {response.status_code}"
    )

    raise create_api_error(
        status=response.status_code,
        code=code,
        message=message,
        rate_limit=rate_limit,
        retry_after=_retry_after(response.headers),
    )


def _is_retryable(error: Exception) -> bool:
    if isinstance(error, (RateLimitError, APIConnectionError)):
        return True
    if isinstance(error, PkmnPricesError):
        return error.status in _RETRYABLE_STATUS
    return False


def _backoff(attempt: int, retry_after: float | None) -> float:
    if retry_after is not None:
        return retry_after

    exponential = _BASE_BACKOFF * 2**attempt
    jitter = exponential * 0.25 * random.random()
    return min(exponential + jitter, _MAX_BACKOFF)


class _BaseTransport:
    def __init__(self, api_key: str | None, max_retries: int) -> None:
        self._api_key = api_key
        self._max_retries = max_retries

    def _headers(self, request: Request) -> dict[str, str]:
        headers = {"accept": "application/json"}
        if request.auth:
            if not self._api_key:
                raise APIConnectionError(
                    "This endpoint requires an API key. Set api_key on the client."
                )
            headers["x-api-key"] = self._api_key
        return headers


class SyncTransport(_BaseTransport):
    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        max_retries: int,
        timeout: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(api_key, max_retries)
        self._client = httpx.Client(base_url=base_url, timeout=timeout, transport=transport)

    def request(self, request: Request) -> Any:
        attempt = 0
        while True:
            try:
                return self._attempt(request)
            except Exception as error:
                retryable = attempt < self._max_retries and _is_retryable(error)
                if not retryable:
                    raise

                retry_after = error.retry_after if isinstance(error, PkmnPricesError) else None
                time.sleep(_backoff(attempt, retry_after))
                attempt += 1

    def _attempt(self, request: Request) -> Any:
        try:
            response = self._client.request(
                request.method, request.path, params=request.query, headers=self._headers(request)
            )
        except httpx.TimeoutException as error:
            raise APIConnectionError(f"Request to {request.path} timed out", error) from error
        except httpx.HTTPError as error:
            raise APIConnectionError(f"Request to {request.path} failed", error) from error

        return _handle(response, request.path)

    def close(self) -> None:
        self._client.close()


class AsyncTransport(_BaseTransport):
    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        max_retries: int,
        timeout: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(api_key, max_retries)
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, transport=transport)

    async def request(self, request: Request) -> Any:
        attempt = 0
        while True:
            try:
                return await self._attempt(request)
            except Exception as error:
                retryable = attempt < self._max_retries and _is_retryable(error)
                if not retryable:
                    raise

                retry_after = error.retry_after if isinstance(error, PkmnPricesError) else None
                await asyncio.sleep(_backoff(attempt, retry_after))
                attempt += 1

    async def _attempt(self, request: Request) -> Any:
        try:
            response = await self._client.request(
                request.method, request.path, params=request.query, headers=self._headers(request)
            )
        except httpx.TimeoutException as error:
            raise APIConnectionError(f"Request to {request.path} timed out", error) from error
        except httpx.HTTPError as error:
            raise APIConnectionError(f"Request to {request.path} failed", error) from error

        return _handle(response, request.path)

    async def close(self) -> None:
        await self._client.aclose()
