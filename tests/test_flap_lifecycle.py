import pytest

from decimal import Decimal

from hlp.data.flap_lifecycle import (
    build_flap_graduation_market_handoffs,
    build_flap_graduation_snapshot_points,
    build_flap_v3_graduation_registry,
    merge_flap_lifecycle_market_cap_summaries,
    summarize_flap_graduation_market_handoffs,
)


TOKEN = "0x" + "11" * 20
QUOTE = "0x" + "22" * 20
POOL = "0x" + "33" * 20


def flap_row(pool=POOL, quote=QUOTE):
    return {
        "token": TOKEN,
        "graduation_block": 20,
        "graduation_transaction_hash": "0x" + "aa" * 32,
        "graduation_transaction_index": 2,
        "graduation_log_index": 5,
        "graduation_pool": pool,
        "graduation_quote_token": quote,
        "graduation_dex_id": 2,
        "graduation_lp_fee_profile": 1,
    }


def market_row(pool=POOL, token=TOKEN, quote=QUOTE):
    return {
        "source_id": "direct_uniswap_v3",
        "venue": "uniswap_v3",
        "source_kind": "direct_dex",
        "token": token,
        "quote_token": quote,
        "quote_decimals": 18,
        "pool": pool,
        "initialize_block": 20,
        "initialize_transaction_index": 2,
        "initialize_log_index": 3,
        "initial_sqrt_price_x96": 2**96,
        "initial_tick": 0,
    }


def test_flap_graduation_handoff_matches_exact_address_market():
    rows = build_flap_graduation_market_handoffs(
        [flap_row()],
        [market_row()],
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["market_handoff_complete"] is True
    assert row["market_source_id"] == "direct_uniswap_v3"
    assert row["market_available_at_graduation"] is True
    assert row["market_initialize_order_relation"] == "before_graduation"

    summary = summarize_flap_graduation_market_handoffs(rows)
    assert summary["graduated_tokens"] == 1
    assert summary["matched_address_markets"] == 1
    assert summary["all_graduations_resolved"] is True
    assert summary["v4_pool_id_inference_used"] is False


def test_flap_graduation_handoff_keeps_unmatched_pool_unresolved():
    rows = build_flap_graduation_market_handoffs(
        [flap_row()],
        [],
    )

    assert rows[0]["market_match_status"] == "unmatched_address_market"
    assert rows[0]["market_handoff_complete"] is False
    assert summarize_flap_graduation_market_handoffs(rows)[
        "all_graduations_resolved"
    ] is False


def test_flap_graduation_handoff_ignores_pool_id_only_market():
    v4 = {
        **market_row(),
        "source_id": "direct_uniswap_v4",
        "venue": "uniswap_v4",
        "pool_id": "0x" + "44" * 32,
    }
    del v4["pool"]
    rows = build_flap_graduation_market_handoffs(
        [flap_row()],
        [v4],
    )
    assert rows[0]["market_handoff_complete"] is False


def test_flap_graduation_handoff_rejects_token_or_quote_mismatch():
    with pytest.raises(ValueError, match="token mismatch"):
        build_flap_graduation_market_handoffs(
            [flap_row()],
            [market_row(token="0x" + "55" * 20)],
        )
    with pytest.raises(ValueError, match="quote mismatch"):
        build_flap_graduation_market_handoffs(
            [flap_row()],
            [market_row(quote="0x" + "66" * 20)],
        )


def test_flap_graduation_handoff_rejects_duplicate_market_pool():
    with pytest.raises(ValueError, match="duplicate address-based"):
        build_flap_graduation_market_handoffs(
            [flap_row()],
            [market_row(), market_row()],
        )


def full_flap_row():
    return {
        **flap_row(),
        "launch_block": 10,
        "launch_transaction_hash": "0x" + "bb" * 32,
        "launch_transaction_index": 1,
        "launch_log_index": 1,
        "supply_raw": 1_000_000_000 * 10**18,
        "token_decimals": 18,
    }


def test_build_flap_v3_graduation_registry_freezes_exact_handoff():
    handoffs = build_flap_graduation_market_handoffs(
        [full_flap_row()],
        [market_row()],
    )
    rows = build_flap_v3_graduation_registry(
        [full_flap_row()],
        handoffs,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["source_id"] == "flap"
    assert row["market_source_id"] == "direct_uniswap_v3"
    assert row["pool"] == POOL
    assert row["lifecycle_block"] == 20
    assert row["lifecycle_transaction_index"] == 2
    assert row["lifecycle_log_index"] == 5
    assert row["initialize_log_index"] == 3


def test_flap_v3_graduation_registry_rejects_unresolved_market():
    handoffs = build_flap_graduation_market_handoffs(
        [full_flap_row()],
        [],
    )
    with pytest.raises(ValueError, match="no exact address market"):
        build_flap_v3_graduation_registry(
            [full_flap_row()],
            handoffs,
        )


def test_flap_graduation_snapshot_prices_exact_handoff():
    handoffs = build_flap_graduation_market_handoffs(
        [full_flap_row()],
        [market_row()],
    )
    registry = build_flap_v3_graduation_registry(
        [full_flap_row()],
        handoffs,
    )
    quote_points = [{
        "pool": POOL,
        "token": TOKEN,
        "quote_token": QUOTE,
        "block_number": 20,
        "transaction_index": 2,
        "log_index": 5,
        "quote_per_token": "0.001",
        "pricing_source": "sparse_v3_state_and_swaps",
    }]
    rows = build_flap_graduation_snapshot_points(
        registry,
        quote_points,
        [],
        initial_weth_usd=Decimal("2000"),
        initial_quote_usd={QUOTE: Decimal("2")},
    )

    assert len(rows) == 1
    assert rows[0]["event_type"] == "v3_graduation_snapshot"
    assert rows[0]["market_cap_quote"] == "1000000.000"
    assert rows[0]["market_cap_proxy_usd"] == "2000000.000"


def test_merge_flap_lifecycle_summaries_preserves_full_population():
    registry = [
        full_flap_row(),
        {
            **full_flap_row(),
            "token": "0x" + "55" * 20,
            "graduation_block": None,
        },
    ]
    curve = [{
        "token": TOKEN,
        "price_points": 2,
        "priced_points": 2,
        "max_market_cap_proxy_usd": "90000",
        "max_market_cap_block": 15,
        "crossed_100k": False,
    }]
    v3 = [{
        "token": TOKEN,
        "price_points": 3,
        "priced_points": 3,
        "max_market_cap_proxy_usd": "150000",
        "max_market_cap_block": 25,
        "crossed_100k": True,
    }]
    rows = merge_flap_lifecycle_market_cap_summaries(
        registry,
        curve,
        v3,
    )
    by_token = {row["token"]: row for row in rows}
    assert len(rows) == 2
    assert by_token[TOKEN]["price_points"] == 5
    assert by_token[TOKEN]["crossed_100k"] is True
    assert by_token[TOKEN]["max_market_cap_proxy_usd"] == "150000"
    assert by_token["0x" + "55" * 20]["price_points"] == 0

