from __future__ import annotations

import asyncio
import random
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
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
        credits_remaining=_int_header(headers.get("x-credits-remaining")),
        credits_reset=_int_header(headers.get("x-credits-reset")),
        credits_balance=_int_header(headers.get("x-credits-balance")),
        rate_limit=_int_header(headers.get("x-rate-limit")),
        rate_remaining=_int_header(headers.get("x-rate-remaining")),
        rate_reset=_int_header(headers.get("x-rate-reset")),
    )


# The header and the body's retry_after carry the same number; the body is the
# fallback for a proxy that strips the header.
def _retry_after(headers: httpx.Headers, body_seconds: Any) -> float | None:
    try:
        return float(headers["retry-after"])
    except (KeyError, ValueError):
        pass

    is_number = isinstance(body_seconds, (int, float)) and not isinstance(body_seconds, bool)
    return float(body_seconds) if is_number else None


def _str_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


# An error from a proxy in front of the API may not be JSON at all.
def _error_detail(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}

    detail = body.get("error") if isinstance(body, dict) else None
    return detail if isinstance(detail, dict) else {}


def _api_error(response: httpx.Response, path: str) -> PkmnPricesError:
    detail = _error_detail(response)
    limit_type = detail.get("limit_type")
    fallback = f"Request to {path} failed with status {response.status_code}"

    return create_api_error(
        status=response.status_code,
        code=_str_or_none(detail.get("code")) or "unknown",
        message=_str_or_none(detail.get("message")) or fallback,
        docs_url=_str_or_none(detail.get("docs_url")),
        rate_limit=_rate_limit(response.headers),
        retry_after=_retry_after(response.headers, detail.get("retry_after")),
        limit_type=limit_type if limit_type in ("per_minute", "daily") else None,
        resets_at=_str_or_none(detail.get("resets_at")),
        upgrade_url=_str_or_none(detail.get("upgrade_url")),
    )


def _handle(response: httpx.Response, path: str) -> Any:
    if not response.is_success:
        raise _api_error(response, path)

    if not response.content:
        return None
    return response.json()


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
        headers = {"accept": request.accept}
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

    # For bodies the caller reads in chunks. One attempt and no retries,
    # because a retried download can spend a daily download allowance twice.
    @contextmanager
    def stream(self, request: Request) -> Iterator[httpx.Response]:
        try:
            with self._client.stream(
                request.method, request.path, params=request.query, headers=self._headers(request)
            ) as response:
                if not response.is_success:
                    response.read()
                    raise _api_error(response, request.path)

                yield response
        except httpx.TimeoutException as error:
            raise APIConnectionError(f"Request to {request.path} timed out", error) from error
        except httpx.HTTPError as error:
            raise APIConnectionError(f"Request to {request.path} failed", error) from error

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

    @asynccontextmanager
    async def stream(self, request: Request) -> AsyncIterator[httpx.Response]:
        try:
            async with self._client.stream(
                request.method, request.path, params=request.query, headers=self._headers(request)
            ) as response:
                if not response.is_success:
                    await response.aread()
                    raise _api_error(response, request.path)

                yield response
        except httpx.TimeoutException as error:
            raise APIConnectionError(f"Request to {request.path} timed out", error) from error
        except httpx.HTTPError as error:
            raise APIConnectionError(f"Request to {request.path} failed", error) from error

    async def close(self) -> None:
        await self._client.aclose()
