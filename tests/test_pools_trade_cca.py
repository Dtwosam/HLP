from decimal import Decimal, getcontext

import pytest

from hlp.data.pools_trade_cca import (
    Q96,
    build_cca_market_cap_points,
    build_cca_quote_price_points,
    cca_quote_per_token,
    infer_cca_price_orientation,
    summarize_cca_market_caps,
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



TOKEN = "0x" + "22" * 20
QUOTE = "0x" + "00" * 20


def registry():
    return [{
        "venue": "pools.trade",
        "launch_kind": "crowd_lbp",
        "token": TOKEN,
        "quote_token": QUOTE,
        "supply_raw": 1_000_000_000 * 10**18,
        "initializer": AUCTION,
    }]


def test_build_cca_market_caps_uses_raw_unit_supply_formula():
    raw = int(Q96 / Decimal(2))
    rows = build_cca_market_cap_points(
        registry(),
        [event(raw)],
        [],
        orientation="quote_per_token",
        initial_weth_usd=Decimal("2000"),
        quote_decimals={QUOTE: 18},
    )

    assert len(rows) == 1
    assert rows[0]["token"] == TOKEN
    assert rows[0]["quote_token"] == QUOTE
    assert Decimal(rows[0]["raw_quote_per_raw_token"]) == (
        Decimal(raw) / Q96
    )
    assert Decimal(rows[0]["market_cap_quote"]) == (
        Decimal(raw) / Q96 * Decimal("1000000000")
    )
    assert rows[0]["pricing_status"] == "priced_weth_usdg"
    assert Decimal(rows[0]["market_cap_proxy_usd"]) == (
        Decimal(rows[0]["market_cap_quote"]) * Decimal("2000")
    )


def test_build_cca_market_caps_fails_closed_without_registry():
    raw = int(Q96)
    with pytest.raises(ValueError, match="missing launch registry"):
        build_cca_market_cap_points(
            [],
            [event(raw)],
            [],
            orientation="quote_per_token",
            initial_weth_usd=Decimal("2000"),
            quote_decimals={QUOTE: 18},
        )


def test_cca_summary_preserves_unpriced_points_and_threshold():
    rows = [
        {
            "token": TOKEN,
            "initializer": AUCTION,
            "quote_token": QUOTE,
            "orientation": "quote_per_token",
            "block_number": 100,
            "pricing_status": "unsupported_quote",
            "market_cap_proxy_usd": None,
        },
        {
            "token": TOKEN,
            "initializer": AUCTION,
            "quote_token": QUOTE,
            "orientation": "quote_per_token",
            "block_number": 101,
            "pricing_status": "priced_weth_usdg",
            "market_cap_proxy_usd": "150000",
        },
    ]
    summary = summarize_cca_market_caps(rows)
    assert summary[0]["price_points"] == 2
    assert summary[0]["priced_points"] == 1
    assert summary[0]["crossed_100k"] is True
    assert summary[0]["max_market_cap_block"] == 101



def test_cca_orientation_math_ignores_global_decimal_precision():
    raw = 7_962_430_332_683_565_928_151_168
    migrated = Decimal(
        "0.00010050000000000000000000001251111621485482844073392923021628218528362978949759907"
    )
    prior = getcontext().prec
    try:
        getcontext().prec = 140
        high = infer_cca_price_orientation(
            raw,
            migrated_quote_per_token=migrated,
        )
        getcontext().prec = 28
        low = infer_cca_price_orientation(
            raw,
            migrated_quote_per_token=migrated,
        )
    finally:
        getcontext().prec = prior

    assert high == low
    assert high["orientation"] == "quote_per_token"
    assert str(high["direct_quote_per_token"]) == (
        "0.00010050000000000000000000001251110676486454358243005646755818816018290817737579346"
    )


def test_cca_market_caps_replay_initializer_seed_supply_deltas():
    raw = int(Q96)
    registry_rows = [{
        **registry()[0],
        "initializer_block": 90,
        "initializer_transaction_index": 1,
        "initializer_log_index": 0,
    }]
    deltas = [{
        "token": TOKEN,
        "from_address": TOKEN,
        "to_address": "0x" + "00" * 20,
        "value_raw": 100_000_000 * 10**18,
        "supply_delta_raw": -100_000_000 * 10**18,
        "is_mint": False,
        "is_burn": True,
        "block_number": 95,
        "transaction_hash": "0x" + "cc" * 32,
        "transaction_index": 1,
        "log_index": 0,
    }]
    rows = build_cca_market_cap_points(
        registry_rows,
        [event(raw, block=100)],
        [],
        orientation="quote_per_token",
        initial_weth_usd=Decimal("2000"),
        quote_decimals={QUOTE: 18},
        supply_delta_rows=deltas,
    )

    assert rows[0]["supply_raw"] == 900_000_000 * 10**18
    assert Decimal(rows[0]["market_cap_quote"]) == Decimal("900000000")

