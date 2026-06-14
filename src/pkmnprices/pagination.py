from __future__ import annotations

from typing import AsyncIterator, Awaitable, Callable, Iterator, TypeVar

from .models import CursorPage, Page

T = TypeVar("T")


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
