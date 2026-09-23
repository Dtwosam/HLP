"""Transaction-initiator enrichment for Pons market-path research."""

from __future__ import annotations

from typing import Iterable

from hlp.data.rpc import RpcClient
from hlp.data.transaction_identity import (
    attach_transaction_identities,
    fetch_transaction_identity_rows as _fetch_transaction_identity_rows,
)


def fetch_transaction_identity_rows(
    rpc: RpcClient,
    transaction_hashes: Iterable[str],
    *,
    batch_size: int = 100,
    min_batch_size: int = 1,
) -> list[dict]:
    """Backward-compatible Pons wrapper around generic tx identity fetch."""

    return _fetch_transaction_identity_rows(
        rpc,
        transaction_hashes,
        batch_size=batch_size,
        min_batch_size=min_batch_size,
    )


def attach_pons_transaction_identities(
    points: Iterable[dict],
    transaction_rows: Iterable[dict],
) -> list[dict]:
    """Backward-compatible Pons wrapper around generic tx enrichment."""

    return attach_transaction_identities(
        points,
        transaction_rows,
        label="Pons point",
    )
