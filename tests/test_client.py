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


def test_sealed_get_passes_currency() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return _json({
            "id": 1,
            "tcg_player_id": 2,
            "name": "Box",
            "image_url": None,
            "cardmarket_url": None,
            "cardmarket_product_id": None,
            "set": {"id": 3, "name": "Set"},
            "prices": [],
        })

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    client.sealed.get(1, currency="eur")

    url = httpx.URL(seen["url"])
    assert url.path == "/v1/sealed/1"
    assert dict(url.params) == {"currency": "eur"}


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


def test_cardmarket_condition_price() -> None:
    payload = {
        "id": 1, "tcg_player_id": 1, "name": "Test", "image_url": None,
        "number": "001", "total_set_number": "100", "rarity": None,
        "artist": None, "hp": None, "set": {"id": 1, "name": "Set"},
        "prices": [{
            "source": "cardmarket", "currency": "EUR", "condition": "Near Mint",
            "variant": "Reverse Holofoil", "market_price": 39.99,
            "created_at": "2026-08-11T08:30:00Z",
        }],
    }

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(lambda r: _json(payload)))
    card = client.cards.get(1)
    price = card.prices[0]
    assert price.source == "cardmarket"
    assert price.market_price == 39.99
    assert price.condition == "Near Mint"
    assert price.variant == "Reverse Holofoil"


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
        return _json({"data": [{"id": state["n"], "title": "t", "price": 1.0,
                                "grader": None, "grade": None,
                                "sold_at": "2025-01-01", "listing_url": "u"}],
                      "pagination": {"has_more": more, "next_cursor": "abc" if more else None, "count": 1}})

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    assert len(client.cards.listings.all_ebay(789)) == 2


def test_ebay_listings_graded_param() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return _json({"data": [{"id": 1, "title": "PSA 10", "price": 10.0,
                                "grader": "PSA", "grade": "10",
                                "sold_at": "2025-01-01", "listing_url": None}],
                      "pagination": {"has_more": False, "next_cursor": None, "count": 1}})

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    page = client.cards.listings.ebay(789, graded=True, grader="PSA", grade="10")
    assert page.data[0].grader == "PSA"
    assert page.data[0].listing_url is None
    assert "graded=true" in captured["url"]
    assert "grader=PSA" in captured["url"]


def test_ebay_listings_carry_attribution_and_ingestion_time() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json({"data": [{"id": 1, "title": "Snorlax 051", "price": 10.0,
                                "grader": None, "grade": None,
                                "variant": "Holofoil", "attribution": "shared",
                                "sold_at": "2025-01-01",
                                "ingested_at": "2025-01-03T04:12:07Z",
                                "listing_url": None}],
                      "pagination": {"has_more": False, "next_cursor": None, "count": 1}})

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    sale = client.cards.listings.ebay(17679).data[0]

    # "shared" means this sale is also served under another card, so it prices
    # the group rather than the entity that was asked for.
    assert sale.attribution == "shared"
    assert sale.variant == "Holofoil"
    assert sale.ingested_at != sale.sold_at


def test_ebay_listings_pass_variant_and_since() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return _json({"data": [], "pagination": {"has_more": False, "next_cursor": None, "count": 0}})

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    client.cards.listings.ebay(789, variant="Holofoil", since="2026-09-01T02:40:15.126147Z")

    url = httpx.URL(captured["url"])
    assert dict(url.params)["variant"] == "Holofoil"
    assert dict(url.params)["since"] == "2026-09-01T02:40:15.126147Z"

    client.sealed.listings.ebay(5678, since="2026-09-01")
    assert dict(httpx.URL(captured["url"]).params)["since"] == "2026-09-01"


def test_tcgplayer_listings_carry_snapshot_time() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json({"data": [{"id": 1, "listing_id": 2, "printing": "Holofoil",
                                "condition": "Near Mint", "language": "English",
                                "price": 57.72, "shipping_price": 0.0,
                                "seller_name": "CollectorsRealm", "seller_id": "1",
                                "seller_rating": 100.0, "seller_sales": "5000",
                                "quantity": 1, "listing_type": "standard",
                                "direct_seller": False, "gold_seller": True,
                                "verified_seller": True, "custom_title": None,
                                "updated_at": "2026-09-01T02:40:15+00:00",
                                "snapshot_at": "2026-09-03T02:41:12Z"}],
                      "pagination": {"has_more": False, "next_cursor": None, "count": 1}})

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    offer = client.cards.listings.tcgplayer(31194).data[0]

    # updated_at is when the offer last changed, snapshot_at when we last
    # looked. Reading the first as freshness is the mistake this field exists
    # to prevent.
    assert offer.updated_at == "2026-09-01T02:40:15+00:00"
    assert offer.snapshot_at == "2026-09-03T02:41:12Z"

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


def test_sealed_tcgplayer_listings() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return _json({"data": [{"id": 9, "listing_id": 991122, "printing": "",
                                "condition": "Unopened", "language": "English", "price": 128.99,
                                "shipping_price": 0.0, "seller_name": "SealedVault", "seller_id": "77321",
                                "seller_rating": 99.2, "seller_sales": "10000+", "quantity": 4,
                                "listing_type": "standard", "direct_seller": False, "gold_seller": True,
                                "verified_seller": True, "custom_title": None,
                                "updated_at": "2026-08-13T09:10:00+00:00"}],
                      "pagination": {"has_more": False, "next_cursor": None, "count": 1}})

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    listings = client.sealed.listings.all_tcgplayer(5678, sort="price_asc")
    assert len(listings) == 1
    assert listings[0].seller_name == "SealedVault"
    assert listings[0].condition == "Unopened"
    assert "/v1/sealed/5678/listings/tcgplayer" in captured["url"]
    assert "sort=price_asc" in captured["url"]


def test_sealed_ebay_listings() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return _json({"data": [{"id": 4, "title": "Obsidian Flames Booster Box", "price": 119.0,
                                "grader": None, "grade": None, "sold_at": "2026-08-01",
                                "listing_url": "https://example.test/x"}],
                      "pagination": {"has_more": False, "next_cursor": None, "count": 1}})

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    page = client.sealed.listings.ebay(5678, min_price=100.0)
    assert page.data[0].grader is None
    assert page.data[0].price == 119.0
    assert "/v1/sealed/5678/listings/ebay" in captured["url"]
    assert "min_price=100" in captured["url"]


def test_cardmarket_listings() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return _json({"data": [{
            "id": 3456, "article_id": 1789012345, "price": 38.5,
            "variant": "Reverse Holofoil", "condition": "Near Mint",
            "seller": "CardKingdomEU", "quantity": 2, "language": "EN",
            "comment": None, "updated_at": "2026-08-11T14:22:00+00:00",
        }], "pagination": {"has_more": False, "next_cursor": None, "count": 1}})

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    listings = client.cards.listings.all_cardmarket(
        789, condition="Near Mint", variant="Reverse Holo",
    )
    assert len(listings) == 1
    assert listings[0].seller == "CardKingdomEU"
    assert listings[0].language == "EN"
    assert "/v1/cards/789/listings/cardmarket" in captured["url"]
    assert "variant=Reverse+Holo" in captured["url"]


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
