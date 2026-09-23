import pytest

from hlp.data.direct_source_coverage import (
    DIRECT_SOURCE_COVERAGE_VERSION,
    audit_direct_source_market_points,
    build_direct_source_coverage_report,
)


TOKEN = "0x" + "11" * 20
POOL_A = "0x" + "22" * 20
POOL_B = "0x" + "33" * 20
SHA = "ab" * 32


def registry(pool, block, log):
    return {
        "source_id": "direct_uniswap_v3",
        "venue": "uniswap_v3",
        "token": TOKEN,
        "pool": pool,
        "initialize_block": block,
        "initialize_transaction_index": 1,
        "initialize_log_index": log,
        "direct_launch_classification": "conclusive_direct_launch",
        "direct_launch_attribution_complete": True,
        "canonical_selector_frozen": True,
        "canonical_market_selected": False,
        "source_coverage_complete": False,
    }


def point(pool, block, log, event_type):
    return {
        "source_id": "direct_uniswap_v3",
        "venue": "uniswap_v3",
        "token": TOKEN,
        "pool": pool,
        "market_id": pool,
        "block_number": block,
        "transaction_hash": "0x" + f"{block:064x}",
        "transaction_index": 1,
        "log_index": log,
        "event_type": event_type,
        "market_cap_proxy_usd": "100000",
        "active_quote_liquidity_usd": (
            "5000" if event_type == "v3_swap" else None
        ),
    }


def test_direct_source_coverage_keeps_multiple_markets_per_token():
    audit = audit_direct_source_market_points(
        [
            registry(POOL_A, 10, 1),
            registry(POOL_B, 20, 2),
        ],
        [
            point(POOL_A, 10, 1, "v3_initialize"),
            point(POOL_A, 11, 2, "v3_swap"),
            point(POOL_B, 20, 2, "v3_initialize"),
            point(POOL_B, 21, 3, "v3_swap"),
        ],
        source_id="direct_uniswap_v3",
        snapshot_head_block=100,
    )

    assert audit["version"] == DIRECT_SOURCE_COVERAGE_VERSION
    assert audit["registry_markets"] == 2
    assert audit["registry_tokens"] == 1
    assert audit["initialize_points"] == 2
    assert audit["price_points"] == audit["priced_points"] == 4
    assert audit["selector_rule_applied_to_coverage_points"] is False


def test_direct_source_coverage_requires_each_market_initialize():
    with pytest.raises(ValueError, match="exactly one Initialize"):
        audit_direct_source_market_points(
            [registry(POOL_A, 10, 1)],
            [point(POOL_A, 11, 2, "v3_swap")],
            source_id="direct_uniswap_v3",
            snapshot_head_block=100,
        )


def test_direct_source_coverage_rejects_unpriced_point():
    row = point(POOL_A, 10, 1, "v3_initialize")
    row["market_cap_proxy_usd"] = None

    with pytest.raises(ValueError, match="unpriced"):
        audit_direct_source_market_points(
            [registry(POOL_A, 10, 1)],
            [row],
            source_id="direct_uniswap_v3",
            snapshot_head_block=100,
        )


def test_direct_source_coverage_report_is_canonical_and_complete():
    audit = audit_direct_source_market_points(
        [registry(POOL_A, 10, 1)],
        [point(POOL_A, 10, 1, "v3_initialize")],
        source_id="direct_uniswap_v3",
        snapshot_head_block=100,
    )
    report = build_direct_source_coverage_report(
        audit,
        provenance_sha256=SHA,
    )

    assert report["coverage_status"] == "complete"
    assert report["required_start_block"] == 8_930
    assert report["last_block"] == 100
    assert report["tokens_discovered"] == 1
    assert report["markets_discovered"] == 1
    assert report["price_points"] == report["priced_points"] == 1


def test_direct_source_coverage_rejects_preselected_registry():
    row = registry(POOL_A, 10, 1)
    row["canonical_market_selected"] = True

    with pytest.raises(ValueError, match="preselects"):
        audit_direct_source_market_points(
            [row],
            [],
            source_id="direct_uniswap_v3",
            snapshot_head_block=100,
        )
