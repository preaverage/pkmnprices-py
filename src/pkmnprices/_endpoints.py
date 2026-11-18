from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from .models import CardsExport, CursorInfo, CursorPage, Model, Page, PageInfo

_FILENAME_PATTERN = re.compile(r'filename="?([^";]+)"?', re.IGNORECASE)
_DEFAULT_EXPORT_NAME = "pkmnprices-cards.csv.gz"


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, Any] = field(default_factory=dict)
    auth: bool = True
    accept: str = "application/json"


def _clean(query: dict[str, Any]) -> dict[str, Any]:
    # List filters (seller_country, sale_type) are comma-separated on the wire.
    return {
        key: ",".join(value) if isinstance(value, (list, tuple)) else value
        for key, value in query.items()
        if value is not None
    }


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


def cards_sales_volume(card_id: int, **query: Any) -> Request:
    return Request("GET", f"/v1/cards/{card_id}/sales/volume", _clean(query))


def cards_population(card_id: int, **query: Any) -> Request:
    return Request("GET", f"/v1/cards/{card_id}/population", _clean(query))


def cards_markers() -> Request:
    return Request("GET", "/v1/cards/markers")


def cards_export() -> Request:
    return Request("GET", "/v1/export/cards", accept="application/gzip")


def cards_listings_ebay(card_id: int, **query: Any) -> Request:
    return Request("GET", f"/v1/cards/{card_id}/listings/ebay", _clean(query))


def cards_listings_cardmarket(card_id: int, **query: Any) -> Request:
    return Request("GET", f"/v1/cards/{card_id}/listings/cardmarket", _clean(query))


def cards_listings_tcgplayer(card_id: int, **query: Any) -> Request:
    return Request("GET", f"/v1/cards/{card_id}/listings/tcgplayer", _clean(query))


def sealed_list(**query: Any) -> Request:
    return Request("GET", "/v1/sealed", _clean(query))


def sealed_get(sealed_id: int, **query: Any) -> Request:
    return Request("GET", f"/v1/sealed/{sealed_id}", _clean(query))


def sealed_history(sealed_id: int, **query: Any) -> Request:
    return Request("GET", f"/v1/sealed/{sealed_id}/prices/history", _clean(query))


def sealed_listings_ebay(sealed_id: int, **query: Any) -> Request:
    return Request("GET", f"/v1/sealed/{sealed_id}/listings/ebay", _clean(query))


def sealed_listings_tcgplayer(sealed_id: int, **query: Any) -> Request:
    return Request("GET", f"/v1/sealed/{sealed_id}/listings/tcgplayer", _clean(query))


def sealed_listings_cardmarket(sealed_id: int, **query: Any) -> Request:
    return Request("GET", f"/v1/sealed/{sealed_id}/listings/cardmarket", _clean(query))


def build_page(raw: dict[str, Any], model: type[Model]) -> Page[Any]:
    items = [model.from_dict(item) for item in raw["data"]]
    return Page(items, PageInfo.from_dict(raw["pagination"]))


def build_cursor_page(raw: dict[str, Any], model: type[Model]) -> CursorPage[Any]:
    items = [model.from_dict(item) for item in raw["data"]]
    return CursorPage(items, CursorInfo.from_dict(raw["pagination"]))


def build_export(headers: httpx.Headers, path: str | os.PathLike[str] | None) -> CardsExport:
    """Describes an export download and decides where its file goes.

    With no ``path`` the file takes the server's name in the working directory.
    """
    match = _FILENAME_PATTERN.search(headers.get("content-disposition", ""))
    filename = match.group(1) if match else None
    remaining = headers.get("x-export-downloads-remaining", "")

    return CardsExport(
        path=Path(path) if path is not None else Path(filename or _DEFAULT_EXPORT_NAME),
        filename=filename,
        downloads_remaining=int(remaining) if remaining.isdigit() else None,
    )
