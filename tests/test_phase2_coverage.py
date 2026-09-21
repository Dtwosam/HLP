import pytest

from hlp.data.phase2_coverage import validate_phase2_source_coverage


SHA = "ab" * 32
INVENTORY = [
    {"source_id": "pons_v1", "readiness": "phase1_proven"},
    {"source_id": "noxa", "readiness": "adapter_ready"},
]


def complete(source_id):
    return {
        "source_id": source_id,
        "coverage_status": "complete",
        "required_start_block": 10,
        "first_block": 10,
        "last_block": 100,
        "continuous": True,
        "missing_ranges": [],
        "tokens_discovered": 5,
        "price_points": 20,
        "priced_points": 20,
        "observed_volume_usd": "1234.5",
        "provenance_sha256": SHA,
    }


def test_coverage_gate_requires_every_inventory_source_complete():
    report = validate_phase2_source_coverage(
        INVENTORY,
        [complete("pons_v1"), complete("noxa")],
        snapshot_head_block=100,
    )

    assert report["all_sources_reported"] is True
    assert report["phase2_universe_coverage_complete"] is True
    assert report["incomplete_source_ids"] == []


def test_adapter_readiness_does_not_substitute_for_historical_coverage():
    report = validate_phase2_source_coverage(
        INVENTORY,
        [complete("pons_v1")],
        snapshot_head_block=100,
    )

    assert report["missing_source_rows"] == ["noxa"]
    assert report["phase2_universe_coverage_complete"] is False


def test_partial_coverage_keeps_gate_closed():
    partial = {
        "source_id": "noxa",
        "coverage_status": "partial",
        "required_start_block": 10,
        "first_block": 20,
        "last_block": 100,
        "continuous": True,
        "missing_ranges": [],
        "tokens_discovered": 1,
        "price_points": 2,
        "priced_points": 2,
        "provenance_sha256": None,
    }
    report = validate_phase2_source_coverage(
        INVENTORY,
        [complete("pons_v1"), partial],
        snapshot_head_block=100,
    )

    assert report["coverage_status_counts"]["partial"] == 1
    assert report["incomplete_source_ids"] == ["noxa"]
    assert report["phase2_universe_coverage_complete"] is False


def test_complete_coverage_must_reach_snapshot_and_be_continuous():
    with pytest.raises(ValueError, match="does not reach snapshot"):
        validate_phase2_source_coverage(
            INVENTORY,
            [{**complete("pons_v1"), "last_block": 99}],
            snapshot_head_block=100,
        )

    with pytest.raises(ValueError, match="not continuous"):
        validate_phase2_source_coverage(
            INVENTORY,
            [{**complete("pons_v1"), "continuous": False}],
            snapshot_head_block=100,
        )


def test_complete_coverage_requires_sha256_provenance():
    with pytest.raises(ValueError, match="provenance_sha256"):
        validate_phase2_source_coverage(
            INVENTORY,
            [{**complete("pons_v1"), "provenance_sha256": "bad"}],
            snapshot_head_block=100,
        )


def test_blocked_coverage_requires_reason():
    blocked = {
        "source_id": "noxa",
        "coverage_status": "blocked",
        "required_start_block": 10,
        "first_block": None,
        "last_block": None,
        "continuous": None,
        "missing_ranges": [],
    }
    with pytest.raises(ValueError, match="blocking_reason"):
        validate_phase2_source_coverage(
            INVENTORY,
            [complete("pons_v1"), blocked],
            snapshot_head_block=100,
        )
