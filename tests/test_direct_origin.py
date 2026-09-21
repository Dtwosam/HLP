import pytest

from hlp.data.direct_origin import build_direct_origin_attribution


TOKEN = "0x" + "11" * 20
OTHER = "0x" + "22" * 20


def inventory():
    return [
        {
            "source_id": "pons_v1",
            "source_kind": "launchpad",
            "readiness": "phase1_proven",
        },
        {
            "source_id": "noxa",
            "source_kind": "launchpad",
            "readiness": "adapter_ready",
        },
        {
            "source_id": "direct_uniswap_v3",
            "source_kind": "direct_dex",
            "readiness": "adapter_ready",
        },
    ]


def coverage():
    return {
        "version": "phase2-source-coverage-v1",
        "snapshot_head_block": 100,
        "sources": [
            {
                "source_id": "pons_v1",
                "source_readiness": "phase1_proven",
                "coverage_status": "complete",
                "required_start_block": 1,
                "first_block": 1,
                "last_block": 100,
                "continuous": True,
                "missing_ranges": [],
                "tokens_discovered": 1,
                "price_points": 1,
                "priced_points": 1,
                "observed_volume_usd": None,
                "provenance_sha256": "ab" * 32,
                "blocking_reason": None,
            },
            {
                "source_id": "noxa",
                "source_readiness": "adapter_ready",
                "coverage_status": "not_started",
                "required_start_block": 2,
                "first_block": None,
                "last_block": None,
                "continuous": None,
                "missing_ranges": [],
                "tokens_discovered": 0,
                "price_points": 0,
                "priced_points": 0,
                "observed_volume_usd": None,
                "provenance_sha256": None,
                "blocking_reason": None,
            },
            {
                "source_id": "direct_uniswap_v3",
                "source_readiness": "adapter_ready",
                "coverage_status": "not_started",
                "required_start_block": 1,
                "first_block": None,
                "last_block": None,
                "continuous": None,
                "missing_ranges": [],
                "tokens_discovered": 0,
                "price_points": 0,
                "priced_points": 0,
                "observed_volume_usd": None,
                "provenance_sha256": None,
                "blocking_reason": None,
            },
        ],
    }


def market(token=TOKEN):
    return {
        "source_id": "direct_uniswap_v3",
        "venue": "uniswap_v3",
        "token": token,
        "pool": "0x" + "33" * 20,
    }


def test_known_launch_match_is_exact_even_when_global_coverage_is_open():
    rows, report = build_direct_origin_attribution(
        [market()],
        {"pons_v1": [{"token": TOKEN}]},
        source_inventory=inventory(),
        coverage_ledger=coverage(),
    )

    assert rows[0]["origin_classification"] == "known_launch_source"
    assert rows[0]["origin_attribution_complete"] is True
    assert rows[0]["launch_source_ids"] == ["pons_v1"]
    assert report["known_launch_source_markets"] == 1
    assert report["launch_source_coverage_complete"] is False
    assert report["absence_from_launch_registries_is_conclusive"] is False
    assert report["missing_launch_registry_source_ids"] == ["noxa"]
    assert report["incomplete_launch_coverage_source_ids"] == ["noxa"]


def test_unmatched_market_stays_inconclusive_until_all_launchpads_complete():
    rows, report = build_direct_origin_attribution(
        [market()],
        {"pons_v1": [{"token": OTHER}]},
        source_inventory=inventory(),
        coverage_ledger=coverage(),
    )

    assert rows[0]["origin_classification"] == "unattributed"
    assert rows[0]["origin_attribution_complete"] is False
    assert report["unattributed_markets"] == 1
    assert report["unattributed_markets_remain_direct_launch_unknown"] is True


def test_absence_becomes_conclusive_only_with_complete_supplied_launchpads():
    ledger = coverage()
    noxa = next(
        row for row in ledger["sources"]
        if row["source_id"] == "noxa"
    )
    noxa.update({
        "coverage_status": "complete",
        "first_block": 2,
        "last_block": 100,
        "continuous": True,
        "tokens_discovered": 1,
        "price_points": 1,
        "priced_points": 1,
        "provenance_sha256": "cd" * 32,
    })

    rows, report = build_direct_origin_attribution(
        [market()],
        {
            "pons_v1": [{"token": OTHER}],
            "noxa": [{"token": "0x" + "44" * 20}],
        },
        source_inventory=inventory(),
        coverage_ledger=ledger,
    )

    assert rows[0]["origin_classification"] == "unattributed"
    assert report["launch_source_coverage_complete"] is True
    assert report["absence_from_launch_registries_is_conclusive"] is True
    assert report["unattributed_markets_remain_direct_launch_unknown"] is False


def test_direct_source_cannot_be_supplied_as_launch_registry():
    with pytest.raises(ValueError, match="not a launchpad"):
        build_direct_origin_attribution(
            [market()],
            {"direct_uniswap_v3": [{"token": TOKEN}]},
            source_inventory=inventory(),
            coverage_ledger=coverage(),
        )
