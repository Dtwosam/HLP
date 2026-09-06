from decimal import Decimal

import pytest

from hlp.data.pons_crosscheck import (
    build_canonical_dex_price_checkpoint,
    build_representative_pool_targets,
    reconcile_external_pool,
    reconcile_price_against_ohlcv,
)


def _registry():
    return [
        {
            "version": "v1",
            "token": "0x" + "11" * 20,
            "pair_token": "0x" + "aa" * 20,
            "pool": "0x" + "33" * 20,
            "supply_raw": 1_000_000 * 10**18,
            "token_decimals": 18,
        },
        {
            "version": "v2",
            "token": "0x" + "22" * 20,
            "pair_token": "0x" + "bb" * 20,
            "pool": None,
            "supply_raw": 1_000_000 * 10**18,
            "token_decimals": 18,
        },
        {
            "version": "v2",
            "token": "0x" + "44" * 20,
            "pair_token": "0x" + "cc" * 20,
            "pool": None,
            "supply_raw": 1_000_000 * 10**18,
            "token_decimals": 18,
        },
    ]


def test_build_representative_pool_targets_handles_v1_and_v2():
    sample = [
        {"token": "0x" + "11" * 20, "pons_version": "v1"},
        {"token": "0x" + "22" * 20, "pons_version": "v2"},
        {"token": "0x" + "44" * 20, "pons_version": "v2"},
    ]
    registrations = [
        {
            "token": "0x" + "22" * 20,
            "quote_token": "0x" + "bb" * 20,
            "pool_id": "0x" + "55" * 32,
        }
    ]
    rows = build_representative_pool_targets(
        sample,
        _registry(),
        registrations,
    )
    assert rows[0]["pool_kind"] == "uniswap_v3"
    assert rows[0]["pool_identifier"] == "0x" + "33" * 20
    assert rows[1]["pool_kind"] == "uniswap_v4"
    assert rows[1]["pool_identifier"] == "0x" + "55" * 32
    assert rows[2]["crosscheck_scope"] == "no_registered_v4_pool"
    assert rows[2]["pool_identifier"] is None


def test_reconcile_external_pool_accepts_reversed_pair_order():
    target = {
        "token": "0x" + "11" * 20,
        "quote_token": "0x" + "aa" * 20,
        "pool_identifier": "0x" + "33" * 20,
    }
    external = {
        "pool_address": "0x" + "33" * 20,
        "base_token": "0x" + "aa" * 20,
        "quote_token": "0x" + "11" * 20,
        "reserve_in_usd": "123.45",
        "pool_created_at": "2026-08-01T00:00:00Z",
    }
    result = reconcile_external_pool(target, external)
    assert result["external_match"] is True
    assert result["mismatches"] == []


def test_reconcile_external_pool_reports_identity_mismatch():
    target = {
        "token": "0x" + "11" * 20,
        "quote_token": "0x" + "aa" * 20,
        "pool_identifier": "0x" + "33" * 20,
    }
    external = {
        "pool_address": "0x" + "99" * 20,
        "base_token": "0x" + "11" * 20,
        "quote_token": "0x" + "bb" * 20,
        "reserve_in_usd": "1",
    }
    result = reconcile_external_pool(target, external)
    assert result["external_match"] is False
    assert result["mismatches"] == ["pool_identifier", "token_pair"]


def test_reconcile_price_passes_inside_independent_candle():
    result = reconcile_price_against_ohlcv(
        canonical_price_usd="1.25",
        canonical_timestamp=112,
        candles=[
            {
                "timestamp": 100,
                "low": "1.0",
                "high": "1.5",
            }
        ],
        candle_seconds=60,
    )
    assert result["price_match"] is True
    assert result["outside_candle_bps"] == "0"


def test_reconcile_price_allows_explicit_bps_tolerance():
    result = reconcile_price_against_ohlcv(
        canonical_price_usd=Decimal("0.99"),
        canonical_timestamp=112,
        candles=[
            {
                "timestamp": 100,
                "low": "1.0",
                "high": "1.5",
            }
        ],
        candle_seconds=60,
        tolerance_bps=101,
    )
    assert result["price_match"] is True
    assert Decimal(result["outside_candle_bps"]) > 0


def test_reconcile_price_missing_candle_is_explicit():
    result = reconcile_price_against_ohlcv(
        canonical_price_usd="1",
        canonical_timestamp=1000,
        candles=[{"timestamp": 100, "low": "1", "high": "2"}],
        candle_seconds=60,
    )
    assert result["price_match"] is None
    assert result["status"] == "missing_candle"


def test_representative_target_rejects_registration_quote_mismatch():
    with pytest.raises(ValueError, match="registration quote mismatch"):
        build_representative_pool_targets(
            [{"token": "0x" + "22" * 20, "pons_version": "v2"}],
            _registry(),
            [
                {
                    "token": "0x" + "22" * 20,
                    "quote_token": "0x" + "ff" * 20,
                    "pool_id": "0x" + "55" * 32,
                }
            ],
        )

def test_canonical_v1_dex_price_checkpoint_uses_swap_maximum():
    target = build_representative_pool_targets(
        [{"token": "0x" + "11" * 20, "pons_version": "v1"}],
        _registry(),
        [],
    )[0]
    checkpoint = build_canonical_dex_price_checkpoint(
        target,
        {
            "token": target["token"],
            "v3_swap_max_market_cap_proxy_usd": "2500000",
            "v3_swap_max_market_cap_block": 12345,
        },
    )
    assert checkpoint["price_crosscheck_scope"] == "canonical_dex_swap"
    assert checkpoint["canonical_price_phase"] == "v3_swap"
    assert checkpoint["canonical_block_number"] == 12345
    assert Decimal(checkpoint["canonical_price_usd"]) == Decimal("2.5")


def test_canonical_v2_dex_price_checkpoint_marks_missing_swap_explicitly():
    target = build_representative_pool_targets(
        [{"token": "0x" + "22" * 20, "pons_version": "v2"}],
        _registry(),
        [{
            "token": "0x" + "22" * 20,
            "quote_token": "0x" + "bb" * 20,
            "pool_id": "0x" + "55" * 32,
        }],
    )[0]
    checkpoint = build_canonical_dex_price_checkpoint(
        target,
        {"token": target["token"]},
    )
    assert checkpoint["price_crosscheck_scope"] == "no_swap_checkpoint"
    assert checkpoint["canonical_price_usd"] is None

