# pkmnprices

Python client for the [Pkmn Prices API](https://pkmnprices.com). Pokemon TCG card pricing from TCGPlayer, Cardmarket, and eBay.

Sync and async clients, both built on httpx. Typed responses, typed errors, and iterators that page through results for you. Python 3.10+.

## Install

```bash
pip install pkmnprices
```

## Usage

```python
from pkmnprices import PkmnPrices

client = PkmnPrices("pk_your_key_here")

page = client.cards.list(name="charizard", per_page=10)

card = client.cards.get(page.data[0].id)
for price in card.prices:
    symbol = "€" if price.currency == "EUR" else "$"
    print(f"{price.source}: {symbol}{price.market_price}")

client.close()
```

The client is also a context manager:

```python
with PkmnPrices("pk_...") as client:
    health = client.health()
```

### Async

```python
import asyncio
from pkmnprices import AsyncPkmnPrices

async def main():
    async with AsyncPkmnPrices("pk_...") as client:
        page = await client.cards.list(name="charizard")
        async for card in client.cards.iterate(name="charizard"):
            print(card.name)

asyncio.run(main())
```

Get an API key from <https://pkmnprices.com/dashboard>.

## Options

```python
PkmnPrices(
    "pk_...",         # API key, sent as the x-api-key header
    max_retries=2,    # retries on 429 rate limits and 5xx/network errors
    timeout=30.0,     # per-request timeout in seconds
)
```

Rate-limit `429`s are retried with backoff. Credit-limit `429`s (`credit_limit_exceeded`) are not, since they don't reset until the next day.

## Pagination

List endpoints return a `Page` (`.data`, `.pagination`). Listing endpoints (eBay, Cardmarket, and TCGplayer) return a `CursorPage`. Both resources expose iterators so you don't track pages or cursors:

```python
for card in client.cards.iterate(name="charizard"):
    print(card.name)

all_sets = client.sets.list_all(language="english")

for sale in client.cards.listings.iterate_ebay(789, graded=True, grader="PSA", grade="10"):
    print(sale.title, sale.price)

for offer in client.cards.listings.iterate_cardmarket(789, condition="Near Mint", variant="Reverse Holo"):
    print(offer.seller, offer.price, offer.language)

for offer in client.cards.listings.iterate_tcgplayer(789, condition="Near Mint"):
    print(offer.seller_name, offer.price, offer.shipping_price)
```

Sealed products carry the same two listing sources, under `client.sealed.listings`:

```python
for offer in client.sealed.listings.iterate_tcgplayer(5678):
    print(offer.seller_name, offer.price, offer.quantity)

for sale in client.sealed.listings.iterate_ebay(5678, sort="price_desc"):
    print(sale.title, sale.price, sale.sold_at)
```

Sealed TCGplayer offers are normally condition `"Unopened"` with an empty
`printing`, so those two filters rarely narrow anything. Sealed eBay sales are
never graded, so `graded`, `grader`, and `grade` aren't accepted there and
`grader`/`grade` come back `None`. The async client mirrors all of these on
`AsyncPkmnPrices`.

## Which card a comp is really about

A variant and its base card can map to one source product page. When that
happens, both serve the same sales, and the titles describe whichever printing
the seller actually sold. Every eBay comp says which case it is:

```python
for sale in client.cards.listings.iterate_ebay(17679):
    if sale.attribution == "shared":
        continue  # another card's evidence
    print(sale.variant, sale.title, sale.price)
```

`exact` means the source page belongs to this card alone. `shared` means the
sale appears under at least one other card too, so it prices the group rather
than this entity. `unknown` means the comp was collected before the source
printing was recorded. A feed that is entirely `shared` is not evidence about
the card you asked for.

`variant` also works as a filter, so a card mapped for more than one printing
can be read one printing at a time:

```python
holo = client.cards.listings.all_ebay(789, variant="Holofoil")
```

## Polling for new comps

Credits are charged per row returned, so re-reading a page of comps you already
hold to find out that nothing changed is the expensive way to stay current.
`since` returns only what arrived after a point you name:

```python
checkpoint = "2026-09-01T02:40:15.126147Z"

page = client.cards.listings.ebay(789, since=checkpoint)
for sale in page.data:
    print(sale.title, sale.price)
if page.data:
    checkpoint = page.data[0].ingested_at
```

Checkpoint on `ingested_at`, not `sold_at`. They are different: `sold_at` is
when the sale happened, `ingested_at` is when we collected it, and a collection
run regularly brings in sales that are weeks old. A sale-date bound would step
over those permanently.

The bound is exclusive, so passing back the `ingested_at` you were given never
repeats that row. `since` also accepts a bare `YYYY-MM-DD` (midnight UTC),
which suits a backfill more than a poll: re-running it the same day returns the
same rows, and pays for them again.

A card with nothing new returns an empty `data` list.

## TCGplayer freshness

`updated_at` on a TCGplayer offer is not a freshness signal. It moves only when
that listing's own price, quantity or seller details change, so an offer that
has been live and unchanged for a month keeps a month-old `updated_at` however
recently it was confirmed.

`snapshot_at` is the freshness field: when that product's listings were last
confirmed against TCGplayer. It is the same for every row in a response, since
a snapshot replaces a product's listings wholesale. Listings refresh daily, so
a `snapshot_at` well over a day old means that product's last fetch did not
succeed and you are looking at the previous snapshot.

One thing `snapshot_at` cannot tell you: listings are collected from a US
vantage point with no shipping-destination filter, so a response can contain
offers TCGplayer's own site hides from you when you browse it from elsewhere.

## Cardmarket special attributes

Cardmarket sells more than one kind of good under a single card. Every
Cardmarket offer carries three booleans, and they are always present:

```python
for offer in client.cards.listings.iterate_cardmarket(789):
    if offer.graded:
        print(offer.grader, offer.grade)  # "PSA", "10"
    if offer.signed or offer.altered:
        continue  # not a clean card
```

A `signed`, `altered` or `graded` offer is real, and it is returned, but it does
**not** contribute to the card's market price. A signed and altered Near Mint
copy at EUR 200 must not set the Near Mint price of a card whose clean copies
sell for EUR 3,800, and a slab is priced for the slab rather than for the card.

The practical consequence: **the cheapest row you get back is not necessarily
the card's `market_price`.** Filter these out before deriving a price yourself.

`grader` and `grade` are named to match the graded eBay sale shape, so "PSA 10"
reads the same whichever source it came from. Both are `None` unless `graded`
is true, and can be `None` even then — Cardmarket flags a slab without always
naming the grader, and the details are read from free-text seller comments.

## Languages

A card's language comes from its set, and it decides what pricing that card can
ever have.

| Language | Cards | Pricing | Plan |
|----------|-------|---------|------|
| English | 28,158 | USD (TCGplayer, eBay) + EUR (Cardmarket) | Free |
| Japanese | 29,660 | USD + EUR | Pro+ |
| German | 13,078 | EUR (Cardmarket) only | Pro+ |

```python
german = client.cards.list(language="German", currency="eur")
```

Spelling is normalised: `"German"`, `"german"`, `"de"` and `"DE"` all resolve to
the same thing, and responses come back in the canonical form (`"German"`).

**German cards have no USD price and never will** — TCGplayer does not sell
German product. Asking for German with `currency="usd"` returns an empty list
rather than an error, so reach for `"eur"`.

A free key is limited to English. Asking for Japanese or German raises
`ForbiddenError`, and omitting `language` returns English only rather than the
whole catalogue.

German coverage runs from HeartGold & SoulSilver (2010) to current sets.

## Currency

Every price has a `currency` field. Pass `currency="usd"` or `currency="eur"` to filter, or leave it off to get everything your plan allows. EUR (Cardmarket) prices need a Pro plan; a free key asking for `eur` raises `ForbiddenError`.

```python
card = client.cards.get(789, currency="usd")
box = client.sealed.get(5678, currency="eur")
```

Cardmarket current prices are condition- and printing-specific marketplace
prices. Each EUR row has one `market_price` for its exact `condition` and
`variant`; for example, a Near Mint Reverse Holofoil price is distinct from a
Mint or Normal price. The retired Price Guide `low`, `trend`, and `avg` fields
are not returned. Live Cardmarket listings are automatically restricted to the
card's language.

## Cardmarket Mapping

Card and sealed detail responses expose Cardmarket's stable product identifiers
when a mapping is available:

```python
card = client.cards.get(789)
print(card.cardmarket_url)
print(card.cardmarket_product_id)

box = client.sealed.get(5678)
print(box.cardmarket_url)
print(box.cardmarket_product_id)
```

Both fields are `None` until the product has been mapped.

## Errors

Everything raised subclasses `PkmnPricesError`, which carries `status`, `code`, `rate_limit`, and `retry_after`.

```python
from pkmnprices import ForbiddenError, NotFoundError, RateLimitError

try:
    client.cards.get(789, currency="eur")
except ForbiddenError:
    ...  # needs a higher plan
except NotFoundError:
    ...  # no such card
except RateLimitError:
    ...  # ran out of retries
```

Subclasses: `BadRequestError` (400), `UnauthorizedError` (401), `ForbiddenError` (403), `NotFoundError` (404), `ConflictError` (409), `CreditLimitError` and `RateLimitError` (429), `InternalServerError` (5xx), `APIConnectionError` (network/timeout).

## License

MIT
