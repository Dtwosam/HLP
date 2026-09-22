import pytest

from hlp.data.direct_canonical import DIRECT_CANONICAL_SERIES_VERSION
from hlp.data.direct_eligibility import (
    DIRECT_ELIGIBILITY_HANDOFF_VERSION,
    build_direct_eligibility_handoff,
)
from hlp.data.direct_selector import (
    DIRECT_SELECTOR_FREEZE_VERSION,
    DIRECT_SELECTOR_VERSION,
)


A = "0x" + "11" * 20
B = "0x" + "22" * 20
SHA = "ab" * 32
SOURCES = (
    "direct_uniswap_v3",
    "direct_sushiswap_v3",
    "direct_uniswap_v4",
)


def inventory():
    return [
        {
            "source_id": source,
            "source_kind": "direct_dex",
            "readiness": "adapter_ready",
        }
        for source in SOURCES
    ]


def selector():
    return {
        "version": DIRECT_SELECTOR_FREEZE_VERSION,
        "selector_version": DIRECT_SELECTOR_VERSION,
        "selection_rule_frozen": True,
        "source_coverage_complete": False,
        "snapshot_head_block": 100,
    }


def coverage(source, tokens):
    return {
        "source_id": source,
        "source_readiness": "adapter_ready",
        "coverage_status": "complete",
        "required_start_block": 1,
        "first_block": 1,
        "last_block": 100,
        "snapshot_head_block": 100,
        "continuous": True,
        "missing_ranges": [],
        "tokens_discovered": tokens,
        "price_points": 10,
        "priced_points": 10,
        "selector_version": DIRECT_SELECTOR_VERSION,
        "selector_descriptor_sha256": SHA,
        "selector_rule_applied_to_coverage_points": False,
    }


def canonical(token, maximum, points=2):
    return {
        "token": token,
        "price_points": points,
        "priced_points": points,
        "unpriced_points": 0,
        "pricing_complete": True,
        "max_market_cap_proxy_usd": str(maximum),
        "max_market_cap_block": 50,
        "crossed_100k": maximum >= 100000,
        "canonical_price_series": True,
    }


def canonical_report(points=4, tokens=2):
    return {
        "version": DIRECT_CANONICAL_SERIES_VERSION,
        "points": points,
        "tokens": tokens,
        "selected_markets": 3,
        "leadership_switches": 1,
        "synthetic_selector_switches": 1,
        "canonical_selector_version": DIRECT_SELECTOR_VERSION,
        "selection_rule_frozen": True,
        "canonical_price_series": True,
        "cross_pool_volume_double_counting_allowed": False,
    }


def test_direct_eligibility_splits_one_canonical_series_by_population():
    memberships = {
        "direct_uniswap_v3": [A],
        "direct_sushiswap_v3": [A, B],
        "direct_uniswap_v4": [],
    }
    reports = {
        source: coverage(source, len(memberships[source]))
        for source in SOURCES
    }

    groups, summary = build_direct_eligibility_handoff(
        [canonical(A, 150000), canonical(B, 90000)],
        canonical_report(),
        memberships,
        reports,
        selector(),
        source_inventory=inventory(),
        provenance_sha256=SHA,
        selector_descriptor_sha256=SHA,
    )

    assert [row["token"] for row in groups["direct_uniswap_v3"]] == [A]
    assert [row["token"] for row in groups["direct_sushiswap_v3"]] == [A, B]
    assert groups["direct_uniswap_v4"] == []
    assert groups["direct_uniswap_v3"][0]["crossed_100k"] is True
    assert summary["version"] == DIRECT_ELIGIBILITY_HANDOFF_VERSION
    assert summary["canonical_tokens"] == 2
    assert summary["direct_population_overlap_tokens"] == 1
    assert summary["phase2_universe_source_ready"] is True


def test_direct_eligibility_requires_complete_source_coverage():
    memberships = {source: [] for source in SOURCES}
    reports = {source: coverage(source, 0) for source in SOURCES}
    reports["direct_uniswap_v3"]["coverage_status"] = "partial"

    with pytest.raises(ValueError, match="requires complete coverage"):
        build_direct_eligibility_handoff(
            [],
            canonical_report(points=0, tokens=0),
            memberships,
            reports,
            selector(),
            source_inventory=inventory(),
            provenance_sha256=SHA,
            selector_descriptor_sha256=SHA,
        )


def test_direct_eligibility_rejects_selector_descriptor_drift():
    memberships = {source: [] for source in SOURCES}
    reports = {source: coverage(source, 0) for source in SOURCES}
    reports["direct_uniswap_v4"]["selector_descriptor_sha256"] = "cd" * 32

    with pytest.raises(ValueError, match="selector descriptor drift"):
        build_direct_eligibility_handoff(
            [],
            canonical_report(points=0, tokens=0),
            memberships,
            reports,
            selector(),
            source_inventory=inventory(),
            provenance_sha256=SHA,
            selector_descriptor_sha256=SHA,
        )


def test_direct_eligibility_requires_every_population_token_in_canonical_series():
    memberships = {
        "direct_uniswap_v3": [A],
        "direct_sushiswap_v3": [],
        "direct_uniswap_v4": [],
    }
    reports = {
        source: coverage(source, len(memberships[source]))
        for source in SOURCES
    }

    with pytest.raises(ValueError, match="canonical token population mismatch"):
        build_direct_eligibility_handoff(
            [],
            canonical_report(points=0, tokens=0),
            memberships,
            reports,
            selector(),
            source_inventory=inventory(),
            provenance_sha256=SHA,
            selector_descriptor_sha256=SHA,
        )
