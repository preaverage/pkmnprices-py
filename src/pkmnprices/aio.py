from __future__ import annotations

from typing import Any, AsyncIterator, List

from . import _endpoints as ep
from ._http import AsyncTransport
from .models import (
    Card,
    CardmarketListing,
    CardSummary,
    CursorPage,
    EbayListing,
    Page,
    PriceHistoryPoint,
    Sealed,
    SealedEbayListing,
    SealedSummary,
    Set,
)
from .pagination import paginate_async, paginate_cursor_async


class AsyncSetsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._t = transport

    async def list(
        self, *, name: str | None = None, language: str | None = None,
        page: int | None = None, per_page: int | None = None,
    ) -> Page[Set]:
        raw = await self._t.request(ep.sets_list(name=name, language=language, page=page, per_page=per_page))
        return ep.build_page(raw, Set)

    async def get(self, set_id: int) -> Set:
        return Set.from_dict(await self._t.request(ep.sets_get(set_id)))

    def iterate(self, **params: Any) -> AsyncIterator[Set]:
        start = params.get("page") or 1
        return paginate_async(lambda page: self.list(**{**params, "page": page}), start)

    async def list_all(self, **params: Any) -> List[Set]:
        return [item async for item in self.iterate(**params)]


class AsyncCardListingsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._t = transport

    async def ebay(
        self, card_id: int, *, grader: str | None = None, grade: str | None = None,
        min_price: float | None = None, max_price: float | None = None,
        sort: str | None = None, limit: int | None = None, cursor: str | None = None,
    ) -> CursorPage[EbayListing]:
        raw = await self._t.request(ep.cards_listings_ebay(
            card_id, grader=grader, grade=grade, min_price=min_price,
            max_price=max_price, sort=sort, limit=limit, cursor=cursor,
        ))
        return ep.build_cursor_page(raw, EbayListing)

    def iterate_ebay(self, card_id: int, **params: Any) -> AsyncIterator[EbayListing]:
        return paginate_cursor_async(lambda cursor: self.ebay(card_id, **{**params, "cursor": cursor}))

    async def all_ebay(self, card_id: int, **params: Any) -> List[EbayListing]:
        return [item async for item in self.iterate_ebay(card_id, **params)]

    async def cardmarket(
        self, card_id: int, *, condition: str | None = None, language: str | None = None,
        variant: str | None = None, min_price: float | None = None, max_price: float | None = None,
        sort: str | None = None, limit: int | None = None, cursor: str | None = None,
    ) -> CursorPage[CardmarketListing]:
        raw = await self._t.request(ep.cards_listings_cardmarket(
            card_id, condition=condition, language=language, variant=variant,
            min_price=min_price, max_price=max_price, sort=sort, limit=limit, cursor=cursor,
        ))
        return ep.build_cursor_page(raw, CardmarketListing)

    def iterate_cardmarket(self, card_id: int, **params: Any) -> AsyncIterator[CardmarketListing]:
        return paginate_cursor_async(lambda cursor: self.cardmarket(card_id, **{**params, "cursor": cursor}))

    async def all_cardmarket(self, card_id: int, **params: Any) -> List[CardmarketListing]:
        return [item async for item in self.iterate_cardmarket(card_id, **params)]


class AsyncCardsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._t = transport
        self.listings = AsyncCardListingsResource(transport)

    async def list(
        self, *, name: str | None = None, set_id: int | None = None, tcg_player_id: int | None = None,
        number: str | None = None, total_set_number: str | None = None, rarity: str | None = None,
        language: str | None = None, currency: str | None = None, condition: str | None = None,
        variant: str | None = None, grade: str | None = None, min_price: float | None = None,
        max_price: float | None = None, sort: str | None = None,
        page: int | None = None, per_page: int | None = None,
    ) -> Page[CardSummary]:
        raw = await self._t.request(ep.cards_list(
            name=name, set_id=set_id, tcg_player_id=tcg_player_id, number=number,
            total_set_number=total_set_number, rarity=rarity, language=language, currency=currency,
            condition=condition, variant=variant, grade=grade, min_price=min_price,
            max_price=max_price, sort=sort, page=page, per_page=per_page,
        ))
        return ep.build_page(raw, CardSummary)

    async def get(self, card_id: int, *, currency: str | None = None) -> Card:
        return Card.from_dict(await self._t.request(ep.cards_get(card_id, currency=currency)))

    def iterate(self, **params: Any) -> AsyncIterator[CardSummary]:
        start = params.get("page") or 1
        return paginate_async(lambda page: self.list(**{**params, "page": page}), start)

    async def list_all(self, **params: Any) -> List[CardSummary]:
        return [item async for item in self.iterate(**params)]

    async def price_history(
        self, card_id: int, *, period: str | None = None, currency: str | None = None,
        limit: int | None = None, page: int | None = None,
    ) -> Page[PriceHistoryPoint]:
        raw = await self._t.request(ep.cards_history(card_id, period=period, currency=currency, limit=limit, page=page))
        return ep.build_page(raw, PriceHistoryPoint)

    def iterate_price_history(self, card_id: int, **params: Any) -> AsyncIterator[PriceHistoryPoint]:
        start = params.get("page") or 1
        return paginate_async(lambda page: self.price_history(card_id, **{**params, "page": page}), start)


class AsyncSealedResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._t = transport

    async def list(
        self, *, set_id: int | None = None, name: str | None = None, language: str | None = None,
        min_price: float | None = None, max_price: float | None = None, sort: str | None = None,
        page: int | None = None, per_page: int | None = None,
    ) -> Page[SealedSummary]:
        raw = await self._t.request(ep.sealed_list(
            set_id=set_id, name=name, language=language, min_price=min_price,
            max_price=max_price, sort=sort, page=page, per_page=per_page,
        ))
        return ep.build_page(raw, SealedSummary)

    async def get(self, sealed_id: int) -> Sealed:
        return Sealed.from_dict(await self._t.request(ep.sealed_get(sealed_id)))

    def iterate(self, **params: Any) -> AsyncIterator[SealedSummary]:
        start = params.get("page") or 1
        return paginate_async(lambda page: self.list(**{**params, "page": page}), start)

    async def list_all(self, **params: Any) -> List[SealedSummary]:
        return [item async for item in self.iterate(**params)]

    async def price_history(
        self, sealed_id: int, *, period: str | None = None, currency: str | None = None,
        limit: int | None = None, page: int | None = None,
    ) -> Page[PriceHistoryPoint]:
        raw = await self._t.request(ep.sealed_history(sealed_id, period=period, currency=currency, limit=limit, page=page))
        return ep.build_page(raw, PriceHistoryPoint)

    async def listings(
        self, sealed_id: int, *, min_price: float | None = None, max_price: float | None = None,
        sort: str | None = None, limit: int | None = None, cursor: str | None = None,
    ) -> CursorPage[SealedEbayListing]:
        raw = await self._t.request(ep.sealed_listings(
            sealed_id, min_price=min_price, max_price=max_price, sort=sort, limit=limit, cursor=cursor,
        ))
        return ep.build_cursor_page(raw, SealedEbayListing)

    def iterate_listings(self, sealed_id: int, **params: Any) -> AsyncIterator[SealedEbayListing]:
        return paginate_cursor_async(lambda cursor: self.listings(sealed_id, **{**params, "cursor": cursor}))

    async def all_listings(self, sealed_id: int, **params: Any) -> List[SealedEbayListing]:
        return [item async for item in self.iterate_listings(sealed_id, **params)]
