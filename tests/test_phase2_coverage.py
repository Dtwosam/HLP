import json
from pathlib import Path

import pytest

from hlp.data.phase2_coverage import (
    PHASE2_COVERAGE_LEDGER_VERSION,
    apply_phase2_source_coverage_report,
    validate_phase2_coverage_ledger,
    validate_phase2_source_coverage,
)
from hlp.data.phase2_sources import build_phase2_source_inventory


SHA = "ab" * 32
INVENTORY = [
    {"source_id": "pons_v1", "readiness": "phase1_proven"},
    {"source_id": "noxa", "readiness": "adapter_ready"},
]


def complete(source_id):
    return {
        "source_id": source_id,
        "source_readiness": (
            "phase1_proven" if source_id == "pons_v1" else "adapter_ready"
        ),
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



def test_not_started_source_may_leave_required_start_unresolved():
    pending = {
        "source_id": "noxa",
        "source_readiness": "adapter_ready",
        "coverage_status": "not_started",
        "required_start_block": None,
        "first_block": None,
        "last_block": None,
        "continuous": None,
        "missing_ranges": [],
        "tokens_discovered": 0,
        "price_points": 0,
        "priced_points": 0,
        "provenance_sha256": None,
    }
    report = validate_phase2_source_coverage(
        INVENTORY,
        [complete("pons_v1"), pending],
        snapshot_head_block=100,
    )
    assert report["incomplete_source_ids"] == ["noxa"]


def test_complete_source_cannot_leave_required_start_unresolved():
    row = {**complete("pons_v1"), "required_start_block": None}
    with pytest.raises(ValueError, match="no required start"):
        validate_phase2_source_coverage(
            INVENTORY,
            [row],
            snapshot_head_block=100,
        )



def test_versioned_coverage_ledger_requires_every_inventory_source_row():
    pending = {
        "source_id": "noxa",
        "source_readiness": "adapter_ready",
        "coverage_status": "not_started",
        "required_start_block": None,
        "first_block": None,
        "last_block": None,
        "continuous": None,
        "missing_ranges": [],
        "tokens_discovered": 0,
        "price_points": 0,
        "priced_points": 0,
        "provenance_sha256": None,
    }
    report = validate_phase2_coverage_ledger(
        {
            "version": PHASE2_COVERAGE_LEDGER_VERSION,
            "snapshot_head_block": 100,
            "sources": [complete("pons_v1"), pending],
        },
        INVENTORY,
    )
    assert report["version"] == PHASE2_COVERAGE_LEDGER_VERSION
    assert report["all_sources_reported"] is True
    assert report["coverage_status_counts"]["complete"] == 1
    assert report["complete_source_ids"] == ["pons_v1"]
    assert report["phase2_universe_coverage_complete"] is False


def test_coverage_ledger_rejects_missing_source_row():
    with pytest.raises(ValueError, match="source contract mismatch"):
        validate_phase2_coverage_ledger(
            {
                "version": PHASE2_COVERAGE_LEDGER_VERSION,
                "snapshot_head_block": 100,
                "sources": [complete("pons_v1")],
            },
            INVENTORY,
        )



def test_repository_phase2_coverage_ledger_matches_source_inventory():
    ledger = json.loads(
        Path(".github/phase2-source-coverage.json").read_text()
    )
    report = validate_phase2_coverage_ledger(
        ledger,
        build_phase2_source_inventory(),
    )

    assert report["version"] == PHASE2_COVERAGE_LEDGER_VERSION
    assert report["snapshot_head_block"] == 54_486_035
    assert report["inventory_sources"] == 14
    assert report["reported_sources"] == 14
    assert report["all_sources_reported"] is True
    assert report["coverage_status_counts"]["complete"] == 2
    assert report["complete_source_ids"] == ["pons_v1", "pons_v2"]
    assert report["phase2_universe_coverage_complete"] is False



def test_coverage_ledger_rejects_source_readiness_drift():
    pending = {
        "source_id": "noxa",
        "source_readiness": "decoder_ready",
        "coverage_status": "not_started",
        "required_start_block": None,
        "first_block": None,
        "last_block": None,
        "continuous": None,
        "missing_ranges": [],
        "tokens_discovered": 0,
        "price_points": 0,
        "priced_points": 0,
        "provenance_sha256": None,
    }
    with pytest.raises(ValueError, match="readiness drift"):
        validate_phase2_coverage_ledger(
            {
                "version": PHASE2_COVERAGE_LEDGER_VERSION,
                "snapshot_head_block": 100,
                "sources": [complete("pons_v1"), pending],
            },
            INVENTORY,
        )



def test_repository_pons_rows_are_complete_and_provenanced():
    ledger = json.loads(
        Path(".github/phase2-source-coverage.json").read_text()
    )
    rows = {row["source_id"]: row for row in ledger["sources"]}

    v1 = rows["pons_v1"]
    assert v1["coverage_status"] == "complete"
    assert v1["required_start_block"] == 8_621_658
    assert v1["last_block"] == 54_486_035
    assert v1["tokens_discovered"] == 268_688
    assert v1["price_points"] == v1["priced_points"] == 63_560_072
    assert v1["provenance_sha256"] == (
        "74a43a5401d88d299070b21414e7d2ef"
        "aaa90c8469596d2207ef41a9456ede31"
    )

    v2 = rows["pons_v2"]
    assert v2["coverage_status"] == "complete"
    assert v2["required_start_block"] == 27_027_321
    assert v2["last_block"] == 54_486_035
    assert v2["tokens_discovered"] == 225_951
    assert v2["price_points"] == v2["priced_points"] == 24_319_652
    assert v2["provenance_sha256"] == (
        "2e880af79350530d4c30cda8d10778f"
        "ee8156c284ccb523cae226f1a886cc566"
    )



def test_complete_coverage_rejects_unpriced_points():
    row = {
        **complete("pons_v1"),
        "price_points": 20,
        "priced_points": 19,
    }
    with pytest.raises(ValueError, match="unpriced points"):
        validate_phase2_source_coverage(
            INVENTORY,
            [row],
            snapshot_head_block=100,
        )



def test_apply_source_coverage_report_replaces_only_target_row():
    ledger = {
        "version": PHASE2_COVERAGE_LEDGER_VERSION,
        "snapshot_head_block": 100,
        "sources": [
            complete("pons_v1"),
            {
                "source_id": "noxa",
                "source_readiness": "adapter_ready",
                "coverage_status": "not_started",
                "required_start_block": None,
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
    report = {
        "source_id": "noxa",
        "source_readiness": "adapter_ready",
        "coverage_status": "complete",
        "required_start_block": 20,
        "first_block": 20,
        "last_block": 100,
        "continuous": True,
        "missing_ranges": [],
        "tokens_discovered": 3,
        "price_points": 9,
        "priced_points": 9,
        "observed_volume_usd": None,
        "provenance_sha256": "cd" * 32,
        "blocking_reason": None,
        "snapshot_head_block": 100,
        "extra_audit_field": "preserved-outside-ledger-only",
    }
    updated, validation = apply_phase2_source_coverage_report(
        ledger,
        INVENTORY,
        report,
    )

    rows = {row["source_id"]: row for row in updated["sources"]}
    assert rows["pons_v1"] == ledger["sources"][0]
    assert rows["noxa"]["coverage_status"] == "complete"
    assert "extra_audit_field" not in rows["noxa"]
    assert validation["phase2_universe_coverage_complete"] is True


def test_apply_source_coverage_report_rejects_snapshot_drift():
    ledger = {
        "version": PHASE2_COVERAGE_LEDGER_VERSION,
        "snapshot_head_block": 100,
        "sources": [
            complete("pons_v1"),
            {
                "source_id": "noxa",
                "source_readiness": "adapter_ready",
                "coverage_status": "not_started",
                "required_start_block": None,
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
    report = {
        **ledger["sources"][1],
        "snapshot_head_block": 99,
    }
    with pytest.raises(ValueError, match="snapshot drift"):
        apply_phase2_source_coverage_report(
            ledger,
            INVENTORY,
            report,
        )
