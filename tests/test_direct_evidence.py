import pytest

from hlp.data.direct_evidence import (
    EVIDENCE_SAMPLE_RULE,
    build_direct_market_evidence_plan,
    filter_direct_market_events,
    filter_direct_market_registry,
    filter_direct_supply_deltas,
    summarize_direct_market_evidence_plan,
)


def cohort(token_byte, last_block):
    token = "0x" + f"{token_byte:02x}" * 20
    v3 = "0x" + f"{token_byte + 20:02x}" * 20
    v4 = "0x" + f"{token_byte + 40:02x}" * 32
    return {
        "token": token,
        "market_count": 2,
        "source_ids": ["direct_uniswap_v3", "direct_uniswap_v4"],
        "venues": ["uniswap_v3", "uniswap_v4"],
        "quote_tokens": ["0x" + "aa" * 20],
        "first_initialize_block": last_block - 10,
        "last_initialize_block": last_block,
        "markets": [
            {
                "source_id": "direct_uniswap_v3",
                "venue": "uniswap_v3",
                "market_kind": "v3_pool",
                "market_id": v3,
                "quote_token": "0x" + "aa" * 20,
                "quote_decimals": 18,
                "initialize_block": last_block - 10,
            },
            {
                "source_id": "direct_uniswap_v4",
                "venue": "uniswap_v4",
                "market_kind": "v4_pool_id",
                "market_id": v4,
                "quote_token": "0x" + "aa" * 20,
                "quote_decimals": 18,
                "initialize_block": last_block,
            },
        ],
        "canonical_market_selection_complete": False,
    }


def test_evidence_plan_spans_chronology_without_ranking_markets():
    rows = [cohort(i, i * 100) for i in range(1, 6)]
    plan = build_direct_market_evidence_plan(
        rows,
        sample_size=3,
        window_blocks=50,
        snapshot_head_block=520,
    )

    assert [row["token"] for row in plan] == [
        rows[0]["token"],
        rows[2]["token"],
        rows[4]["token"],
    ]
    assert [row["evidence_window_from_block"] for row in plan] == [
        100,
        300,
        500,
    ]
    assert [row["evidence_window_to_block"] for row in plan] == [
        149,
        349,
        520,
    ]
    assert all(
        row["evidence_sample_rule"] == EVIDENCE_SAMPLE_RULE
        for row in plan
    )
    assert all(row["selector_freeze_ready"] is False for row in plan)

    summary = summarize_direct_market_evidence_plan(plan)
    assert summary["tokens"] == 3
    assert summary["markets"] == 6
    assert summary["first_window_block"] == 100
    assert summary["last_window_block"] == 520
    assert summary["selector_freeze_ready"] is False


def test_market_event_filter_keeps_only_per_token_evidence_window():
    plan = build_direct_market_evidence_plan(
        [cohort(1, 100)],
        sample_size=1,
        window_blocks=20,
        snapshot_head_block=200,
    )
    pool = plan[0]["markets"][0]["market_id"]
    rows = [
        {
            "pool": pool,
            "block_number": 99,
            "transaction_index": 1,
            "log_index": 0,
        },
        {
            "pool": pool,
            "block_number": 100,
            "transaction_index": 1,
            "log_index": 0,
        },
        {
            "pool": pool,
            "block_number": 119,
            "transaction_index": 1,
            "log_index": 0,
        },
        {
            "pool": pool,
            "block_number": 120,
            "transaction_index": 1,
            "log_index": 0,
        },
    ]
    filtered = filter_direct_market_events(
        rows,
        plan,
        market_field="pool",
    )
    assert [row["block_number"] for row in filtered] == [100, 119]


def test_supply_filter_preserves_deltas_from_first_seed_to_evidence_end():
    plan = build_direct_market_evidence_plan(
        [cohort(1, 100)],
        sample_size=1,
        window_blocks=20,
        snapshot_head_block=200,
    )
    token = plan[0]["token"]
    rows = [
        {
            "token": token,
            "block_number": 89,
            "transaction_index": 1,
            "log_index": 0,
        },
        {
            "token": token,
            "block_number": 90,
            "transaction_index": 1,
            "log_index": 0,
        },
        {
            "token": token,
            "block_number": 110,
            "transaction_index": 1,
            "log_index": 0,
        },
        {
            "token": token,
            "block_number": 120,
            "transaction_index": 1,
            "log_index": 0,
        },
    ]
    filtered = filter_direct_supply_deltas(rows, plan)
    assert [row["block_number"] for row in filtered] == [90, 110]


def test_registry_filter_retains_exact_planned_market_identity():
    plan = build_direct_market_evidence_plan(
        [cohort(1, 100)],
        sample_size=1,
        window_blocks=20,
        snapshot_head_block=200,
    )
    token = plan[0]["token"]
    v3_market = plan[0]["markets"][0]["market_id"]
    rows = [
        {
            "source_id": "direct_uniswap_v3",
            "token": token,
            "pool": v3_market,
            "initialize_block": 90,
        },
        {
            "source_id": "direct_uniswap_v3",
            "token": token,
            "pool": "0x" + "ff" * 20,
            "initialize_block": 95,
        },
    ]
    filtered = filter_direct_market_registry(rows, plan)
    assert len(filtered) == 1
    assert filtered[0]["pool"] == v3_market


def test_evidence_plan_rejects_declared_initialize_drift():
    row = cohort(1, 100)
    row["last_initialize_block"] = 99
    with pytest.raises(ValueError, match="last Initialize drift"):
        build_direct_market_evidence_plan(
            [row],
            sample_size=1,
            window_blocks=20,
            snapshot_head_block=200,
        )
