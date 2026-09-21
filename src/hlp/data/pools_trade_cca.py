"""pools.trade CCA price-path helpers.

CCA event decoding is already evidence-backed. Price orientation is kept
explicit until migration evidence freezes which Q96 direction represents
quote-per-token.
"""

from __future__ import annotations

from decimal import Decimal, getcontext
from typing import Iterable

from hlp.data.types import CcaPriceEvent


getcontext().prec = max(getcontext().prec, 80)
Q96 = Decimal(2) ** 96
CCA_ORIENTATIONS = frozenset({"quote_per_token", "token_per_quote"})


def cca_price_candidates(clearing_price_x96: int) -> dict[str, Decimal]:
    """Return quote-per-token under both possible Q96 interpretations."""
    raw = int(clearing_price_x96)
    if raw <= 0:
        raise ValueError("CCA clearing_price_x96 must be positive")
    value = Decimal(raw)
    return {
        "quote_per_token": value / Q96,
        "token_per_quote": Q96 / value,
    }


def cca_quote_per_token(
    clearing_price_x96: int,
    *,
    orientation: str,
) -> Decimal:
    """Return quote-per-token only for an explicitly frozen orientation."""
    orientation = str(orientation)
    if orientation not in CCA_ORIENTATIONS:
        raise ValueError(f"invalid CCA price orientation: {orientation!r}")
    candidates = cca_price_candidates(clearing_price_x96)
    return candidates[orientation]


def infer_cca_price_orientation(
    clearing_price_x96: int,
    *,
    migrated_quote_per_token: Decimal | str,
) -> dict:
    """Compare both CCA orientations with an observed migrated-market price."""
    migrated = Decimal(str(migrated_quote_per_token))
    if migrated <= 0:
        raise ValueError("migrated quote-per-token must be positive")

    candidates = cca_price_candidates(clearing_price_x96)
    direct_quote = candidates["quote_per_token"]
    inverse_quote = candidates["token_per_quote"]
    direct_error = abs(direct_quote / migrated - Decimal(1))
    inverse_error = abs(inverse_quote / migrated - Decimal(1))

    if direct_error == inverse_error:
        raise ValueError("CCA price orientation is ambiguous")
    orientation = (
        "quote_per_token"
        if direct_error < inverse_error
        else "token_per_quote"
    )
    return {
        "orientation": orientation,
        "direct_quote_per_token": direct_quote,
        "inverse_quote_per_token": inverse_quote,
        "direct_relative_error": direct_error,
        "inverse_relative_error": inverse_error,
        "best_relative_error": min(direct_error, inverse_error),
    }


def build_cca_quote_price_points(
    events: Iterable[CcaPriceEvent],
    *,
    orientation: str,
) -> list[dict]:
    """Build a deterministic CCA quote-price event tape."""
    if orientation not in CCA_ORIENTATIONS:
        raise ValueError(f"invalid CCA price orientation: {orientation!r}")

    ordered = sorted(
        list(events),
        key=lambda row: (
            int(row.block_number),
            -1 if row.transaction_index is None else int(row.transaction_index),
            int(row.log_index),
        ),
    )
    output: list[dict] = []
    previous_order: tuple[int, int, int] | None = None
    for row in ordered:
        order = (
            int(row.block_number),
            -1 if row.transaction_index is None else int(row.transaction_index),
            int(row.log_index),
        )
        if previous_order == order:
            raise ValueError(f"duplicate CCA price event order: {order}")
        previous_order = order
        price = cca_quote_per_token(
            row.clearing_price_x96,
            orientation=orientation,
        )
        if price <= 0:
            raise ValueError("CCA quote-per-token must be positive")
        output.append(
            {
                "auction": row.auction.lower(),
                "event_type": row.event_type,
                "checkpoint_block": int(row.checkpoint_block),
                "clearing_price_x96": int(row.clearing_price_x96),
                "cumulative_mps": row.cumulative_mps,
                "quote_per_token": str(price),
                "orientation": orientation,
                "block_number": int(row.block_number),
                "transaction_hash": row.transaction_hash.lower(),
                "transaction_index": row.transaction_index,
                "log_index": int(row.log_index),
            }
        )
    return output
