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

List endpoints return a `Page` (`.data`, `.pagination`). Listing endpoints (eBay/Cardmarket) return a `CursorPage`. Both resources expose iterators so you don't track pages or cursors:

```python
for card in client.cards.iterate(name="charizard"):
    print(card.name)

all_sets = client.sets.list_all(language="english")

for sale in client.cards.listings.iterate_ebay(789, grader="PSA", grade="10"):
    print(sale.title, sale.price)
```

## Currency

Every price has a `currency` field. Pass `currency="usd"` or `currency="eur"` to filter, or leave it off to get everything your plan allows. EUR (Cardmarket) prices need a Pro plan; a free key asking for `eur` raises `ForbiddenError`.

```python
card = client.cards.get(789, currency="usd")
```

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
