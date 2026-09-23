import copy

import pytest

from hlp.data.phase2_coverage import (
    validate_phase2_coverage_ledger,
)
from hlp.data.phase2_coverage_promotion import (
    build_phase2_pools_fun_promotion_review_handoff,
    build_phase2_pools_trade_instant_promotion_review_handoff,
    build_phase2_pools_trade_lbp_promotion_review_handoff,
    validate_phase2_coverage_ledger_commit,
    validate_phase2_pools_fun_promotion_review_receipt,
    validate_phase2_pools_fun_promotion_proposal_receipt,
    validate_phase2_pools_fun_ledger_commit_receipt,
    validate_phase2_pools_fun_ledger_approved_receipt,
    validate_phase2_pools_fun_post_commit_frontier,
    validate_phase2_pools_trade_instant_promotion_review_receipt,
    validate_phase2_pools_trade_instant_promotion_proposal_receipt,
    validate_phase2_pools_trade_instant_ledger_commit_receipt,
    validate_phase2_pools_trade_instant_ledger_approved_receipt,
    validate_phase2_pools_trade_lbp_promotion_review_receipt,
    validate_phase2_pools_trade_lbp_promotion_proposal_receipt,
    validate_phase2_pools_trade_lbp_ledger_commit_receipt,
    validate_phase2_pools_trade_lbp_ledger_approved_receipt,
    validate_phase2_pools_trade_lbp_post_commit_frontier,
    validate_phase2_pools_trade_instant_post_commit_frontier,
)
from hlp.data.phase2_sources import build_phase2_source_inventory
from hlp.data.phase2_first_wave import (
    PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS,
    PHASE2_FIRST_WAVE_NODE_IDS,
)
from hlp.data.phase2_post_fanout import (
    PHASE2_POST_FANOUT_AUTO_NODE_IDS,
    PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS,
    PHASE2_PRE_SELECTOR_AUTO_NODE_IDS,
    PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS,
    PHASE2_AFTER_POST_SELECTOR_AUTO_NODE_IDS,
)


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
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "aa" * 20,
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



def pools_fun_ledger_commit_receipt():
    return {
        "version": "phase2-source-coverage-ledger-commit-v1",
        "source_id": "pools_fun",
        "promotion_run_id": 404,
        "promotion_artifact_name": "phase2-source-coverage-promotion-pools_fun",
        "promotion_artifact_digest": "sha256:" + "22" * 32,
        "promotion_handoff_sha256": "33" * 32,
        "base_ledger_sha256": "55" * 32,
        "proposed_ledger_sha256": "44" * 32,
        "complete_source_ids_before": ["pons_v1", "pons_v2"],
        "complete_source_ids_after": ["pons_v1", "pons_v2", "pools_fun"],
        "phase2_universe_coverage_complete": False,
        "canonical_ledger_commit_sha": "66" * 20,
        "explicit_approval": True,
        "canonical_ledger_mutated": True,
    }


def test_pools_fun_ledger_commit_receipt_requires_exact_approved_write():
    report = validate_phase2_pools_fun_ledger_commit_receipt(
        pools_fun_ledger_commit_receipt(),
        expected_promotion_run_id=404,
        expected_promotion_artifact_digest="sha256:" + "22" * 32,
        expected_promotion_handoff_sha256="33" * 32,
        expected_proposed_ledger_sha256="44" * 32,
    )
    assert report["canonical_ledger_commit_sha"] == "66" * 20
    assert report["complete_source_ids_after"] == [
        "pons_v1",
        "pons_v2",
        "pools_fun",
    ]


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("explicit_approval", False, "explicit approval"),
        ("canonical_ledger_mutated", False, "mutation proof"),
        ("source_id", "doppler", "source identity"),
    ],
)
def test_pools_fun_ledger_commit_receipt_rejects_drift(field, value, match):
    row = pools_fun_ledger_commit_receipt()
    row[field] = value
    with pytest.raises(ValueError, match=match):
        validate_phase2_pools_fun_ledger_commit_receipt(
            row,
            expected_promotion_run_id=404,
            expected_promotion_artifact_digest="sha256:" + "22" * 32,
            expected_promotion_handoff_sha256="33" * 32,
            expected_proposed_ledger_sha256="44" * 32,
        )


def pools_fun_post_commit_plans():
    pre_frontier = (
        set(PHASE2_FIRST_WAVE_NODE_IDS)
        | set(PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS)
        | set(PHASE2_POST_FANOUT_AUTO_NODE_IDS)
        | set(PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS)
        | set(PHASE2_PRE_SELECTOR_AUTO_NODE_IDS)
        | {"shared:direct_selector_freeze"}
        | set(PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS)
        | set(PHASE2_AFTER_POST_SELECTOR_AUTO_NODE_IDS)
    )
    active = sorted(pre_frontier - {"coverage:pools_fun"})
    verified_completed = sorted(pre_frontier | {"promote:pools_fun"})
    execution = {
        "canonical_complete_source_ids": ["pons_v1", "pons_v2", "pools_fun"],
        "complete_sources": 3,
        "incomplete_sources": 11,
        "phase2_universe_coverage_complete": False,
        "completed_node_ids": active,
        "ignored_completed_node_ids": [
            "coverage:pools_fun",
            "promote:pools_fun",
        ],
        "ready_to_dispatch_node_ids": ["promote:pools_trade_instant"],
        "awaiting_explicit_approval_node_ids": [],
        "ledger_commit_approval_node_ids": [],
        "manual_ledger_commit_node_ids": [],
    }
    verified = {
        "completed_node_ids": verified_completed,
        "node_dispatch_run_ids_consumed": list(range(30000, 30041)),
        "all_runs_current_or_ledger_only_ancestors": True,
    }
    dispatch = {
        "nodes": [{
            "node_id": "promote:pools_trade_instant",
            "workflow": "phase2-source-coverage-promotion.yml",
            "status": "ready_to_dispatch",
            "run_id_inputs": {"coverage_run_id": "31000"},
            "remaining_manual_inputs": [
                "coverage_artifact_name",
                "coverage_report_path",
                "expected_artifact_digest",
                "expected_report_sha256",
                "expected_source_id",
            ],
        }],
    }
    return execution, verified, dispatch


def test_pools_fun_post_commit_frontier_unlocks_only_next_promotion():
    execution, verified, dispatch = pools_fun_post_commit_plans()
    report = validate_phase2_pools_fun_post_commit_frontier(
        execution,
        verified,
        dispatch,
    )
    assert report["complete_sources"] == 3
    assert report["active_completed_execution_nodes"] == 40
    assert report["node_dispatch_control_runs_consumed"] == 41
    assert report["next_promotion_node_id"] == "promote:pools_trade_instant"


def test_pools_fun_post_commit_frontier_rejects_hidden_auto_work():
    execution, verified, dispatch = pools_fun_post_commit_plans()
    execution["ready_to_dispatch_node_ids"].append("coverage:doppler")
    with pytest.raises(ValueError, match="next promotion drift"):
        validate_phase2_pools_fun_post_commit_frontier(
            execution,
            verified,
            dispatch,
        )



def test_pools_fun_proposal_receipt_rejects_head_drift():
    row = promotion_proposal_receipt()
    row["execution_head_sha"] = "bad"
    with pytest.raises(ValueError, match="execution head"):
        validate_phase2_pools_fun_promotion_proposal_receipt(row)



def pools_trade_instant_report():
    return {
        "source_id": "pools_trade_instant",
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


def test_pools_trade_instant_review_prepares_exact_4_of_14_advance():
    report = build_phase2_pools_trade_instant_promotion_review_handoff(
        ledger({"pons_v1", "pons_v2", "pools_fun"}),
        pools_trade_instant_report(),
        build_phase2_source_inventory(),
        coverage_run_id=501,
        coverage_artifact_digest="sha256:" + "11" * 32,
        coverage_report_sha256="22" * 32,
        planner_run_id=502,
        planner_artifact_digest="sha256:" + "33" * 32,
        canonical_ledger_sha256="44" * 32,
    )
    assert report["complete_source_ids_before"] == [
        "pons_v1",
        "pons_v2",
        "pools_fun",
    ]
    assert report["complete_source_ids_after_if_promoted"] == [
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
    ]
    assert report["promotion_dispatched"] is False


def pools_trade_instant_review_receipt():
    row = build_phase2_pools_trade_instant_promotion_review_handoff(
        ledger({"pons_v1", "pons_v2", "pools_fun"}),
        pools_trade_instant_report(),
        build_phase2_source_inventory(),
        coverage_run_id=501,
        coverage_artifact_digest="sha256:" + "11" * 32,
        coverage_report_sha256="22" * 32,
        planner_run_id=502,
        planner_artifact_digest="sha256:" + "33" * 32,
        canonical_ledger_sha256="44" * 32,
    )
    row.update({
        "promotion_review_control_run_id": 503,
        "pools_fun_ledger_approval_run_id": 504,
        "pools_fun_ledger_approval_artifact_digest": "sha256:" + "55" * 32,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "66" * 20,
    })
    return row


def test_pools_trade_instant_review_receipt_is_read_only():
    report = validate_phase2_pools_trade_instant_promotion_review_receipt(
        pools_trade_instant_review_receipt()
    )
    assert report["promotion_review_control_run_id"] == 503
    assert report["coverage_run_id"] == 501
    assert report["promotion_generated_inputs"]["expected_source_id"] == (
        "pools_trade_instant"
    )
    assert report["canonical_coverage_ledger_mutated"] is False



def pools_fun_ledger_approved_receipt():
    return {
        "version": "phase2-pools-fun-ledger-approved-receipt-v1",
        "ledger_approval_control_run_id": 601,
        "execution_branch": "phase1/data-acquisition-spike",
        "approval_execution_head_sha": "11" * 20,
        "promotion_proposal_run_id": 602,
        "promotion_proposal_artifact_digest": "sha256:" + "22" * 32,
        "ledger_commit_run_id": 603,
        "ledger_commit_artifact_digest": "sha256:" + "33" * 32,
        "canonical_ledger_commit_sha": "44" * 20,
        "base_ledger_sha256": "55" * 32,
        "canonical_coverage_ledger_sha256": "66" * 32,
        "node_dispatch_control_run_ids_consumed": list(range(700, 741)),
        "selector_run_id": 604,
        "planner_run_id": 605,
        "planner_artifact_digest": "sha256:" + "77" * 32,
        "canonical_complete_source_ids": [
            "pons_v1",
            "pons_v2",
            "pools_fun",
        ],
        "next_promotion_node_id": "promote:pools_trade_instant",
        "human_approval_input": "apply_pools_fun_ledger",
        "human_approval_value": True,
        "canonical_ledger_mutated": True,
        "automatic_acquisition_complete": True,
        "phase2_universe_coverage_complete": False,
    }


def test_pools_fun_ledger_approved_receipt_validates_3_of_14_handoff():
    report = validate_phase2_pools_fun_ledger_approved_receipt(
        pools_fun_ledger_approved_receipt()
    )
    assert report["canonical_ledger_commit_sha"] == "44" * 20
    assert report["next_promotion_node_id"] == "promote:pools_trade_instant"
    assert len(report["node_dispatch_control_run_ids_consumed"]) == 41


def test_pools_fun_ledger_approved_receipt_rejects_false_approval():
    row = pools_fun_ledger_approved_receipt()
    row["human_approval_value"] = False
    with pytest.raises(ValueError, match="affirmative approval"):
        validate_phase2_pools_fun_ledger_approved_receipt(row)



def pools_trade_instant_proposal_receipt():
    return {
        "version": "phase2-pools-trade-instant-promotion-proposal-v1",
        "promotion_proposal_control_run_id": 801,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "11" * 20,
        "promotion_review_run_id": 802,
        "promotion_review_artifact_digest": "sha256:" + "22" * 32,
        "node_dispatch_control_run_id": 803,
        "promotion_run_id": 804,
        "promotion_workflow": "phase2-source-coverage-promotion.yml",
        "promotion_artifact_digest": "sha256:" + "33" * 32,
        "promotion_handoff_sha256": "44" * 32,
        "base_ledger_sha256": "55" * 32,
        "proposed_ledger_sha256": "66" * 32,
        "source_id": "pools_trade_instant",
        "complete_source_ids_before": [
            "pons_v1",
            "pons_v2",
            "pools_fun",
        ],
        "complete_source_ids_after": [
            "pons_v1",
            "pons_v2",
            "pools_fun",
            "pools_trade_instant",
        ],
        "phase2_universe_coverage_complete": False,
        "ledger_commit_generated_inputs": {
            "promotion_run_id": "804",
            "expected_artifact_digest": "sha256:" + "33" * 32,
            "expected_handoff_sha256": "44" * 32,
            "expected_proposed_ledger_sha256": "66" * 32,
            "expected_source_id": "pools_trade_instant",
        },
        "ledger_commit_approval_input": "apply_proposed_ledger",
        "ledger_commit_approval_value_supplied": False,
        "proposal_created": True,
        "proposal_validated": True,
        "canonical_coverage_ledger_mutated": False,
        "ledger_commit_authorized": False,
    }


def test_pools_trade_instant_proposal_receipt_exposes_unapproved_commit_inputs():
    report = validate_phase2_pools_trade_instant_promotion_proposal_receipt(
        pools_trade_instant_proposal_receipt()
    )
    assert report["promotion_run_id"] == 804
    assert report["ledger_commit_generated_inputs"]["expected_source_id"] == (
        "pools_trade_instant"
    )
    assert report["ledger_commit_approval_value_supplied"] is False


def test_pools_trade_instant_proposal_receipt_rejects_authorization():
    row = pools_trade_instant_proposal_receipt()
    row["ledger_commit_authorized"] = True
    with pytest.raises(ValueError, match="authorizes"):
        validate_phase2_pools_trade_instant_promotion_proposal_receipt(row)



def pools_trade_instant_ledger_commit_receipt():
    row = pools_fun_ledger_commit_receipt()
    row.update({
        "source_id": "pools_trade_instant",
        "promotion_run_id": 804,
        "promotion_artifact_name": (
            "phase2-source-coverage-promotion-pools_trade_instant"
        ),
        "promotion_artifact_digest": "sha256:" + "33" * 32,
        "promotion_handoff_sha256": "44" * 32,
        "base_ledger_sha256": "55" * 32,
        "proposed_ledger_sha256": "66" * 32,
        "complete_source_ids_before": [
            "pons_v1",
            "pons_v2",
            "pools_fun",
        ],
        "complete_source_ids_after": [
            "pons_v1",
            "pons_v2",
            "pools_fun",
            "pools_trade_instant",
        ],
        "canonical_ledger_commit_sha": "77" * 20,
    })
    return row


def test_pools_trade_instant_ledger_commit_receipt_validates_4_of_14():
    report = validate_phase2_pools_trade_instant_ledger_commit_receipt(
        pools_trade_instant_ledger_commit_receipt(),
        expected_promotion_run_id=804,
        expected_promotion_artifact_digest="sha256:" + "33" * 32,
        expected_promotion_handoff_sha256="44" * 32,
        expected_proposed_ledger_sha256="66" * 32,
    )
    assert report["canonical_ledger_commit_sha"] == "77" * 20


def pools_trade_instant_post_commit_plans():
    pre_frontier = (
        set(PHASE2_FIRST_WAVE_NODE_IDS)
        | set(PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS)
        | set(PHASE2_POST_FANOUT_AUTO_NODE_IDS)
        | set(PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS)
        | set(PHASE2_PRE_SELECTOR_AUTO_NODE_IDS)
        | {"shared:direct_selector_freeze"}
        | set(PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS)
        | set(PHASE2_AFTER_POST_SELECTOR_AUTO_NODE_IDS)
    )
    active = sorted(pre_frontier - {
        "coverage:pools_fun",
        "coverage:pools_trade_instant",
    })
    verified_completed = sorted(pre_frontier | {
        "promote:pools_fun",
        "promote:pools_trade_instant",
    })
    execution = {
        "canonical_complete_source_ids": [
            "pons_v1",
            "pons_v2",
            "pools_fun",
            "pools_trade_instant",
        ],
        "complete_sources": 4,
        "incomplete_sources": 10,
        "phase2_universe_coverage_complete": False,
        "completed_node_ids": active,
        "ignored_completed_node_ids": [
            "coverage:pools_fun",
            "promote:pools_fun",
            "coverage:pools_trade_instant",
            "promote:pools_trade_instant",
        ],
        "ready_to_dispatch_node_ids": ["promote:pools_trade_lbp"],
        "awaiting_explicit_approval_node_ids": [],
        "ledger_commit_approval_node_ids": [],
    }
    verified = {
        "completed_node_ids": verified_completed,
        "node_dispatch_run_ids_consumed": list(range(40000, 40042)),
        "all_runs_current_or_ledger_only_ancestors": True,
    }
    dispatch = {
        "nodes": [{
            "node_id": "promote:pools_trade_lbp",
            "workflow": "phase2-source-coverage-promotion.yml",
            "status": "ready_to_dispatch",
            "run_id_inputs": {"coverage_run_id": "41000"},
            "remaining_manual_inputs": [
                "coverage_artifact_name",
                "coverage_report_path",
                "expected_artifact_digest",
                "expected_report_sha256",
                "expected_source_id",
            ],
        }],
    }
    return execution, verified, dispatch


def test_pools_trade_instant_post_commit_frontier_unlocks_lbp_only():
    execution, verified, dispatch = pools_trade_instant_post_commit_plans()
    report = validate_phase2_pools_trade_instant_post_commit_frontier(
        execution,
        verified,
        dispatch,
    )
    assert report["complete_sources"] == 4
    assert report["active_completed_execution_nodes"] == 39
    assert report["node_dispatch_control_runs_consumed"] == 42
    assert report["next_promotion_node_id"] == "promote:pools_trade_lbp"



def pools_trade_instant_ledger_approved_receipt():
    return {
        "version": "phase2-pools-trade-instant-ledger-approved-receipt-v1",
        "ledger_approval_control_run_id": 901,
        "execution_branch": "phase1/data-acquisition-spike",
        "approval_execution_head_sha": "11" * 20,
        "promotion_proposal_run_id": 902,
        "promotion_proposal_artifact_digest": "sha256:" + "22" * 32,
        "ledger_commit_run_id": 903,
        "ledger_commit_artifact_digest": "sha256:" + "33" * 32,
        "canonical_ledger_commit_sha": "44" * 20,
        "base_ledger_sha256": "55" * 32,
        "canonical_coverage_ledger_sha256": "66" * 32,
        "node_dispatch_control_run_ids_consumed": list(range(1000, 1042)),
        "selector_run_id": 904,
        "planner_run_id": 905,
        "planner_artifact_digest": "sha256:" + "77" * 32,
        "canonical_complete_source_ids": [
            "pons_v1",
            "pons_v2",
            "pools_fun",
            "pools_trade_instant",
        ],
        "next_promotion_node_id": "promote:pools_trade_lbp",
        "human_approval_input": "apply_pools_trade_instant_ledger",
        "human_approval_value": True,
        "canonical_ledger_mutated": True,
        "automatic_acquisition_complete": True,
        "phase2_universe_coverage_complete": False,
    }


def test_pools_trade_instant_approved_receipt_validates_4_of_14_handoff():
    report = validate_phase2_pools_trade_instant_ledger_approved_receipt(
        pools_trade_instant_ledger_approved_receipt()
    )
    assert report["canonical_ledger_commit_sha"] == "44" * 20
    assert report["next_promotion_node_id"] == "promote:pools_trade_lbp"
    assert len(report["node_dispatch_control_run_ids_consumed"]) == 42



def pools_trade_lbp_report():
    return {
        "source_id": "pools_trade_lbp",
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


def test_pools_trade_lbp_review_prepares_exact_5_of_14_advance():
    report = build_phase2_pools_trade_lbp_promotion_review_handoff(
        ledger({
            "pons_v1",
            "pons_v2",
            "pools_fun",
            "pools_trade_instant",
        }),
        pools_trade_lbp_report(),
        build_phase2_source_inventory(),
        coverage_run_id=1101,
        coverage_artifact_digest="sha256:" + "11" * 32,
        coverage_report_sha256="22" * 32,
        planner_run_id=1102,
        planner_artifact_digest="sha256:" + "33" * 32,
        canonical_ledger_sha256="44" * 32,
    )
    assert report["complete_source_ids_after_if_promoted"] == [
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
    ]
    assert report["promotion_dispatched"] is False


def pools_trade_lbp_review_receipt():
    row = build_phase2_pools_trade_lbp_promotion_review_handoff(
        ledger({
            "pons_v1",
            "pons_v2",
            "pools_fun",
            "pools_trade_instant",
        }),
        pools_trade_lbp_report(),
        build_phase2_source_inventory(),
        coverage_run_id=1101,
        coverage_artifact_digest="sha256:" + "11" * 32,
        coverage_report_sha256="22" * 32,
        planner_run_id=1102,
        planner_artifact_digest="sha256:" + "33" * 32,
        canonical_ledger_sha256="44" * 32,
    )
    row.update({
        "promotion_review_control_run_id": 1103,
        "pools_trade_instant_ledger_approval_run_id": 1104,
        "pools_trade_instant_ledger_approval_artifact_digest": (
            "sha256:" + "55" * 32
        ),
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "66" * 20,
    })
    return row


def test_pools_trade_lbp_review_receipt_is_read_only():
    report = validate_phase2_pools_trade_lbp_promotion_review_receipt(
        pools_trade_lbp_review_receipt()
    )
    assert report["coverage_run_id"] == 1101
    assert report["promotion_generated_inputs"]["expected_source_id"] == (
        "pools_trade_lbp"
    )
    assert report["canonical_coverage_ledger_mutated"] is False



def pools_trade_lbp_proposal_receipt():
    return {
        "version": "phase2-pools-trade-lbp-promotion-proposal-v1",
        "promotion_proposal_control_run_id": 1201,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "11" * 20,
        "promotion_review_run_id": 1202,
        "promotion_review_artifact_digest": "sha256:" + "22" * 32,
        "node_dispatch_control_run_id": 1203,
        "promotion_run_id": 1204,
        "promotion_workflow": "phase2-source-coverage-promotion.yml",
        "promotion_artifact_digest": "sha256:" + "33" * 32,
        "promotion_handoff_sha256": "44" * 32,
        "base_ledger_sha256": "55" * 32,
        "proposed_ledger_sha256": "66" * 32,
        "source_id": "pools_trade_lbp",
        "complete_source_ids_before": [
            "pons_v1",
            "pons_v2",
            "pools_fun",
            "pools_trade_instant",
        ],
        "complete_source_ids_after": [
            "pons_v1",
            "pons_v2",
            "pools_fun",
            "pools_trade_instant",
            "pools_trade_lbp",
        ],
        "phase2_universe_coverage_complete": False,
        "ledger_commit_generated_inputs": {
            "promotion_run_id": "1204",
            "expected_artifact_digest": "sha256:" + "33" * 32,
            "expected_handoff_sha256": "44" * 32,
            "expected_proposed_ledger_sha256": "66" * 32,
            "expected_source_id": "pools_trade_lbp",
        },
        "ledger_commit_approval_input": "apply_proposed_ledger",
        "ledger_commit_approval_value_supplied": False,
        "proposal_created": True,
        "proposal_validated": True,
        "canonical_coverage_ledger_mutated": False,
        "ledger_commit_authorized": False,
    }


def test_pools_trade_lbp_proposal_receipt_is_approval_free():
    report = validate_phase2_pools_trade_lbp_promotion_proposal_receipt(
        pools_trade_lbp_proposal_receipt()
    )
    assert report["promotion_run_id"] == 1204
    assert report["ledger_commit_generated_inputs"]["expected_source_id"] == (
        "pools_trade_lbp"
    )
    assert report["ledger_commit_approval_value_supplied"] is False


def test_pools_trade_lbp_proposal_receipt_rejects_authorization():
    row = pools_trade_lbp_proposal_receipt()
    row["ledger_commit_authorized"] = True
    with pytest.raises(ValueError, match="authorizes"):
        validate_phase2_pools_trade_lbp_promotion_proposal_receipt(row)



def pools_trade_lbp_ledger_commit_receipt():
    row = pools_trade_instant_ledger_commit_receipt()
    row.update({
        "source_id": "pools_trade_lbp",
        "promotion_run_id": 1204,
        "promotion_artifact_name": (
            "phase2-source-coverage-promotion-pools_trade_lbp"
        ),
        "promotion_artifact_digest": "sha256:" + "33" * 32,
        "promotion_handoff_sha256": "44" * 32,
        "base_ledger_sha256": "55" * 32,
        "proposed_ledger_sha256": "66" * 32,
        "complete_source_ids_before": [
            "pons_v1",
            "pons_v2",
            "pools_fun",
            "pools_trade_instant",
        ],
        "complete_source_ids_after": [
            "pons_v1",
            "pons_v2",
            "pools_fun",
            "pools_trade_instant",
            "pools_trade_lbp",
        ],
        "canonical_ledger_commit_sha": "77" * 20,
    })
    return row


def test_pools_trade_lbp_ledger_commit_receipt_validates_5_of_14():
    report = validate_phase2_pools_trade_lbp_ledger_commit_receipt(
        pools_trade_lbp_ledger_commit_receipt(),
        expected_promotion_run_id=1204,
        expected_promotion_artifact_digest="sha256:" + "33" * 32,
        expected_promotion_handoff_sha256="44" * 32,
        expected_proposed_ledger_sha256="66" * 32,
    )
    assert report["canonical_ledger_commit_sha"] == "77" * 20


def pools_trade_lbp_post_commit_plans():
    pre_frontier = (
        set(PHASE2_FIRST_WAVE_NODE_IDS)
        | set(PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS)
        | set(PHASE2_POST_FANOUT_AUTO_NODE_IDS)
        | set(PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS)
        | set(PHASE2_PRE_SELECTOR_AUTO_NODE_IDS)
        | {"shared:direct_selector_freeze"}
        | set(PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS)
        | set(PHASE2_AFTER_POST_SELECTOR_AUTO_NODE_IDS)
    )
    canonical_coverages = {
        "coverage:pools_fun",
        "coverage:pools_trade_instant",
        "coverage:pools_trade_lbp",
    }
    active = sorted(pre_frontier - canonical_coverages)
    verified_completed = sorted(pre_frontier | {
        "promote:pools_fun",
        "promote:pools_trade_instant",
        "promote:pools_trade_lbp",
    })
    execution = {
        "canonical_complete_source_ids": [
            "pons_v1",
            "pons_v2",
            "pools_fun",
            "pools_trade_instant",
            "pools_trade_lbp",
        ],
        "complete_sources": 5,
        "incomplete_sources": 9,
        "phase2_universe_coverage_complete": False,
        "completed_node_ids": active,
        "ignored_completed_node_ids": [
            "coverage:pools_fun",
            "promote:pools_fun",
            "coverage:pools_trade_instant",
            "promote:pools_trade_instant",
            "coverage:pools_trade_lbp",
            "promote:pools_trade_lbp",
        ],
        "ready_to_dispatch_node_ids": ["promote:doppler"],
        "awaiting_explicit_approval_node_ids": [],
        "ledger_commit_approval_node_ids": [],
    }
    verified = {
        "completed_node_ids": verified_completed,
        "node_dispatch_run_ids_consumed": list(range(50000, 50043)),
        "all_runs_current_or_ledger_only_ancestors": True,
    }
    dispatch = {
        "nodes": [{
            "node_id": "promote:doppler",
            "workflow": "phase2-source-coverage-promotion.yml",
            "status": "ready_to_dispatch",
            "run_id_inputs": {"coverage_run_id": "51000"},
            "remaining_manual_inputs": [
                "coverage_artifact_name",
                "coverage_report_path",
                "expected_artifact_digest",
                "expected_report_sha256",
                "expected_source_id",
            ],
        }],
    }
    return execution, verified, dispatch


def test_pools_trade_lbp_post_commit_frontier_unlocks_doppler_only():
    execution, verified, dispatch = pools_trade_lbp_post_commit_plans()
    report = validate_phase2_pools_trade_lbp_post_commit_frontier(
        execution,
        verified,
        dispatch,
    )
    assert report["complete_sources"] == 5
    assert report["active_completed_execution_nodes"] == 38
    assert report["node_dispatch_control_runs_consumed"] == 43
    assert report["next_promotion_node_id"] == "promote:doppler"



def pools_trade_lbp_ledger_approved_receipt():
    return {
        "version": "phase2-pools-trade-lbp-ledger-approved-receipt-v1",
        "ledger_approval_control_run_id": 1301,
        "execution_branch": "phase1/data-acquisition-spike",
        "approval_execution_head_sha": "11" * 20,
        "promotion_proposal_run_id": 1302,
        "promotion_proposal_artifact_digest": "sha256:" + "22" * 32,
        "ledger_commit_run_id": 1303,
        "ledger_commit_artifact_digest": "sha256:" + "33" * 32,
        "canonical_ledger_commit_sha": "44" * 20,
        "base_ledger_sha256": "55" * 32,
        "canonical_coverage_ledger_sha256": "66" * 32,
        "node_dispatch_control_run_ids_consumed": list(range(1400, 1443)),
        "selector_run_id": 1304,
        "planner_run_id": 1305,
        "planner_artifact_digest": "sha256:" + "77" * 32,
        "canonical_complete_source_ids": [
            "pons_v1",
            "pons_v2",
            "pools_fun",
            "pools_trade_instant",
            "pools_trade_lbp",
        ],
        "next_promotion_node_id": "promote:doppler",
        "human_approval_input": "apply_pools_trade_lbp_ledger",
        "human_approval_value": True,
        "canonical_ledger_mutated": True,
        "automatic_acquisition_complete": True,
        "phase2_universe_coverage_complete": False,
    }


def test_pools_trade_lbp_approved_receipt_validates_5_of_14_handoff():
    report = validate_phase2_pools_trade_lbp_ledger_approved_receipt(
        pools_trade_lbp_ledger_approved_receipt()
    )
    assert report["canonical_ledger_commit_sha"] == "44" * 20
    assert report["next_promotion_node_id"] == "promote:doppler"
    assert len(report["node_dispatch_control_run_ids_consumed"]) == 43


def test_pools_trade_lbp_approved_receipt_rejects_wrong_next_source():
    row = pools_trade_lbp_ledger_approved_receipt()
    row["next_promotion_node_id"] = "promote:flap"
    with pytest.raises(ValueError, match="next promotion drift"):
        validate_phase2_pools_trade_lbp_ledger_approved_receipt(row)
