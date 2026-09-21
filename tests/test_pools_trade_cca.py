from decimal import Decimal

import pytest

from hlp.data.pools_trade_cca import (
    Q96,
    build_cca_quote_price_points,
    cca_quote_per_token,
    infer_cca_price_orientation,
)
from hlp.data.types import CcaPriceEvent


AUCTION = "0x" + "11" * 20


def event(price, *, block=100, log_index=1):
    return CcaPriceEvent(
        auction=AUCTION,
        event_type="checkpoint",
        checkpoint_block=block,
        clearing_price_x96=price,
        cumulative_mps=123,
        block_number=block,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=2,
        log_index=log_index,
    )


def test_explicit_cca_orientation_is_required():
    raw = int(Q96 / Decimal(2))
    assert cca_quote_per_token(
        raw,
        orientation="quote_per_token",
    ) == Decimal(raw) / Q96
    assert cca_quote_per_token(
        raw,
        orientation="token_per_quote",
    ) == Q96 / Decimal(raw)

    with pytest.raises(ValueError, match="invalid CCA price orientation"):
        cca_quote_per_token(raw, orientation="unknown")


def test_infer_direct_cca_orientation_from_migrated_price():
    raw = int(Q96 / Decimal(2))
    report = infer_cca_price_orientation(
        raw,
        migrated_quote_per_token=Decimal("0.5"),
    )
    assert report["orientation"] == "quote_per_token"
    assert report["direct_relative_error"] < Decimal("1e-20")


def test_infer_inverse_cca_orientation_from_migrated_price():
    raw = int(Q96 * Decimal(2))
    report = infer_cca_price_orientation(
        raw,
        migrated_quote_per_token=Decimal("0.5"),
    )
    assert report["orientation"] == "token_per_quote"
    assert report["inverse_relative_error"] < Decimal("1e-20")


def test_build_cca_price_points_sorts_and_preserves_provenance():
    raw = int(Q96 / Decimal(4))
    rows = build_cca_quote_price_points(
        [
            event(raw, block=101, log_index=2),
            event(raw, block=100, log_index=1),
        ],
        orientation="quote_per_token",
    )
    assert [row["block_number"] for row in rows] == [100, 101]
    assert rows[0]["orientation"] == "quote_per_token"
    assert Decimal(rows[0]["quote_per_token"]) == Decimal(raw) / Q96


def test_build_cca_price_points_rejects_duplicate_event_order():
    raw = int(Q96)
    with pytest.raises(ValueError, match="duplicate CCA price event order"):
        build_cca_quote_price_points(
            [event(raw), event(raw)],
            orientation="quote_per_token",
        )
