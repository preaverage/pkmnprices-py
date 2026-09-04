from __future__ import annotations

import dataclasses
import types as _types
from typing import Any, Generic, Literal, TypeVar, Union, get_args, get_origin, get_type_hints

Currency = Literal["USD", "EUR"]
PriceSource = Literal["tcgplayer", "ebay", "cardmarket"]
HealthStatus = Literal["healthy", "degraded", "unreachable"]

# Whether a sold comp describes one card alone. A variant and its base card can
# map to a single source product page, and when they do both serve the same
# sales, with titles describing whichever printing the seller actually sold.
#
#   exact    the source page belongs to this card and no other
#   shared   the sale appears under another card too, and its title may
#            describe that printing; it prices the group, not this entity
#   unknown  collected before the source printing was recorded
ListingAttribution = Literal["exact", "shared", "unknown"]

_hints_cache: dict[type, dict[str, Any]] = {}


def _hints(cls: type) -> dict[str, Any]:
    if cls not in _hints_cache:
        _hints_cache[cls] = get_type_hints(cls)
    return _hints_cache[cls]


def _coerce(tp: Any, value: Any) -> Any:
    if value is None:
        return None

    origin = get_origin(tp)

    if origin is Union or origin is _types.UnionType:
        inner = next((arg for arg in get_args(tp) if arg is not type(None)), None)
        return _coerce(inner, value) if inner is not None else value

    if origin in (list, tuple):
        args = get_args(tp)
        inner = args[0] if args else Any
        return [_coerce(inner, item) for item in value]

    if isinstance(tp, type) and dataclasses.is_dataclass(tp):
        return _build(tp, value)

    return value


def _build(cls: type, data: dict[str, Any]) -> Any:
    hints = _hints(cls)
    kwargs = {
        field.name: _coerce(hints[field.name], data[field.name]) if field.name in data else None
        for field in dataclasses.fields(cls)
    }
    return cls(**kwargs)


class Model:
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Any:
        return _build(cls, data)


@dataclasses.dataclass
class SetRef(Model):
    id: int
    name: str


@dataclasses.dataclass
class Set(Model):
    id: int
    tcg_player_id: int
    name: str
    language: str
    card_count: int


@dataclasses.dataclass
class Price(Model):
    source: PriceSource
    currency: Currency
    condition: str | None
    variant: str | None
    market_price: float
    created_at: str


@dataclasses.dataclass
class CardSummary(Model):
    id: int
    tcg_player_id: int
    name: str
    image_url: str | None
    number: str | None
    total_set_number: str | None
    rarity: str | None
    artist: str | None
    hp: int | None
    set: SetRef


@dataclasses.dataclass
class Card(CardSummary):
    cardmarket_url: str | None = None
    cardmarket_product_id: int | None = None
    stage: str | None = None
    card_type: str | None = None
    weakness: str | None = None
    resistance: str | None = None
    retreat_cost: int | None = None
    energy_type: list[str] | None = None
    ability: str | None = None
    flavor_text: str | None = None
    attacks: list[str] = dataclasses.field(default_factory=list)
    prices: list[Price] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class PriceHistoryPoint(Model):
    date: str
    source: PriceSource
    currency: Currency
    condition: str | None
    variant: str | None
    avg: float
    low: float
    high: float
    sale_count: int


@dataclasses.dataclass
class EbayListing(Model):
    id: int
    title: str
    price: float
    grader: str | None
    # Grades are strings and include halves ("9.5", "1.5"), so grade="9"
    # matches PSA 9 and not BGS 9.5.
    grade: str | None
    # The printing this comp was collected under, e.g. "Holofoil".
    variant: str | None
    attribution: ListingAttribution
    sold_at: str
    # When we collected the sale, which is not when it sold: collection runs
    # regularly bring in sales that are weeks old. This is the field to
    # checkpoint on when polling `since`.
    ingested_at: str
    listing_url: str | None


@dataclasses.dataclass
class CardmarketListing(Model):
    id: int
    article_id: int | None
    price: float
    variant: str
    condition: str | None
    seller: str | None
    quantity: int | None
    language: str | None
    comment: str | None
    updated_at: str
    # Cardmarket's per-listing special attributes. Any of these being True
    # means the offer is real but does not contribute to the card's market
    # price: a signed and altered Near Mint copy at EUR 200 must not set the
    # Near Mint price of a card whose clean copies sell for EUR 3,800, and a
    # slab is priced for the slab rather than for the card. So the cheapest
    # row from cardmarket() is not necessarily the card's market_price --
    # filter these out before deriving a price of your own.
    signed: bool
    altered: bool
    graded: bool
    # Slab details, named to match the graded eBay sale shape so "PSA 10"
    # reads the same whichever source it came from. None unless graded is
    # True, and possibly None even then: Cardmarket flags a slab without
    # always naming the grader, and these are read from free-text comments.
    grader: str | None
    grade: str | None


@dataclasses.dataclass
class TcgplayerListing(Model):
    id: int
    listing_id: int | None
    printing: str
    condition: str | None
    language: str | None
    price: float
    shipping_price: float | None
    seller_name: str | None
    seller_id: str | None
    seller_rating: float | None
    seller_sales: str | None
    quantity: int | None
    listing_type: str | None
    direct_seller: bool | None
    gold_seller: bool | None
    verified_seller: bool | None
    custom_title: str | None
    # When this listing's own fields last changed. Not a freshness signal: an
    # offer live and unchanged for a month keeps a month-old value however
    # recently it was confirmed. Read snapshot_at for that.
    updated_at: str
    # When this product's listings were last confirmed against TCGplayer. The
    # same for every row in a response, since a snapshot replaces a product's
    # listings wholesale. None if no successful snapshot has been recorded.
    snapshot_at: str | None


@dataclasses.dataclass
class SealedSummary(Model):
    id: int
    tcg_player_id: int
    name: str
    image_url: str | None
    set: SetRef


@dataclasses.dataclass
class Sealed(SealedSummary):
    cardmarket_url: str | None = None
    cardmarket_product_id: int | None = None
    prices: list[Price] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Health(Model):
    status: HealthStatus
    database: str


@dataclasses.dataclass
class PageInfo(Model):
    page: int
    per_page: int
    total: int
    total_pages: int


@dataclasses.dataclass
class CursorInfo(Model):
    has_more: bool
    next_cursor: str | None
    count: int


T = TypeVar("T")


@dataclasses.dataclass
class Page(Generic[T]):
    data: list[T]
    pagination: PageInfo


@dataclasses.dataclass
class CursorPage(Generic[T]):
    data: list[T]
    pagination: CursorInfo
