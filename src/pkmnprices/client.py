from __future__ import annotations

from typing import Any

import httpx

from . import _endpoints as ep
from ._http import AsyncTransport, SyncTransport
from .aio import AsyncCardsResource, AsyncSealedResource, AsyncSetsResource
from .models import Health
from .resources import CardsResource, SealedResource, SetsResource

# Request paths carry their own /v1 prefix, and /health has none, so this is the origin only.
_BASE_URL = "https://api.pkmnprices.com"


class PkmnPrices:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        max_retries: int = 2,
        timeout: float = 30.0,
        _transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._t = SyncTransport(
            api_key=api_key,
            base_url=_BASE_URL,
            max_retries=max_retries,
            timeout=timeout,
            transport=_transport,
        )
        self.sets = SetsResource(self._t)
        self.cards = CardsResource(self._t)
        self.sealed = SealedResource(self._t)

    def health(self) -> Health:
        return Health.from_dict(self._t.request(ep.health()))

    def close(self) -> None:
        self._t.close()

    def __enter__(self) -> "PkmnPrices":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


class AsyncPkmnPrices:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        max_retries: int = 2,
        timeout: float = 30.0,
        _transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._t = AsyncTransport(
            api_key=api_key,
            base_url=_BASE_URL,
            max_retries=max_retries,
            timeout=timeout,
            transport=_transport,
        )
        self.sets = AsyncSetsResource(self._t)
        self.cards = AsyncCardsResource(self._t)
        self.sealed = AsyncSealedResource(self._t)

    async def health(self) -> Health:
        return Health.from_dict(await self._t.request(ep.health()))

    async def close(self) -> None:
        await self._t.close()

    async def __aenter__(self) -> "AsyncPkmnPrices":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()
