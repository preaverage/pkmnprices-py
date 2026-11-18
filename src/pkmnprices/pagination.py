from __future__ import annotations

from typing import Any, AsyncIterator, Awaitable, Callable, Iterator, TypeVar

from .models import CursorPage, Page

T = TypeVar("T")

# Where a walk over the set, card or sealed list stands: a page number, or the
# keyset cursor that replaces it.
ListPosition = tuple[int, str | None]


def _list_request(position: ListPosition) -> tuple[int | None, str | None]:
    page, cursor = position
    # A cursor replaces the page number: the API refuses both together.
    return (None, cursor) if cursor is not None else (page, None)


def _next_list_position(position: ListPosition, result: Page[Any]) -> ListPosition | None:
    """The position after ``result``, or None when the walk is over."""
    page, cursor = position
    info = result.pagination

    if info.next_cursor:
        return page, info.next_cursor

    # Under a cursor `page` stays at 1, so only a page-number walk can
    # continue past a null cursor.
    if cursor is not None or page >= info.total_pages or not result.data:
        return None

    return page + 1, None


def paginate_list(
    fetch_page: Callable[[int | None, str | None], Page[T]],
    page: int | None = None,
    cursor: str | None = None,
) -> Iterator[T]:
    """Walks the set, card and sealed lists.

    Follows the keyset cursor whenever the API hands one out, and falls back to
    page numbers on price-ordered lists, which have no cursor.
    """
    position: ListPosition | None = (page or 1, cursor)
    while position is not None:
        result = fetch_page(*_list_request(position))
        yield from result.data

        position = _next_list_position(position, result)


async def paginate_list_async(
    fetch_page: Callable[[int | None, str | None], Awaitable[Page[T]]],
    page: int | None = None,
    cursor: str | None = None,
) -> AsyncIterator[T]:
    position: ListPosition | None = (page or 1, cursor)
    while position is not None:
        result = await fetch_page(*_list_request(position))
        for item in result.data:
            yield item

        position = _next_list_position(position, result)


def paginate(fetch_page: Callable[[int], Page[T]], start: int = 1) -> Iterator[T]:
    page = start
    while True:
        result = fetch_page(page)
        yield from result.data

        if page >= result.pagination.total_pages or not result.data:
            return
        page += 1


def paginate_cursor(fetch_page: Callable[[str | None], CursorPage[T]]) -> Iterator[T]:
    cursor: str | None = None
    while True:
        result = fetch_page(cursor)
        yield from result.data

        info = result.pagination
        if not info.has_more or info.next_cursor is None:
            return
        cursor = info.next_cursor


async def paginate_async(
    fetch_page: Callable[[int], Awaitable[Page[T]]], start: int = 1
) -> AsyncIterator[T]:
    page = start
    while True:
        result = await fetch_page(page)
        for item in result.data:
            yield item

        if page >= result.pagination.total_pages or not result.data:
            return
        page += 1


async def paginate_cursor_async(
    fetch_page: Callable[[str | None], Awaitable[CursorPage[T]]],
) -> AsyncIterator[T]:
    cursor: str | None = None
    while True:
        result = await fetch_page(cursor)
        for item in result.data:
            yield item

        info = result.pagination
        if not info.has_more or info.next_cursor is None:
            return
        cursor = info.next_cursor
