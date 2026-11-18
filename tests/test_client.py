from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from pkmnprices import AsyncPkmnPrices, CreditLimitError, ForbiddenError, PkmnPrices


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
        return _json({"error": {"code": "forbidden", "message": "needs pro",
                                "docs_url": "https://www.pkmnprices.com/pricing"}}, 403)

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    with pytest.raises(ForbiddenError) as exc:
        client.cards.get(1, currency="eur")

    assert exc.value.status == 403
    assert exc.value.code == "forbidden"
    assert exc.value.docs_url == "https://www.pkmnprices.com/pricing"


def test_error_without_docs_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json({"error": {"code": "forbidden", "message": "needs pro"}}, 403)

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    with pytest.raises(ForbiddenError) as exc:
        client.cards.get(1, currency="eur")
    assert exc.value.docs_url is None


def test_price_history_passes_condition_and_variant() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return _json({"data": [], "pagination": {"page": 1, "per_page": 30, "total": 0, "total_pages": 0}})

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    client.cards.price_history(789, condition="Near Mint", variant="Holofoil")
    assert "condition=Near+Mint" in captured["url"]
    assert "variant=Holofoil" in captured["url"]


def test_ebay_listing_carries_grade_qualifier() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json({"data": [{"id": 1, "title": "CGC 10 Pristine", "price": 900.0, "grader": "CGC",
                                "grade": "10", "grade_qualifier": "Pristine", "variant": "Holofoil",
                                "attribution": "exact", "sold_at": "2026-08-01",
                                "ingested_at": "2026-08-02T00:00:00Z", "listing_url": None}],
                      "pagination": {"has_more": False, "next_cursor": None, "count": 1}})

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    sale = client.cards.listings.ebay(789, grader="CGC", grade="10").data[0]
    assert sale.grade == "10"
    assert sale.grade_qualifier == "Pristine"


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


def test_ebay_listings_carry_currency_seller_country_and_sale_type() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json({"data": [{"id": 9012, "title": "Mega-Glurak X ex 125/094", "price": 900.0,
                                "currency": "EUR", "seller_country": None,
                                "sale_type": "best_offer_accepted",
                                "grader": "AOG", "grade": "10", "grade_qualifier": None,
                                "variant": None, "attribution": "exact",
                                "sold_at": "2026-08-24",
                                "ingested_at": "2026-09-17T11:30:15Z",
                                "listing_url": None}],
                      "pagination": {"has_more": False, "next_cursor": None, "count": 1}})

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    sale = client.cards.listings.ebay(31194).data[0]

    assert sale.currency == "EUR"
    assert sale.seller_country is None
    assert sale.sale_type == "best_offer_accepted"


def test_ebay_listings_pass_country_qualifier_and_sale_type_filters() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return _json({"data": [], "pagination": {"has_more": False, "next_cursor": None, "count": 0}})

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    client.cards.listings.ebay(
        789, grader="BGS", grade="10", grade_qualifier="black_label",
        seller_country=["US", "PR"], exclude_seller_country="CN,HK",
        sale_type=["auction", "best_offer_accepted"],
    )

    params = dict(httpx.URL(captured["url"]).params)
    assert params["grade_qualifier"] == "black_label"
    assert params["seller_country"] == "US,PR"
    assert params["exclude_seller_country"] == "CN,HK"
    assert params["sale_type"] == "auction,best_offer_accepted"

    client.cards.listings.ebay(789, sale_type="auction")
    assert dict(httpx.URL(captured["url"]).params)["sale_type"] == "auction"


def test_cardmarket_listings_seller_country() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return _json({"data": [{
            "id": 3456, "article_id": 1789012345, "price": 38.5,
            "variant": "Reverse Holofoil", "condition": "Near Mint",
            "seller": "CardKingdomEU", "quantity": 2, "language": "EN",
            "comment": None, "updated_at": "2026-08-11T14:22:00+00:00",
            "signed": False, "altered": False, "graded": False,
            "grader": None, "grade": None, "opened": False, "sell_count": 2022,
            "seller_country": "IT",
        }], "pagination": {"has_more": False, "next_cursor": None, "count": 1}})

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    offer = client.cards.listings.cardmarket(789, seller_country=["it", "de"]).data[0]

    assert offer.seller_country == "IT"
    assert dict(httpx.URL(captured["url"]).params)["seller_country"] == "it,de"

    client.sealed.listings.cardmarket(1430, exclude_seller_country=["CN"])
    params = dict(httpx.URL(captured["url"]).params)
    assert params["exclude_seller_country"] == "CN"
    assert "seller_country" not in params


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


def test_card_tcgplayer_listings_total_sort() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return _json({"data": [], "pagination": {"has_more": False, "next_cursor": None, "count": 0}})

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    assert client.cards.listings.all_tcgplayer(789, sort="total_asc") == []
    assert "/v1/cards/789/listings/tcgplayer" in captured["url"]
    assert "sort=total_asc" in captured["url"]


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


def test_cardmarket_listing_special_attributes_and_sell_count() -> None:
    """An unsealed offer and a no-sales seller are both excluded from the
    market price, so a caller has to be able to tell them apart from a row
    whose count was simply never recorded."""

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return _json({"data": [
            {
                "id": 1, "article_id": 11, "price": 10.0, "variant": "",
                "condition": None, "seller": "JapOn", "quantity": 1,
                "language": "EN", "comment": "Not Sealed (open, just the booster)",
                "updated_at": "2026-09-03T15:47:12+00:00",
                "signed": False, "altered": False, "graded": False,
                "grader": None, "grade": None,
                "opened": True, "sell_count": 1210,
            },
            {
                "id": 2, "article_id": 12, "price": 799.99, "variant": "",
                "condition": None, "seller": "collector0913", "quantity": 1,
                "language": "EN", "comment": "Sealed",
                "updated_at": "2026-09-03T15:47:12+00:00",
                "signed": False, "altered": False, "graded": False,
                "grader": None, "grade": None,
                "opened": False, "sell_count": 0,
            },
            {
                "id": 3, "article_id": 13, "price": 850.0, "variant": "",
                "condition": None, "seller": "Phima90", "quantity": 1,
                "language": "EN", "comment": "Sealed - holo guaranteed",
                "updated_at": "2026-09-03T15:47:12+00:00",
                "signed": False, "altered": False, "graded": False,
                "grader": None, "grade": None,
                "opened": False, "sell_count": None,
            },
        ], "pagination": {"has_more": False, "next_cursor": None, "count": 3}})

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    offers = client.sealed.listings.all_cardmarket(1430)

    assert [o.opened for o in offers] == [True, False, False]
    # None and 0 must stay distinguishable: only 0 says the seller has sold
    # nothing, and only that disqualifies an offer from setting a price.
    assert [o.sell_count for o in offers] == [1210, 0, None]
    assert offers[1].sell_count is not None
    assert offers[2].sell_count is None
    assert "/v1/sealed/1430/listings/cardmarket" in captured["url"]


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


def _list_page(ids: list[int], **pagination: object) -> httpx.Response:
    return _json({
        "data": [{"id": i, "name": "s", "language": "English"} for i in ids],
        "pagination": {"page": 1, "per_page": 2, "total": 5, "total_pages": 3, **pagination},
    })


def test_list_iteration_follows_the_keyset_cursor() -> None:
    pages = [
        _list_page([1, 2], next_cursor="c1"),
        _list_page([3, 4], next_cursor="c2"),
        _list_page([5], next_cursor=None),
    ]
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.url.params))
        return pages[len(seen) - 1]

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    sets = client.sets.list_all(language="English", per_page=2)

    assert [s.id for s in sets] == [1, 2, 3, 4, 5]
    # A cursor replaces the page number, and the filters ride along.
    assert seen == [
        {"language": "English", "page": "1", "per_page": "2"},
        {"language": "English", "per_page": "2", "cursor": "c1"},
        {"language": "English", "per_page": "2", "cursor": "c2"},
    ]


def test_price_ordered_list_pages_by_number() -> None:
    pages = [
        _list_page([1, 2], next_cursor=None, total_pages=2),
        _list_page([3], next_cursor=None, page=2, total_pages=2),
    ]
    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.params.get("page"))
        return pages[len(seen) - 1]

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))

    assert len(client.cards.list_all(sort="price_asc")) == 3
    assert seen == ["1", "2"]


def test_card_markers_parse_and_filter() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = request.url
        return _json({
            "data": [{"id": 1, "tcg_player_id": None, "name": "Pikachu", "image_url": None,
                      "number": "025", "total_set_number": "165", "rarity": "Common",
                      "pattern": "Poke Ball Pattern", "stamp": None, "stamp_number": None,
                      "distribution": "Staff", "placement": None, "artist": "Atsuko Nishida",
                      "hp": 60, "set": {"id": 1, "name": "151"}}],
            "pagination": {"page": 1, "per_page": 50, "total": 1, "total_pages": 1, "next_cursor": None},
        })

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    page = client.cards.list(pattern="Poke Ball Pattern", distribution="Staff", artist="nishida", hp=60)

    assert dict(seen["url"].params) == {
        "pattern": "Poke Ball Pattern", "distribution": "Staff", "artist": "nishida", "hp": "60",
    }
    card = page.data[0]
    assert card.tcg_player_id is None
    assert (card.pattern, card.distribution, card.stamp) == ("Poke Ball Pattern", "Staff", None)


def test_markers_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/cards/markers"
        return _json({"patterns": [{"value": "Cosmos Holo", "cards": 412}], "stamps": [],
                      "distributions": [], "placements": []})

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    markers = client.cards.markers()

    assert markers.patterns[0].value == "Cosmos Holo"
    assert markers.patterns[0].cards == 412


def test_population_builds_nested_graders() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = request.url
        return _json({"card_id": 12927, "variants": [{
            "variant": "Holofoil", "total_population": 133526, "total_gems": 1043, "gem_rate": 0.78,
            "grades": {"9": 11158, "10": 781}, "pristine": 12, "black_label": 1, "authentic": 873,
            "percent_higher": {"9": 0.91}, "last_population_change": "2026-10-18",
            "updated_at": "2026-10-18T19:29:42+00:00",
            "graders": {"PSA": {"total": 107747, "gems": 490, "gem_rate": 0.45,
                                "grades": {"10": 490}, "pristine": None, "black_label": None,
                                "authentic": 799, "altered": None, "qualified": 206,
                                "last_population_change": "2026-10-18", "pop_report_url": None,
                                "spec_id": "544027", "description": "1999 Pokemon Game Charizard-Holo"}},
        }]})

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    population = client.cards.population(12927, variant="Holofoil")

    assert seen["url"].path == "/v1/cards/12927/population"
    assert seen["url"].params["variant"] == "Holofoil"
    holo = population.variants[0]
    assert holo.grades["10"] == 781
    assert holo.graders["PSA"].total == 107747
    assert holo.graders["PSA"].pristine is None


def test_sales_volume() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = request.url
        return _json({
            "data": [{"date": "2026-10-20", "currency": "USD", "variant": None, "graded": False,
                      "sales": 7, "priced_sales": 6, "median": 41.5}],
            "pagination": {"page": 1, "per_page": 30, "total": 1, "total_pages": 1},
        })

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    days = list(client.cards.iterate_sales_volume(789, period="90d", graded=False))

    assert seen["url"].path == "/v1/cards/789/sales/volume"
    assert dict(seen["url"].params) == {"period": "90d", "graded": "false", "page": "1"}
    assert (days[0].sales, days[0].priced_sales, days[0].median) == (7, 6, 41.5)


def test_listing_filters_added_since_4_1() -> None:
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return _json({"data": [], "pagination": {"has_more": False, "next_cursor": None, "count": 0}})

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    client.cards.listings.ebay(789, updated_since="2026-11-01T00:00:00Z", period="90d")
    client.cards.listings.cardmarket(789, graded=False, signed=False, altered=False, min_sell_count=0)
    client.sealed.listings.cardmarket(5678, opened=False)
    client.sealed.listings.ebay(5678, period="30d")

    assert dict(seen[0].params) == {"updated_since": "2026-11-01T00:00:00Z", "period": "90d"}
    assert dict(seen[1].params) == {
        "graded": "false", "signed": "false", "altered": "false", "min_sell_count": "0",
    }
    assert dict(seen[2].params) == {"opened": "false"}
    assert dict(seen[3].params) == {"period": "30d"}


def test_rate_limit_error_reports_which_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json(
            {"error": {"code": "credit_limit_exceeded", "message": "daily credit limit exceeded",
                       "docs_url": "https://www.pkmnprices.com/docs/rate-limits", "limit_type": "daily",
                       "retry_after": 41230, "resets_at": "2026-10-26T00:00:00Z",
                       "upgrade_url": "https://www.pkmnprices.com/dashboard?view=billing"}},
            429,
            {"x-credits-limit": "500", "x-credits-remaining": "0", "x-credits-reset": "41230"},
        )

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    with pytest.raises(CreditLimitError) as exc:
        client.sets.get(1)

    error = exc.value
    assert error.limit_type == "daily"
    # No Retry-After header here, so the body's retry_after is the fallback.
    assert error.retry_after == 41230.0
    assert error.resets_at == "2026-10-26T00:00:00Z"
    assert error.upgrade_url == "https://www.pkmnprices.com/dashboard?view=billing"
    assert (error.rate_limit.credits_remaining, error.rate_limit.credits_reset) == (0, 41230)


_EXPORT_HEADERS = {
    "content-type": "application/gzip",
    "content-disposition": 'attachment; filename="pkmnprices-cards-2026-10-26.csv.gz"',
    "x-export-downloads-remaining": "1",
}


def test_export_writes_the_file(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/export/cards"
        assert request.headers["accept"] == "application/gzip"
        return httpx.Response(200, content=b"\x1f\x8b\x08", headers=_EXPORT_HEADERS)

    client = PkmnPrices("pk_test", _transport=httpx.MockTransport(handler))
    export = client.cards.export(tmp_path / "cards.csv.gz")

    assert export.path.read_bytes() == b"\x1f\x8b\x08"
    assert export.filename == "pkmnprices-cards-2026-10-26.csv.gz"
    assert export.downloads_remaining == 1


def test_export_is_not_retried() -> None:
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        return _json({"error": {"code": "forbidden", "message": "Daily export download limit reached"}}, 403)

    client = PkmnPrices("pk_test", max_retries=3, _transport=httpx.MockTransport(handler))
    with pytest.raises(ForbiddenError):
        client.cards.export("unused.csv.gz")

    assert state["n"] == 1


async def test_async_list_iteration_and_export(tmp_path: Path) -> None:
    pages = [_list_page([1, 2], next_cursor="c1"), _list_page([3], next_cursor=None)]
    cursors: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/export/cards":
            return httpx.Response(200, content=b"\x1f\x8b\x08", headers=_EXPORT_HEADERS)

        cursors.append(request.url.params.get("cursor"))
        return pages[len(cursors) - 1]

    async with AsyncPkmnPrices("pk_test", _transport=httpx.MockTransport(handler)) as client:
        sets = await client.sets.list_all()
        export = await client.cards.export(tmp_path / "cards.csv.gz")

    assert [s.id for s in sets] == [1, 2, 3]
    assert cursors == [None, "c1"]
    assert export.path.read_bytes() == b"\x1f\x8b\x08"
