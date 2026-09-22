import copy

import pytest

from hlp.data.phase2_coverage import (
    validate_phase2_coverage_ledger,
)
from hlp.data.phase2_coverage_promotion import (
    validate_phase2_coverage_ledger_commit,
)
from hlp.data.phase2_sources import build_phase2_source_inventory


SHA = "ab" * 32
PROPOSED_SHA = "cd" * 32
SNAPSHOT = 100


def ledger(complete):
    rows = []
    for source in build_phase2_source_inventory():
        source_id = source["source_id"]
        base = {
            "source_id": source_id,
            "source_readiness": source["readiness"],
            "required_start_block": 0,
            "observed_volume_usd": None,
            "blocking_reason": None,
        }
        if source_id in complete:
            rows.append({
                **base,
                "coverage_status": "complete",
                "first_block": 0,
                "last_block": SNAPSHOT,
                "continuous": True,
                "missing_ranges": [],
                "tokens_discovered": 1,
                "price_points": 1,
                "priced_points": 1,
                "provenance_sha256": "ef" * 32,
            })
        else:
            rows.append({
                **base,
                "coverage_status": "not_started",
                "first_block": None,
                "last_block": None,
                "continuous": None,
                "missing_ranges": [],
                "tokens_discovered": 0,
                "price_points": 0,
                "priced_points": 0,
                "provenance_sha256": None,
            })
    return {
        "version": "phase2-source-coverage-v1",
        "snapshot_head_block": SNAPSHOT,
        "sources": rows,
    }


def fixtures():
    before_ids = {"pons_v1", "pons_v2"}
    after_ids = before_ids | {"pools_fun"}
    current = ledger(before_ids)
    proposed = ledger(after_ids)
    validation = validate_phase2_coverage_ledger(
        proposed,
        build_phase2_source_inventory(),
    )
    handoff = {
        "version": "phase2-source-coverage-promotion-v1",
        "source_id": "pools_fun",
        "base_ledger_sha256": SHA,
        "proposed_ledger_sha256": PROPOSED_SHA,
        "complete_source_ids_before": sorted(before_ids),
        "complete_source_ids_after": sorted(after_ids),
        "phase2_universe_coverage_complete": False,
        "proposal_only": True,
        "canonical_ledger_mutated": False,
    }
    return current, proposed, validation, handoff


def test_ledger_commit_accepts_exact_single_source_advance():
    current, proposed, validation, handoff = fixtures()
    result = validate_phase2_coverage_ledger_commit(
        current,
        proposed,
        handoff,
        validation,
        build_phase2_source_inventory(),
        expected_source_id="pools_fun",
        current_ledger_sha256=SHA,
        proposed_ledger_sha256=PROPOSED_SHA,
    )

    assert result["newly_complete_source_ids"] == ["pools_fun"]
    assert result["complete_source_ids_before"] == [
        "pons_v1",
        "pons_v2",
    ]
    assert result["complete_source_ids_after"] == [
        "pons_v1",
        "pons_v2",
        "pools_fun",
    ]
    assert result["canonical_ledger_mutation_allowed"] is True


def test_ledger_commit_rejects_stale_base_sha():
    current, proposed, validation, handoff = fixtures()

    with pytest.raises(ValueError, match="promotion is stale"):
        validate_phase2_coverage_ledger_commit(
            current,
            proposed,
            handoff,
            validation,
            build_phase2_source_inventory(),
            expected_source_id="pools_fun",
            current_ledger_sha256="12" * 32,
            proposed_ledger_sha256=PROPOSED_SHA,
        )


def test_ledger_commit_rejects_proposed_sha_linkage_drift():
    current, proposed, validation, handoff = fixtures()

    with pytest.raises(ValueError, match="SHA linkage drift"):
        validate_phase2_coverage_ledger_commit(
            current,
            proposed,
            handoff,
            validation,
            build_phase2_source_inventory(),
            expected_source_id="pools_fun",
            current_ledger_sha256=SHA,
            proposed_ledger_sha256="12" * 32,
        )


def test_ledger_commit_rejects_multi_source_advance():
    current, _, _, handoff = fixtures()
    proposed = ledger({
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "doppler",
    })
    validation = validate_phase2_coverage_ledger(
        proposed,
        build_phase2_source_inventory(),
    )
    handoff = copy.deepcopy(handoff)
    handoff["complete_source_ids_after"] = [
        "doppler",
        "pons_v1",
        "pons_v2",
        "pools_fun",
    ]

    with pytest.raises(
        ValueError,
        match="complete exactly the expected source",
    ):
        validate_phase2_coverage_ledger_commit(
            current,
            proposed,
            handoff,
            validation,
            build_phase2_source_inventory(),
            expected_source_id="pools_fun",
            current_ledger_sha256=SHA,
            proposed_ledger_sha256=PROPOSED_SHA,
        )


def test_ledger_commit_rejects_complete_source_regression():
    current, _, _, handoff = fixtures()
    proposed = ledger({"pons_v1", "pools_fun"})
    validation = validate_phase2_coverage_ledger(
        proposed,
        build_phase2_source_inventory(),
    )
    handoff = copy.deepcopy(handoff)
    handoff["complete_source_ids_after"] = [
        "pons_v1",
        "pools_fun",
    ]

    with pytest.raises(ValueError, match="regresses complete sources"):
        validate_phase2_coverage_ledger_commit(
            current,
            proposed,
            handoff,
            validation,
            build_phase2_source_inventory(),
            expected_source_id="pools_fun",
            current_ledger_sha256=SHA,
            proposed_ledger_sha256=PROPOSED_SHA,
        )
