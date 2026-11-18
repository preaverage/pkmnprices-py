from __future__ import annotations

import os
from typing import Any, AsyncIterator, List, Sequence

from . import _endpoints as ep
from ._http import AsyncTransport
from .models import (
    Card,
    CardMarkers,
    CardmarketListing,
    CardPopulation,
    CardsExport,
    CardSummary,
    Countries,
    CursorPage,
    EbayListing,
    GradeQualifierFilter,
    Page,
    PriceHistoryPoint,
    SalesVolumePoint,
    SaleType,
    Sealed,
    SealedSummary,
    Set,
    TcgplayerListing,
    TcgplayerSort,
)
from .pagination import paginate_async, paginate_cursor_async, paginate_list_async


class AsyncSetsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._t = transport

    async def list(
        self, *, name: str | None = None, language: str | None = None,
        page: int | None = None, per_page: int | None = None, cursor: str | None = None,
    ) -> Page[Set]:
        """Sets, 50 a page by default.

        ``cursor`` takes the previous page's ``pagination.next_cursor`` and
        replaces ``page``: send one or the other.
        """
        raw = await self._t.request(ep.sets_list(
            name=name, language=language, page=page, per_page=per_page, cursor=cursor,
        ))
        return ep.build_page(raw, Set)

    async def get(self, set_id: int) -> Set:
        return Set.from_dict(await self._t.request(ep.sets_get(set_id)))

    def iterate(self, **params: Any) -> AsyncIterator[Set]:
        return paginate_list_async(
            lambda page, cursor: self.list(**{**params, "page": page, "cursor": cursor}),
            params.get("page"), params.get("cursor"),
        )

    async def list_all(self, **params: Any) -> List[Set]:
        return [item async for item in self.iterate(**params)]


class AsyncCardListingsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._t = transport

    async def ebay(
        self, card_id: int, *, graded: bool | None = None, grader: str | None = None,
        grade: str | None = None, min_price: float | None = None, max_price: float | None = None,
        variant: str | None = None, since: str | None = None,
        updated_since: str | None = None, period: str | None = None,
        seller_country: Countries | None = None, exclude_seller_country: Countries | None = None,
        grade_qualifier: GradeQualifierFilter | None = None,
        sale_type: SaleType | Sequence[SaleType] | None = None,
        sort: str | None = None, limit: int | None = None, cursor: str | None = None,
    ) -> CursorPage[EbayListing]:
        """Sold eBay comps for a card.

        ``since`` returns only comps ingested after that instant, as an RFC 3339
        timestamp or ``YYYY-MM-DD`` for midnight UTC. It filters on ingestion,
        not on sale date: a sale-date bound would permanently step over comps
        that arrive back-dated. Checkpoint on a row's ``ingested_at``, which is
        exclusive, so passing it back never repeats that row.

        ``updated_since`` returns only comps corrected after that instant, in
        the same format. It bounds ``updated_at``. A correction never moves
        ``ingested_at``, so if you keep a copy of comps, poll this as well and
        replace rows by ``id``.

        ``period`` returns only comps sold in the last N days, as ``"90d"`` or
        ``"90"`` (1 to 365). It bounds ``sold_at``, so use it for pricing and
        not for syncing: comps often arrive days after the sale.

        ``seller_country`` and ``exclude_seller_country`` take ISO 3166-1
        alpha-2 codes as a list or a comma-separated string, at most 30.
        ``seller_country`` leaves out comps with no known country;
        ``exclude_seller_country`` keeps them. ``sale_type`` takes one value or
        a list, and leaves out comps whose sale type is unknown.
        """
        raw = await self._t.request(ep.cards_listings_ebay(
            card_id, graded=graded, grader=grader, grade=grade, min_price=min_price,
            max_price=max_price, variant=variant, since=since,
            updated_since=updated_since, period=period,
            seller_country=seller_country, exclude_seller_country=exclude_seller_country,
            grade_qualifier=grade_qualifier, sale_type=sale_type,
            sort=sort, limit=limit, cursor=cursor,
        ))
        return ep.build_cursor_page(raw, EbayListing)

    def iterate_ebay(self, card_id: int, **params: Any) -> AsyncIterator[EbayListing]:
        return paginate_cursor_async(lambda cursor: self.ebay(card_id, **{**params, "cursor": cursor}))

    async def all_ebay(self, card_id: int, **params: Any) -> List[EbayListing]:
        return [item async for item in self.iterate_ebay(card_id, **params)]

    async def cardmarket(
        self, card_id: int, *, condition: str | None = None, variant: str | None = None,
        min_price: float | None = None, max_price: float | None = None,
        seller_country: Countries | None = None, exclude_seller_country: Countries | None = None,
        graded: bool | None = None, grader: str | None = None, grade: str | None = None,
        signed: bool | None = None, altered: bool | None = None,
        min_sell_count: int | None = None,
        sort: str | None = None, limit: int | None = None, cursor: str | None = None,
    ) -> CursorPage[CardmarketListing]:
        """Live Cardmarket offers for a card, in the card's set language.

        ``graded``, ``signed`` and ``altered`` each take ``True`` for only those
        offers and ``False`` to leave them out. Such offers are real but do not
        set a market price, so ``graded=False, signed=False, altered=False``
        leaves clean raw copies. ``grader`` and ``grade`` narrow graded offers.

        ``min_sell_count`` keeps offers from sellers with at least that many
        completed sales, and leaves out offers with no recorded count.
        """
        raw = await self._t.request(ep.cards_listings_cardmarket(
            card_id, condition=condition, variant=variant, min_price=min_price,
            max_price=max_price, seller_country=seller_country,
            exclude_seller_country=exclude_seller_country, graded=graded, grader=grader,
            grade=grade, signed=signed, altered=altered, min_sell_count=min_sell_count,
            sort=sort, limit=limit, cursor=cursor,
        ))
        return ep.build_cursor_page(raw, CardmarketListing)

    def iterate_cardmarket(self, card_id: int, **params: Any) -> AsyncIterator[CardmarketListing]:
        return paginate_cursor_async(lambda cursor: self.cardmarket(card_id, **{**params, "cursor": cursor}))

    async def all_cardmarket(self, card_id: int, **params: Any) -> List[CardmarketListing]:
        return [item async for item in self.iterate_cardmarket(card_id, **params)]

    async def tcgplayer(
        self, card_id: int, *, condition: str | None = None, language: str | None = None,
        printing: str | None = None, min_price: float | None = None, max_price: float | None = None,
        sort: TcgplayerSort | None = None, limit: int | None = None, cursor: str | None = None,
    ) -> CursorPage[TcgplayerListing]:
        raw = await self._t.request(ep.cards_listings_tcgplayer(
            card_id, condition=condition, language=language, printing=printing,
            min_price=min_price, max_price=max_price, sort=sort, limit=limit, cursor=cursor,
        ))
        return ep.build_cursor_page(raw, TcgplayerListing)

    def iterate_tcgplayer(self, card_id: int, **params: Any) -> AsyncIterator[TcgplayerListing]:
        return paginate_cursor_async(lambda cursor: self.tcgplayer(card_id, **{**params, "cursor": cursor}))

    async def all_tcgplayer(self, card_id: int, **params: Any) -> List[TcgplayerListing]:
        return [item async for item in self.iterate_tcgplayer(card_id, **params)]


class AsyncCardsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._t = transport
        self.listings = AsyncCardListingsResource(transport)

    async def list(
        self, *, name: str | None = None, set_id: int | None = None, tcg_player_id: int | None = None,
        number: str | None = None, total_set_number: str | None = None, rarity: str | None = None,
        pattern: str | None = None, stamp: str | None = None,
        distribution: str | None = None, placement: str | None = None,
        stage: str | None = None, card_type: str | None = None, weakness: str | None = None,
        energy_type: str | None = None, artist: str | None = None, hp: int | None = None,
        language: str | None = None, currency: str | None = None, condition: str | None = None,
        variant: str | None = None, grader: str | None = None, grade: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None, sort: str | None = None,
        page: int | None = None, per_page: int | None = None, cursor: str | None = None,
    ) -> Page[CardSummary]:
        """Cards, without prices. Use ``get()`` for a card's prices.

        ``pattern``, ``stamp``, ``distribution`` and ``placement`` match exactly
        as spelled in responses; ``markers()`` lists every value they accept.
        ``artist`` is a case-insensitive substring match and ``hp`` is exact.

        ``cursor`` takes the previous page's ``pagination.next_cursor`` and
        replaces ``page``: send one or the other. It is refused with a 400 on
        lists filtered or sorted by price, which page by number only.
        """
        raw = await self._t.request(ep.cards_list(
            name=name, set_id=set_id, tcg_player_id=tcg_player_id, number=number,
            total_set_number=total_set_number, rarity=rarity, pattern=pattern, stamp=stamp,
            distribution=distribution, placement=placement, stage=stage, card_type=card_type,
            weakness=weakness, energy_type=energy_type, artist=artist, hp=hp,
            language=language, currency=currency,
            condition=condition, variant=variant, grader=grader, grade=grade, min_price=min_price,
            max_price=max_price, sort=sort, page=page, per_page=per_page, cursor=cursor,
        ))
        return ep.build_page(raw, CardSummary)

    async def get(self, card_id: int, *, currency: str | None = None) -> Card:
        return Card.from_dict(await self._t.request(ep.cards_get(card_id, currency=currency)))

    def iterate(self, **params: Any) -> AsyncIterator[CardSummary]:
        return paginate_list_async(
            lambda page, cursor: self.list(**{**params, "page": page, "cursor": cursor}),
            params.get("page"), params.get("cursor"),
        )

    async def list_all(self, **params: Any) -> List[CardSummary]:
        return [item async for item in self.iterate(**params)]

    async def price_history(
        self, card_id: int, *, period: str | None = None, currency: str | None = None,
        condition: str | None = None, variant: str | None = None,
        limit: int | None = None, page: int | None = None,
    ) -> Page[PriceHistoryPoint]:
        raw = await self._t.request(ep.cards_history(
            card_id, period=period, currency=currency, condition=condition, variant=variant,
            limit=limit, page=page,
        ))
        return ep.build_page(raw, PriceHistoryPoint)

    def iterate_price_history(self, card_id: int, **params: Any) -> AsyncIterator[PriceHistoryPoint]:
        start = params.get("page") or 1
        return paginate_async(lambda page: self.price_history(card_id, **{**params, "page": page}), start)

    async def sales_volume(
        self, card_id: int, *, period: str | None = None, currency: str | None = None,
        variant: str | None = None, graded: bool | None = None,
        limit: int | None = None, page: int | None = None,
    ) -> Page[SalesVolumePoint]:
        """Daily eBay sold-comp counts for a card, newest day first.

        eBay only: TCGplayer and Cardmarket sales are not recorded, so this is
        not total market volume. A row is one day, currency, variant and graded
        group, so ``limit`` counts rows, not days.
        """
        raw = await self._t.request(ep.cards_sales_volume(
            card_id, period=period, currency=currency, variant=variant, graded=graded,
            limit=limit, page=page,
        ))
        return ep.build_page(raw, SalesVolumePoint)

    def iterate_sales_volume(self, card_id: int, **params: Any) -> AsyncIterator[SalesVolumePoint]:
        start = params.get("page") or 1
        return paginate_async(lambda page: self.sales_volume(card_id, **{**params, "page": page}), start)

    async def population(self, card_id: int, *, variant: str | None = None) -> CardPopulation:
        """Graded population per variant, from the PSA, BGS, SGC and CGC reports."""
        raw = await self._t.request(ep.cards_population(card_id, variant=variant))
        return CardPopulation.from_dict(raw)

    async def markers(self) -> CardMarkers:
        """Every value the pattern, stamp, distribution and placement filters accept."""
        return CardMarkers.from_dict(await self._t.request(ep.cards_markers()))

    async def export(self, path: str | os.PathLike[str] | None = None) -> CardsExport:
        """Downloads the whole price catalog as one gzipped CSV. Scale plan and up.

        Writes to ``path``, or to the server's filename in the working directory
        when ``path`` is omitted. The export is not charged in credits, but each
        account gets two downloads per UTC day, so it is never retried.
        """
        async with self._t.stream(ep.cards_export()) as response:
            export = ep.build_export(response.headers, path)
            with export.path.open("wb") as file:
                async for chunk in response.aiter_bytes():
                    file.write(chunk)

        return export


class AsyncSealedListingsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._t = transport

    # Sealed eBay sales are never graded, so graded/grader/grade don't apply.
    async def ebay(
        self, sealed_id: int, *, min_price: float | None = None, max_price: float | None = None,
        since: str | None = None, period: str | None = None,
        sort: str | None = None, limit: int | None = None, cursor: str | None = None,
    ) -> CursorPage[EbayListing]:
        """Sold eBay comps for a sealed product.

        ``since`` returns only comps ingested after that instant, as an RFC 3339
        timestamp or ``YYYY-MM-DD`` for midnight UTC. It filters on ingestion,
        not on sale date. Checkpoint on a row's ``ingested_at``.

        ``period`` returns only comps sold in the last N days, as ``"90d"`` or
        ``"90"`` (1 to 365). It bounds ``sold_at``.
        """
        raw = await self._t.request(ep.sealed_listings_ebay(
            sealed_id, min_price=min_price, max_price=max_price, since=since, period=period,
            sort=sort, limit=limit, cursor=cursor,
        ))
        return ep.build_cursor_page(raw, EbayListing)

    def iterate_ebay(self, sealed_id: int, **params: Any) -> AsyncIterator[EbayListing]:
        return paginate_cursor_async(lambda cursor: self.ebay(sealed_id, **{**params, "cursor": cursor}))

    async def all_ebay(self, sealed_id: int, **params: Any) -> List[EbayListing]:
        return [item async for item in self.iterate_ebay(sealed_id, **params)]

    # Sealed offers are normally condition "Unopened" with an empty printing,
    # so those two filters rarely narrow anything here.
    async def tcgplayer(
        self, sealed_id: int, *, condition: str | None = None, language: str | None = None,
        printing: str | None = None, min_price: float | None = None, max_price: float | None = None,
        sort: TcgplayerSort | None = None, limit: int | None = None, cursor: str | None = None,
    ) -> CursorPage[TcgplayerListing]:
        raw = await self._t.request(ep.sealed_listings_tcgplayer(
            sealed_id, condition=condition, language=language, printing=printing,
            min_price=min_price, max_price=max_price, sort=sort, limit=limit, cursor=cursor,
        ))
        return ep.build_cursor_page(raw, TcgplayerListing)

    def iterate_tcgplayer(self, sealed_id: int, **params: Any) -> AsyncIterator[TcgplayerListing]:
        return paginate_cursor_async(lambda cursor: self.tcgplayer(sealed_id, **{**params, "cursor": cursor}))

    async def all_tcgplayer(self, sealed_id: int, **params: Any) -> List[TcgplayerListing]:
        return [item async for item in self.iterate_tcgplayer(sealed_id, **params)]

    # No variant filter, unlike the card endpoint: every sealed Cardmarket row
    # is written with an empty variant, so the parameter could only ever
    # exclude everything. `opened` is meaningful only on these rows: True for
    # offers whose seller says the product is not sealed, False to leave those
    # out. The other attribute filters behave as on the card endpoint.
    async def cardmarket(
        self, sealed_id: int, *, condition: str | None = None,
        min_price: float | None = None, max_price: float | None = None,
        seller_country: Countries | None = None, exclude_seller_country: Countries | None = None,
        graded: bool | None = None, grader: str | None = None, grade: str | None = None,
        signed: bool | None = None, altered: bool | None = None, opened: bool | None = None,
        min_sell_count: int | None = None,
        sort: str | None = None, limit: int | None = None, cursor: str | None = None,
    ) -> CursorPage[CardmarketListing]:
        raw = await self._t.request(ep.sealed_listings_cardmarket(
            sealed_id, condition=condition, min_price=min_price,
            max_price=max_price, seller_country=seller_country,
            exclude_seller_country=exclude_seller_country, graded=graded, grader=grader,
            grade=grade, signed=signed, altered=altered, opened=opened,
            min_sell_count=min_sell_count, sort=sort, limit=limit, cursor=cursor,
        ))
        return ep.build_cursor_page(raw, CardmarketListing)

    def iterate_cardmarket(self, sealed_id: int, **params: Any) -> AsyncIterator[CardmarketListing]:
        return paginate_cursor_async(lambda cursor: self.cardmarket(sealed_id, **{**params, "cursor": cursor}))

    async def all_cardmarket(self, sealed_id: int, **params: Any) -> List[CardmarketListing]:
        return [item async for item in self.iterate_cardmarket(sealed_id, **params)]


class AsyncSealedResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._t = transport
        self.listings = AsyncSealedListingsResource(transport)

    async def list(
        self, *, set_id: int | None = None, tcg_player_id: int | None = None,
        name: str | None = None, language: str | None = None,
        currency: str | None = None, min_price: float | None = None, max_price: float | None = None,
        sort: str | None = None, page: int | None = None, per_page: int | None = None,
        cursor: str | None = None,
    ) -> Page[SealedSummary]:
        raw = await self._t.request(ep.sealed_list(
            set_id=set_id, tcg_player_id=tcg_player_id, name=name, language=language,
            currency=currency, min_price=min_price, max_price=max_price, sort=sort,
            page=page, per_page=per_page, cursor=cursor,
        ))
        return ep.build_page(raw, SealedSummary)

    async def get(self, sealed_id: int, *, currency: str | None = None) -> Sealed:
        return Sealed.from_dict(await self._t.request(ep.sealed_get(sealed_id, currency=currency)))

    def iterate(self, **params: Any) -> AsyncIterator[SealedSummary]:
        return paginate_list_async(
            lambda page, cursor: self.list(**{**params, "page": page, "cursor": cursor}),
            params.get("page"), params.get("cursor"),
        )

    async def list_all(self, **params: Any) -> List[SealedSummary]:
        return [item async for item in self.iterate(**params)]

    async def price_history(
        self, sealed_id: int, *, period: str | None = None, currency: str | None = None,
        condition: str | None = None, variant: str | None = None,
        limit: int | None = None, page: int | None = None,
    ) -> Page[PriceHistoryPoint]:
        raw = await self._t.request(ep.sealed_history(
            sealed_id, period=period, currency=currency, condition=condition, variant=variant,
            limit=limit, page=page,
        ))
        return ep.build_page(raw, PriceHistoryPoint)

    def iterate_price_history(self, sealed_id: int, **params: Any) -> AsyncIterator[PriceHistoryPoint]:
        start = params.get("page") or 1
        return paginate_async(lambda page: self.price_history(sealed_id, **{**params, "page": page}), start)
