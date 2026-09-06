"""Shared historical event-tape acquisition.

The core cost-control principle is: query a protocol/event family once per
block range, then join/filter locally. Never issue one log scan per token when
the same event family can be acquired as a shared tape.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Callable, Iterable, Iterator, TypeVar

from hlp.data.rpc import RpcClient
from hlp.data.types import RawLog


T = TypeVar("T")


def iter_event_tape(
    rpc: RpcClient,
    *,
    from_block: int,
    to_block: int,
    topic0: str,
    address: str | list[str] | None = None,
    chunk_size: int = 100_000,
    min_chunk_size: int = 1,
) -> Iterator[RawLog]:
    """Yield a complete ordered tape for one event signature."""
    yield from rpc.iter_logs_chunked(
        from_block,
        to_block,
        address=address,
        topics=[topic0],
        chunk_size=chunk_size,
        min_chunk_size=min_chunk_size,
    )


def decode_tape(
    rows: Iterable[RawLog],
    decoder: Callable[[RawLog], T],
) -> Iterator[T]:
    for row in rows:
        yield decoder(row)


def filter_by_addresses(
    rows: Iterable[T],
    addresses: set[str],
    *,
    attribute: str,
) -> Iterator[T]:
    """Filter decoded rows against a normalized local address registry."""
    wanted = {value.lower() for value in addresses}
    for row in rows:
        value = getattr(row, attribute).lower()
        if value in wanted:
            yield row
