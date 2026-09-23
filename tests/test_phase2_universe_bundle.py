import pytest

from hlp.data.phase2_coverage import PHASE2_COVERAGE_LEDGER_VERSION
from hlp.data.phase2_universe_bundle import (
    PHASE2_UNIVERSE_SOURCE_BUNDLE_VERSION,
    validate_phase2_universe_source_bundle,
)


SHA = "ab" * 32
INVENTORY = [
    {
        "source_id": "launch",
        "source_kind": "launchpad",
        "readiness": "adapter_ready",
    },
    {
        "source_id": "direct",
        "source_kind": "direct_dex",
        "readiness": "adapter_ready",
    },
]


def ledger(status="complete"):
    rows = []
    for source in ("launch", "direct"):
        row = {
            "source_id": source,
            "source_readiness": "adapter_ready",
            "coverage_status": "complete",
            "required_start_block": 1,
            "first_block": 1,
            "last_block": 100,
            "continuous": True,
            "missing_ranges": [],
            "tokens_discovered": 2,
            "price_points": 5,
            "priced_points": 5,
            "observed_volume_usd": None,
            "provenance_sha256": SHA,
            "blocking_reason": None,
        }
        rows.append(row)
    if status != "complete":
        rows[1].update({
            "coverage_status": "not_started",
            "first_block": None,
            "last_block": None,
            "continuous": None,
            "tokens_discovered": 0,
            "price_points": 0,
            "priced_points": 0,
            "provenance_sha256": None,
        })
    return {
        "version": PHASE2_COVERAGE_LEDGER_VERSION,
        "snapshot_head_block": 100,
        "sources": rows,
    }


def summaries():
    common = {
        "source_readiness": "adapter_ready",
        "snapshot_head_block": 100,
        "tokens": 2,
        "coverage_provenance_sha256": SHA,
        "eligible_tokens": 1,
        "canonical_price_series": True,
        "source_coverage_complete": True,
        "phase2_universe_source_ready": True,
        "phase2_universe_frozen": False,
    }
    return {
        "launch": {
            **common,
            "source_id": "launch",
            "price_points": 5,
            "priced_points": 5,
        },
        "direct": {
            **common,
            "source_id": "direct",
            "coverage_price_points": 5,
            "coverage_priced_points": 5,
            "canonical_price_points": 3,
        },
    }


def test_universe_source_bundle_requires_ledger_matched_provenance():
    report = validate_phase2_universe_source_bundle(
        summaries(),
        coverage_ledger=ledger(),
        source_inventory=INVENTORY,
    )

    assert report["version"] == PHASE2_UNIVERSE_SOURCE_BUNDLE_VERSION
    assert report["sources"] == 2
    assert report["coverage_provenance_matches_ledger"] is True
    assert report["phase2_universe_source_bundle_ready"] is True
    assert report["phase2_universe_frozen"] is False


def test_universe_source_bundle_rejects_incomplete_ledger():
    with pytest.raises(ValueError, match="14/14 complete coverage"):
        validate_phase2_universe_source_bundle(
            summaries(),
            coverage_ledger=ledger("not_started"),
            source_inventory=INVENTORY,
        )


def test_universe_source_bundle_rejects_provenance_substitution():
    data = summaries()
    data["direct"]["coverage_provenance_sha256"] = "cd" * 32

    with pytest.raises(ValueError, match="coverage provenance drift"):
        validate_phase2_universe_source_bundle(
            data,
            coverage_ledger=ledger(),
            source_inventory=INVENTORY,
        )


def test_universe_source_bundle_rejects_point_count_substitution():
    data = summaries()
    data["launch"]["price_points"] = 4
    data["launch"]["priced_points"] = 4

    with pytest.raises(ValueError, match="point count drift"):
        validate_phase2_universe_source_bundle(
            data,
            coverage_ledger=ledger(),
            source_inventory=INVENTORY,
        )
