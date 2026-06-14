from __future__ import annotations

from typing import Any, Iterator, List

from . import _endpoints as ep
from ._http import SyncTransport
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
from .pagination import paginate, paginate_cursor


class SetsResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._t = transport

    def list(
        self, *, name: str | None = None, language: str | None = None,
        page: int | None = None, per_page: int | None = None,
    ) -> Page[Set]:
        raw = self._t.request(ep.sets_list(name=name, language=language, page=page, per_page=per_page))
        return ep.build_page(raw, Set)

    def get(self, set_id: int) -> Set:
        return Set.from_dict(self._t.request(ep.sets_get(set_id)))

    def iterate(self, **params: Any) -> Iterator[Set]:
        start = params.get("page") or 1
        return paginate(lambda page: self.list(**{**params, "page": page}), start)

    def list_all(self, **params: Any) -> List[Set]:
        return list(self.iterate(**params))


class CardListingsResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._t = transport

    def ebay(
        self, card_id: int, *, grader: str | None = None, grade: str | None = None,
        min_price: float | None = None, max_price: float | None = None,
        sort: str | None = None, limit: int | None = None, cursor: str | None = None,
    ) -> CursorPage[EbayListing]:
        raw = self._t.request(ep.cards_listings_ebay(
            card_id, grader=grader, grade=grade, min_price=min_price,
            max_price=max_price, sort=sort, limit=limit, cursor=cursor,
        ))
        return ep.build_cursor_page(raw, EbayListing)

    def iterate_ebay(self, card_id: int, **params: Any) -> Iterator[EbayListing]:
        return paginate_cursor(lambda cursor: self.ebay(card_id, **{**params, "cursor": cursor}))

    def all_ebay(self, card_id: int, **params: Any) -> List[EbayListing]:
        return list(self.iterate_ebay(card_id, **params))

    def cardmarket(
        self, card_id: int, *, condition: str | None = None, language: str | None = None,
        variant: str | None = None, min_price: float | None = None, max_price: float | None = None,
        sort: str | None = None, limit: int | None = None, cursor: str | None = None,
    ) -> CursorPage[CardmarketListing]:
        raw = self._t.request(ep.cards_listings_cardmarket(
            card_id, condition=condition, language=language, variant=variant,
            min_price=min_price, max_price=max_price, sort=sort, limit=limit, cursor=cursor,
        ))
        return ep.build_cursor_page(raw, CardmarketListing)

    def iterate_cardmarket(self, card_id: int, **params: Any) -> Iterator[CardmarketListing]:
        return paginate_cursor(lambda cursor: self.cardmarket(card_id, **{**params, "cursor": cursor}))

    def all_cardmarket(self, card_id: int, **params: Any) -> List[CardmarketListing]:
        return list(self.iterate_cardmarket(card_id, **params))


class CardsResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._t = transport
        self.listings = CardListingsResource(transport)

    def list(
        self, *, name: str | None = None, set_id: int | None = None, tcg_player_id: int | None = None,
        number: str | None = None, total_set_number: str | None = None, rarity: str | None = None,
        language: str | None = None, currency: str | None = None, condition: str | None = None,
        variant: str | None = None, grade: str | None = None, min_price: float | None = None,
        max_price: float | None = None, sort: str | None = None,
        page: int | None = None, per_page: int | None = None,
    ) -> Page[CardSummary]:
        raw = self._t.request(ep.cards_list(
            name=name, set_id=set_id, tcg_player_id=tcg_player_id, number=number,
            total_set_number=total_set_number, rarity=rarity, language=language, currency=currency,
            condition=condition, variant=variant, grade=grade, min_price=min_price,
            max_price=max_price, sort=sort, page=page, per_page=per_page,
        ))
        return ep.build_page(raw, CardSummary)

    def get(self, card_id: int, *, currency: str | None = None) -> Card:
        return Card.from_dict(self._t.request(ep.cards_get(card_id, currency=currency)))

    def iterate(self, **params: Any) -> Iterator[CardSummary]:
        start = params.get("page") or 1
        return paginate(lambda page: self.list(**{**params, "page": page}), start)

    def list_all(self, **params: Any) -> List[CardSummary]:
        return list(self.iterate(**params))

    def price_history(
        self, card_id: int, *, period: str | None = None, currency: str | None = None,
        limit: int | None = None, page: int | None = None,
    ) -> Page[PriceHistoryPoint]:
        raw = self._t.request(ep.cards_history(card_id, period=period, currency=currency, limit=limit, page=page))
        return ep.build_page(raw, PriceHistoryPoint)

    def iterate_price_history(self, card_id: int, **params: Any) -> Iterator[PriceHistoryPoint]:
        start = params.get("page") or 1
        return paginate(lambda page: self.price_history(card_id, **{**params, "page": page}), start)


class SealedResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._t = transport

    def list(
        self, *, set_id: int | None = None, name: str | None = None, language: str | None = None,
        min_price: float | None = None, max_price: float | None = None, sort: str | None = None,
        page: int | None = None, per_page: int | None = None,
    ) -> Page[SealedSummary]:
        raw = self._t.request(ep.sealed_list(
            set_id=set_id, name=name, language=language, min_price=min_price,
            max_price=max_price, sort=sort, page=page, per_page=per_page,
        ))
        return ep.build_page(raw, SealedSummary)

    def get(self, sealed_id: int) -> Sealed:
        return Sealed.from_dict(self._t.request(ep.sealed_get(sealed_id)))

    def iterate(self, **params: Any) -> Iterator[SealedSummary]:
        start = params.get("page") or 1
        return paginate(lambda page: self.list(**{**params, "page": page}), start)

    def list_all(self, **params: Any) -> List[SealedSummary]:
        return list(self.iterate(**params))

    def price_history(
        self, sealed_id: int, *, period: str | None = None, currency: str | None = None,
        limit: int | None = None, page: int | None = None,
    ) -> Page[PriceHistoryPoint]:
        raw = self._t.request(ep.sealed_history(sealed_id, period=period, currency=currency, limit=limit, page=page))
        return ep.build_page(raw, PriceHistoryPoint)

    def listings(
        self, sealed_id: int, *, min_price: float | None = None, max_price: float | None = None,
        sort: str | None = None, limit: int | None = None, cursor: str | None = None,
    ) -> CursorPage[SealedEbayListing]:
        raw = self._t.request(ep.sealed_listings(
            sealed_id, min_price=min_price, max_price=max_price, sort=sort, limit=limit, cursor=cursor,
        ))
        return ep.build_cursor_page(raw, SealedEbayListing)

    def iterate_listings(self, sealed_id: int, **params: Any) -> Iterator[SealedEbayListing]:
        return paginate_cursor(lambda cursor: self.listings(sealed_id, **{**params, "cursor": cursor}))

    def all_listings(self, sealed_id: int, **params: Any) -> List[SealedEbayListing]:
        return list(self.iterate_listings(sealed_id, **params))
