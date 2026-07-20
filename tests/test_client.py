from __future__ import annotations

import json

import httpx
import pytest

from pkmnprices import AsyncPkmnPrices, ForbiddenError, CreditLimitError, PkmnPrices


def _json(payload: object, status: int = 200, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(status, content=json.dumps(payload), headers={"content-type": "application/json", **(headers or {})})


def test_auth_header_and_query() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("x-api-key")
        return _json({"data": [], "pagination": {"page": 1, "per_page": 50, "total": 0, "total_pages": 0}})

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    client.cards.list(name="charizard", per_page=10, currency="usd")

    url = httpx.URL(seen["url"])
    assert seen["key"] == "pk_test"
    assert url.path == "/v1/cards"
    assert dict(url.params) == {"name": "charizard", "per_page": "10", "currency": "usd"}


def test_forbidden_maps_to_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json({"error": {"code": "forbidden", "message": "needs pro"}}, 403)

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    with pytest.raises(ForbiddenError) as exc:
        client.cards.get(1, currency="eur")

    assert exc.value.status == 403
    assert exc.value.code == "forbidden"


def test_card_model_parsing() -> None:
    payload = {
        "id": 789, "tcg_player_id": 519184, "name": "Charizard ex", "image_url": None,
        "cardmarket_url": "/en/Pokemon/Products/Singles/Obsidian-Flames/Charizard-ex-OBF006",
        "cardmarket_product_id": 733537,
        "number": "006", "total_set_number": "197", "rarity": "Double Rare",
        "artist": "PLANETA", "hp": 330, "set": {"id": 123, "name": "Obsidian Flames"},
        "prices": [{"source": "tcgplayer", "currency": "USD", "condition": "Near Mint",
                    "variant": "Holofoil", "market_price": 42.5, "created_at": "2025-01-15T08:30:00Z"}],
    }

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(lambda r: _json(payload)))
    card = client.cards.get(789)

    assert card.name == "Charizard ex"
    assert card.cardmarket_product_id == 733537
    assert card.cardmarket_url.endswith("Charizard-ex-OBF006")
    assert card.set.name == "Obsidian Flames"
    assert card.prices[0].market_price == 42.5
    assert card.prices[0].currency == "USD"


def test_page_auto_pagination() -> None:
    state = {"page": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["page"] += 1
        p = state["page"]
        return _json({"data": [{"id": p, "tcg_player_id": 0, "name": "s", "language": "english", "card_count": 0}],
                      "pagination": {"page": p, "per_page": 1, "total": 3, "total_pages": 3}})

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    assert len(client.sets.list_all()) == 3


def test_cursor_pagination() -> None:
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        more = state["n"] < 2
        return _json({"data": [{"id": state["n"], "ebay_listing_id": "x", "title": "t", "price": 1.0,
                                "grader": None, "grade": None, "sale_type": "auction",
                                "sold_at": "2025-01-01", "listing_url": "u"}],
                      "pagination": {"has_more": more, "next_cursor": "abc" if more else None, "count": 1}})

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    assert len(client.cards.listings.all_ebay(789)) == 2


def test_tcgplayer_listings() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return _json({"data": [{"id": 1, "listing_id": 274183167, "printing": "1st Edition Holofoil",
                                "condition": "Near Mint", "language": "English", "price": 4650.0,
                                "shipping_price": 0.0, "seller_name": "Cash Cow Games", "seller_id": "120594",
                                "seller_rating": 100.0, "seller_sales": "50000+", "quantity": 1,
                                "listing_type": "standard", "direct_seller": False, "gold_seller": True,
                                "verified_seller": False, "custom_title": None, "updated_at": "2026-06-17T03:44:00+00:00"}],
                      "pagination": {"has_more": False, "next_cursor": None, "count": 1}})

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    listings = client.cards.listings.all_tcgplayer(789, condition="Near Mint", printing="1st Edition Holofoil")
    assert len(listings) == 1
    assert listings[0].seller_name == "Cash Cow Games"
    assert listings[0].shipping_price == 0.0
    assert "/v1/cards/789/listings/tcgplayer" in captured["url"]
    assert "printing=1st+Edition+Holofoil" in captured["url"]


def test_retry_on_rate_limit_then_succeed() -> None:
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        if state["n"] == 1:
            return _json({"error": {"code": "rate_limit_exceeded", "message": "slow"}}, 429, {"retry-after": "0"})
        return _json({"status": "healthy", "database": "connected"})

    client = PkmnPrices("pk_test", max_retries=2, _transport=httpx.MockTransport(handler))
    assert client.health().status == "healthy"
    assert state["n"] == 2


def test_credit_limit_not_retried() -> None:
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        return _json({"error": {"code": "credit_limit_exceeded", "message": "out"}}, 429)

    client = PkmnPrices("pk_test", max_retries=3, _transport=httpx.MockTransport(handler))
    with pytest.raises(CreditLimitError):
        client.health()
    assert state["n"] == 1


async def test_async_client() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["key"] = request.headers.get("x-api-key")
        return _json({"id": 1, "tcg_player_id": 0, "name": "Charizard ex", "image_url": None,
                      "number": None, "total_set_number": None, "rarity": None, "artist": None,
                      "hp": None, "set": {"id": 1, "name": "s"}, "prices": []})

    async with AsyncPkmnPrices("pk_test", _transport=httpx.MockTransport(handler)) as client:
        card = await client.cards.get(789, currency="usd")
        assert card.name == "Charizard ex"
        assert seen["key"] == "pk_test"
