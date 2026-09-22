import copy

import pytest

from hlp.data.phase2_coverage import (
    validate_phase2_coverage_ledger,
)
from hlp.data.phase2_coverage_promotion import (
    build_phase2_pools_fun_promotion_review_handoff,
    validate_phase2_coverage_ledger_commit,
    validate_phase2_pools_fun_promotion_review_receipt,
    validate_phase2_pools_fun_promotion_proposal_receipt,
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



def pools_fun_report():
    return {
        "source_id": "pools_fun",
        "source_readiness": "adapter_ready",
        "coverage_status": "complete",
        "required_start_block": 0,
        "first_block": 0,
        "last_block": SNAPSHOT,
        "continuous": True,
        "missing_ranges": [],
        "tokens_discovered": 2,
        "price_points": 3,
        "priced_points": 3,
        "observed_volume_usd": None,
        "provenance_sha256": "ef" * 32,
        "blocking_reason": None,
        "snapshot_head_block": SNAPSHOT,
    }


def test_pools_fun_promotion_review_is_read_only_and_exact():
    report = build_phase2_pools_fun_promotion_review_handoff(
        ledger({"pons_v1", "pons_v2"}),
        pools_fun_report(),
        build_phase2_source_inventory(),
        coverage_run_id=301,
        coverage_artifact_digest="sha256:" + "11" * 32,
        coverage_report_sha256="22" * 32,
        planner_run_id=302,
        planner_artifact_digest="sha256:" + "33" * 32,
        canonical_ledger_sha256="44" * 32,
    )

    assert report["complete_source_ids_before"] == ["pons_v1", "pons_v2"]
    assert report["complete_source_ids_after_if_promoted"] == [
        "pons_v1",
        "pons_v2",
        "pools_fun",
    ]
    assert report["promotion_generated_inputs"]["coverage_run_id"] == "301"
    assert report["promotion_review_required"] is True
    assert report["promotion_dispatched"] is False
    assert report["proposal_created"] is False
    assert report["canonical_coverage_ledger_mutated"] is False


def promotion_review_receipt():
    row = build_phase2_pools_fun_promotion_review_handoff(
        ledger({"pons_v1", "pons_v2"}),
        pools_fun_report(),
        build_phase2_source_inventory(),
        coverage_run_id=301,
        coverage_artifact_digest="sha256:" + "11" * 32,
        coverage_report_sha256="22" * 32,
        planner_run_id=302,
        planner_artifact_digest="sha256:" + "33" * 32,
        canonical_ledger_sha256="44" * 32,
    )
    row.update({
        "promotion_review_control_run_id": 303,
        "promotion_frontier_run_id": 304,
        "promotion_frontier_artifact_digest": "sha256:" + "55" * 32,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "66" * 20,
    })
    return row


def test_pools_fun_promotion_review_receipt_rejects_dispatch_claim():
    row = promotion_review_receipt()
    row["promotion_dispatched"] = True
    with pytest.raises(ValueError, match="read-only field"):
        validate_phase2_pools_fun_promotion_review_receipt(row)


def test_pools_fun_promotion_review_receipt_validates_generated_inputs():
    report = validate_phase2_pools_fun_promotion_review_receipt(
        promotion_review_receipt()
    )

    assert report["promotion_review_control_run_id"] == 303
    assert report["coverage_run_id"] == 301
    assert report["promotion_generated_inputs"]["expected_source_id"] == (
        "pools_fun"
    )
    assert report["promotion_dispatched"] is False



def promotion_proposal_receipt():
    return {
        "version": "phase2-pools-fun-promotion-proposal-v1",
        "promotion_proposal_control_run_id": 401,
        "promotion_review_run_id": 402,
        "promotion_review_artifact_digest": "sha256:" + "11" * 32,
        "node_dispatch_control_run_id": 403,
        "promotion_run_id": 404,
        "promotion_artifact_digest": "sha256:" + "22" * 32,
        "promotion_handoff_sha256": "33" * 32,
        "proposed_ledger_sha256": "44" * 32,
        "base_ledger_sha256": "55" * 32,
        "source_id": "pools_fun",
        "promotion_workflow": "phase2-source-coverage-promotion.yml",
        "complete_source_ids_before": ["pons_v1", "pons_v2"],
        "complete_source_ids_after": ["pons_v1", "pons_v2", "pools_fun"],
        "phase2_universe_coverage_complete": False,
        "ledger_commit_generated_inputs": {
            "promotion_run_id": "404",
            "expected_artifact_digest": "sha256:" + "22" * 32,
            "expected_handoff_sha256": "33" * 32,
            "expected_proposed_ledger_sha256": "44" * 32,
            "expected_source_id": "pools_fun",
        },
        "ledger_commit_approval_input": "apply_proposed_ledger",
        "ledger_commit_approval_value_supplied": False,
        "proposal_created": True,
        "proposal_validated": True,
        "canonical_coverage_ledger_mutated": False,
        "ledger_commit_authorized": False,
    }


def test_pools_fun_proposal_receipt_exposes_commit_inputs_without_approval():
    report = validate_phase2_pools_fun_promotion_proposal_receipt(
        promotion_proposal_receipt()
    )

    assert report["promotion_run_id"] == 404
    assert report["ledger_commit_generated_inputs"]["expected_source_id"] == (
        "pools_fun"
    )
    assert report["ledger_commit_approval_value_supplied"] is False
    assert report["canonical_coverage_ledger_mutated"] is False


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("proposal_created", False, "proposal proof"),
        ("proposal_validated", False, "validation proof"),
        ("ledger_commit_authorized", True, "authorizes"),
        (
            "ledger_commit_approval_value_supplied",
            True,
            "already supplies",
        ),
    ],
)
def test_pools_fun_proposal_receipt_rejects_authorization_drift(
    field,
    value,
    match,
):
    row = promotion_proposal_receipt()
    row[field] = value
    with pytest.raises(ValueError, match=match):
        validate_phase2_pools_fun_promotion_proposal_receipt(row)
