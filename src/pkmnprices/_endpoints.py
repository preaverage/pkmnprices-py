from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import CursorInfo, CursorPage, Model, Page, PageInfo


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, Any] = field(default_factory=dict)
    auth: bool = True


def _clean(query: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in query.items() if value is not None}


def health() -> Request:
    return Request("GET", "/health", auth=False)


def sets_list(**query: Any) -> Request:
    return Request("GET", "/v1/sets", _clean(query))


def sets_get(set_id: int) -> Request:
    return Request("GET", f"/v1/sets/{set_id}")


def cards_list(**query: Any) -> Request:
    return Request("GET", "/v1/cards", _clean(query))


def cards_get(card_id: int, **query: Any) -> Request:
    return Request("GET", f"/v1/cards/{card_id}", _clean(query))


def cards_history(card_id: int, **query: Any) -> Request:
    return Request("GET", f"/v1/cards/{card_id}/prices/history", _clean(query))


def cards_listings_ebay(card_id: int, **query: Any) -> Request:
    return Request("GET", f"/v1/cards/{card_id}/listings/ebay", _clean(query))


def cards_listings_cardmarket(card_id: int, **query: Any) -> Request:
    return Request("GET", f"/v1/cards/{card_id}/listings/cardmarket", _clean(query))


def cards_listings_tcgplayer(card_id: int, **query: Any) -> Request:
    return Request("GET", f"/v1/cards/{card_id}/listings/tcgplayer", _clean(query))


def sealed_list(**query: Any) -> Request:
    return Request("GET", "/v1/sealed", _clean(query))


def sealed_get(sealed_id: int) -> Request:
    return Request("GET", f"/v1/sealed/{sealed_id}")


def sealed_history(sealed_id: int, **query: Any) -> Request:
    return Request("GET", f"/v1/sealed/{sealed_id}/prices/history", _clean(query))


def sealed_listings(sealed_id: int, **query: Any) -> Request:
    return Request("GET", f"/v1/sealed/{sealed_id}/listings", _clean(query))


def build_page(raw: dict[str, Any], model: type[Model]) -> Page[Any]:
    items = [model.from_dict(item) for item in raw["data"]]
    return Page(items, PageInfo.from_dict(raw["pagination"]))


def build_cursor_page(raw: dict[str, Any], model: type[Model]) -> CursorPage[Any]:
    items = [model.from_dict(item) for item in raw["data"]]
    return CursorPage(items, CursorInfo.from_dict(raw["pagination"]))
