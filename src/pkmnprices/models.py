from __future__ import annotations

import dataclasses
import types as _types
from typing import Any, Generic, Literal, TypeVar, Union, get_args, get_origin, get_type_hints

Currency = Literal["USD", "EUR"]
PriceSource = Literal["tcgplayer", "ebay", "cardmarket"]
HealthStatus = Literal["healthy", "degraded", "unreachable"]

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
    ebay_listing_id: str
    title: str
    price: float
    grader: str | None
    grade: str | None
    sale_type: str
    sold_at: str
    listing_url: str


@dataclasses.dataclass
class CardmarketListing(Model):
    id: int
    article_id: int
    price: float
    variant: str | None
    condition: str | None
    seller: str
    quantity: int
    language: str | None
    comment: str | None
    updated_at: str


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
    updated_at: str


@dataclasses.dataclass
class SealedSummary(Model):
    id: int
    tcg_player_id: int
    name: str
    image_url: str | None
    set: SetRef


@dataclasses.dataclass
class Sealed(SealedSummary):
    prices: list[Price] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class SealedEbayListing(Model):
    id: int
    ebay_listing_id: str
    title: str
    price: float
    sale_type: str
    sold_at: str
    listing_url: str


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
