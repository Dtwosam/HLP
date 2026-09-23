"""Validation policy for applying Phase-2 coverage-ledger proposals."""

from __future__ import annotations

from typing import Iterable, Mapping

from hlp.data.phase2_coverage import (
    apply_phase2_source_coverage_report,
    validate_phase2_coverage_ledger,
)
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


PHASE2_COVERAGE_PROMOTION_VERSION = "phase2-source-coverage-promotion-v1"


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower().removeprefix("sha256:")
    if len(text) != 64:
        raise ValueError(f"{label} must be 64 hex chars")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} is not hexadecimal") from exc
    return text


def validate_phase2_coverage_ledger_commit(
    current_ledger: Mapping[str, object],
    proposed_ledger: Mapping[str, object],
    promotion_handoff: Mapping[str, object],
    promotion_validation: Mapping[str, object],
    source_inventory: Iterable[Mapping[str, object]],
    *,
    expected_source_id: str,
    current_ledger_sha256: str,
    proposed_ledger_sha256: str,
) -> dict:
    """Validate one exact stale-safe canonical coverage-ledger advance."""

    handoff = dict(promotion_handoff)
    if str(handoff.get("version") or "") != (
        PHASE2_COVERAGE_PROMOTION_VERSION
    ):
        raise ValueError("promotion handoff version changed")
    source_id = str(expected_source_id)
    if handoff.get("source_id") != source_id:
        raise ValueError("promotion source identity drift")
    if handoff.get("proposal_only") is not True:
        raise ValueError("promotion is not proposal-only")
    if handoff.get("canonical_ledger_mutated") is not False:
        raise ValueError(
            "promotion unexpectedly claims ledger mutation"
        )

    current_sha = _sha256(
        current_ledger_sha256,
        label="current canonical ledger SHA",
    )
    proposed_sha = _sha256(
        proposed_ledger_sha256,
        label="proposed ledger SHA",
    )
    if current_sha != _sha256(
        handoff.get("base_ledger_sha256"),
        label="promotion base_ledger_sha256",
    ):
        raise ValueError(
            "current canonical ledger SHA drift; promotion is stale"
        )
    if proposed_sha != _sha256(
        handoff.get("proposed_ledger_sha256"),
        label="promotion proposed_ledger_sha256",
    ):
        raise ValueError(
            "proposed ledger/handoff SHA linkage drift"
        )

    inventory = [dict(row) for row in source_inventory]
    before = validate_phase2_coverage_ledger(
        dict(current_ledger),
        inventory,
    )
    after = validate_phase2_coverage_ledger(
        dict(proposed_ledger),
        inventory,
    )
    before_ids = set(before["complete_source_ids"])
    after_ids = set(after["complete_source_ids"])
    if not before_ids.issubset(after_ids):
        raise ValueError("proposed ledger regresses complete sources")

    newly_complete = sorted(after_ids - before_ids)
    if newly_complete != [source_id]:
        raise ValueError(
            "proposed ledger must complete exactly the expected "
            f"source; got {newly_complete}"
        )

    handoff_before = sorted(
        str(value)
        for value in handoff.get("complete_source_ids_before") or []
    )
    handoff_after = sorted(
        str(value)
        for value in handoff.get("complete_source_ids_after") or []
    )
    if handoff_before != sorted(before_ids):
        raise ValueError("promotion handoff before-set drift")
    if handoff_after != sorted(after_ids):
        raise ValueError("promotion handoff after-set drift")

    validation_ids = sorted(
        str(value)
        for value in promotion_validation.get(
            "complete_source_ids"
        ) or []
    )
    if validation_ids != sorted(after_ids):
        raise ValueError(
            "promotion validation/ledger complete-set drift"
        )
    if promotion_validation.get(
        "phase2_universe_coverage_complete"
    ) != after["phase2_universe_coverage_complete"]:
        raise ValueError(
            "promotion validation completeness drift"
        )
    if handoff.get(
        "phase2_universe_coverage_complete"
    ) != after["phase2_universe_coverage_complete"]:
        raise ValueError(
            "promotion handoff completeness drift"
        )

    return {
        "source_id": source_id,
        "base_ledger_sha256": current_sha,
        "proposed_ledger_sha256": proposed_sha,
        "complete_source_ids_before": sorted(before_ids),
        "complete_source_ids_after": sorted(after_ids),
        "phase2_universe_coverage_complete": bool(
            after["phase2_universe_coverage_complete"]
        ),
        "newly_complete_source_ids": newly_complete,
        "canonical_ledger_mutation_allowed": True,
    }



PHASE2_POOLS_FUN_PROMOTION_REVIEW_VERSION = (
    "phase2-pools-fun-promotion-review-v1"
)
POOLS_FUN_COVERAGE_WORKFLOW = "phase2-pools-fun-source-coverage.yml"
POOLS_FUN_COVERAGE_ARTIFACT = "phase2-pools-fun-source-coverage"
POOLS_FUN_COVERAGE_REPORT_PATH = "pools-fun-source-coverage-report.json"
SOURCE_COVERAGE_PROMOTION_WORKFLOW = "phase2-source-coverage-promotion.yml"


def _artifact_digest(value: object, *, label: str) -> str:
    text = str(value or "").lower()
    if not text.startswith("sha256:") or len(text) != 71:
        raise ValueError(f"{label} must use sha256:<64 hex chars>")
    _sha256(text, label=label)
    return text


def _positive_run_id(value: object, *, label: str) -> int:
    run_id = int(value or 0)
    if run_id <= 0:
        raise ValueError(f"{label} must be positive")
    return run_id


def build_phase2_pools_fun_promotion_review_handoff(
    current_ledger: Mapping[str, object],
    coverage_report: Mapping[str, object],
    source_inventory: Iterable[Mapping[str, object]],
    *,
    coverage_run_id: int,
    coverage_artifact_digest: str,
    coverage_report_sha256: str,
    planner_run_id: int,
    planner_artifact_digest: str,
    canonical_ledger_sha256: str,
) -> dict:
    """Prepare exact pools.fun promotion inputs without dispatching proposal."""

    inventory = [dict(row) for row in source_inventory]
    before = validate_phase2_coverage_ledger(
        dict(current_ledger),
        inventory,
    )
    if before["complete_source_ids"] != ["pons_v1", "pons_v2"]:
        raise ValueError(
            "pools.fun promotion review requires exact Pons-only ledger"
        )
    if before["phase2_universe_coverage_complete"]:
        raise ValueError(
            "pools.fun promotion review cannot run after universe completion"
        )

    report = dict(coverage_report)
    if report.get("source_id") != "pools_fun":
        raise ValueError("pools.fun promotion review source identity drift")
    if report.get("coverage_status") != "complete":
        raise ValueError(
            "pools.fun promotion review requires complete coverage report"
        )

    proposed, after = apply_phase2_source_coverage_report(
        dict(current_ledger),
        inventory,
        report,
    )
    del proposed
    if after["complete_source_ids"] != [
        "pons_v1",
        "pons_v2",
        "pools_fun",
    ]:
        raise ValueError(
            "pools.fun promotion review does not complete exactly pools_fun"
        )
    if after["phase2_universe_coverage_complete"]:
        raise ValueError(
            "pools.fun promotion review unexpectedly closes Phase 2"
        )

    run_id = _positive_run_id(
        coverage_run_id,
        label="pools.fun coverage run ID",
    )
    artifact_digest = _artifact_digest(
        coverage_artifact_digest,
        label="pools.fun coverage artifact digest",
    )
    report_sha = _sha256(
        coverage_report_sha256,
        label="pools.fun coverage report",
    )
    planner_id = _positive_run_id(
        planner_run_id,
        label="promotion-frontier planner run ID",
    )
    planner_digest = _artifact_digest(
        planner_artifact_digest,
        label="promotion-frontier planner artifact digest",
    )
    ledger_sha = _sha256(
        canonical_ledger_sha256,
        label="canonical Phase-2 coverage ledger",
    )

    generated_inputs = {
        "coverage_run_id": str(run_id),
        "coverage_artifact_name": POOLS_FUN_COVERAGE_ARTIFACT,
        "expected_artifact_digest": artifact_digest,
        "coverage_report_path": POOLS_FUN_COVERAGE_REPORT_PATH,
        "expected_report_sha256": report_sha,
        "expected_source_id": "pools_fun",
    }
    return {
        "version": PHASE2_POOLS_FUN_PROMOTION_REVIEW_VERSION,
        "source_id": "pools_fun",
        "coverage_workflow": POOLS_FUN_COVERAGE_WORKFLOW,
        "coverage_run_id": run_id,
        "coverage_artifact_name": POOLS_FUN_COVERAGE_ARTIFACT,
        "coverage_artifact_digest": artifact_digest,
        "coverage_report_path": POOLS_FUN_COVERAGE_REPORT_PATH,
        "coverage_report_sha256": report_sha,
        "planner_run_id": planner_id,
        "planner_artifact_digest": planner_digest,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "complete_source_ids_before": ["pons_v1", "pons_v2"],
        "complete_source_ids_after_if_promoted": [
            "pons_v1",
            "pons_v2",
            "pools_fun",
        ],
        "promotion_workflow": SOURCE_COVERAGE_PROMOTION_WORKFLOW,
        "promotion_generated_inputs": generated_inputs,
        "promotion_review_required": True,
        "promotion_dispatched": False,
        "proposal_created": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }


def validate_phase2_pools_fun_promotion_review_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate immutable read-only pools.fun promotion review handoff."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE2_POOLS_FUN_PROMOTION_REVIEW_VERSION
    ):
        raise ValueError("pools.fun promotion review version changed")
    control_run_id = _positive_run_id(
        row.get("promotion_review_control_run_id"),
        label="pools.fun promotion review control run ID",
    )
    frontier_run_id = _positive_run_id(
        row.get("promotion_frontier_run_id"),
        label="promotion frontier run ID",
    )
    coverage_run_id = _positive_run_id(
        row.get("coverage_run_id"),
        label="pools.fun promotion coverage run ID",
    )
    planner_run_id = _positive_run_id(
        row.get("planner_run_id"),
        label="pools.fun promotion planner run ID",
    )
    frontier_digest = _artifact_digest(
        row.get("promotion_frontier_artifact_digest"),
        label="promotion frontier artifact digest",
    )
    coverage_digest = _artifact_digest(
        row.get("coverage_artifact_digest"),
        label="pools.fun promotion coverage artifact digest",
    )
    planner_digest = _artifact_digest(
        row.get("planner_artifact_digest"),
        label="pools.fun promotion planner artifact digest",
    )
    report_sha = _sha256(
        row.get("coverage_report_sha256"),
        label="pools.fun promotion report",
    )
    ledger_sha = _sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="pools.fun promotion canonical ledger",
    )

    if row.get("source_id") != "pools_fun":
        raise ValueError("pools.fun promotion review source drift")
    if row.get("coverage_workflow") != POOLS_FUN_COVERAGE_WORKFLOW:
        raise ValueError("pools.fun promotion coverage workflow drift")
    if row.get("coverage_artifact_name") != POOLS_FUN_COVERAGE_ARTIFACT:
        raise ValueError("pools.fun promotion artifact-name drift")
    if row.get("coverage_report_path") != POOLS_FUN_COVERAGE_REPORT_PATH:
        raise ValueError("pools.fun promotion report-path drift")
    if row.get("promotion_workflow") != SOURCE_COVERAGE_PROMOTION_WORKFLOW:
        raise ValueError("pools.fun promotion workflow drift")

    expected_inputs = {
        "coverage_run_id": str(coverage_run_id),
        "coverage_artifact_name": POOLS_FUN_COVERAGE_ARTIFACT,
        "expected_artifact_digest": coverage_digest,
        "coverage_report_path": POOLS_FUN_COVERAGE_REPORT_PATH,
        "expected_report_sha256": report_sha,
        "expected_source_id": "pools_fun",
    }
    if row.get("promotion_generated_inputs") != expected_inputs:
        raise ValueError("pools.fun promotion generated-input drift")
    if row.get("promotion_review_required") is not True:
        raise ValueError("pools.fun promotion lost review requirement")
    for field in (
        "promotion_dispatched",
        "proposal_created",
        "canonical_coverage_ledger_mutated",
        "canonical_ledger_write_authorized",
    ):
        if row.get(field) is not False:
            raise ValueError(
                f"pools.fun promotion review violates read-only field {field}"
            )

    return {
        **row,
        "promotion_review_control_run_id": control_run_id,
        "promotion_frontier_run_id": frontier_run_id,
        "promotion_frontier_artifact_digest": frontier_digest,
        "coverage_run_id": coverage_run_id,
        "coverage_artifact_digest": coverage_digest,
        "coverage_report_sha256": report_sha,
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "promotion_generated_inputs": expected_inputs,
        "promotion_review_required": True,
        "promotion_dispatched": False,
        "proposal_created": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }



PHASE2_POOLS_FUN_PROMOTION_PROPOSAL_VERSION = (
    "phase2-pools-fun-promotion-proposal-v1"
)


def validate_phase2_pools_fun_promotion_proposal_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate proposal-only handoff before explicit canonical-ledger approval."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE2_POOLS_FUN_PROMOTION_PROPOSAL_VERSION
    ):
        raise ValueError("pools.fun promotion proposal receipt version changed")

    control_run_id = _positive_run_id(
        row.get("promotion_proposal_control_run_id"),
        label="pools.fun promotion proposal control run ID",
    )
    review_run_id = _positive_run_id(
        row.get("promotion_review_run_id"),
        label="pools.fun promotion review run ID",
    )
    dispatcher_run_id = _positive_run_id(
        row.get("node_dispatch_control_run_id"),
        label="pools.fun promotion dispatcher control run ID",
    )
    promotion_run_id = _positive_run_id(
        row.get("promotion_run_id"),
        label="pools.fun promotion run ID",
    )
    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError("pools.fun proposal execution branch is empty")
    head_sha = _commit_sha(
        row.get("execution_head_sha"),
        label="pools.fun proposal execution head",
    )

    review_digest = _artifact_digest(
        row.get("promotion_review_artifact_digest"),
        label="pools.fun promotion review artifact digest",
    )
    promotion_digest = _artifact_digest(
        row.get("promotion_artifact_digest"),
        label="pools.fun promotion artifact digest",
    )
    handoff_sha = _sha256(
        row.get("promotion_handoff_sha256"),
        label="pools.fun promotion handoff",
    )
    proposed_sha = _sha256(
        row.get("proposed_ledger_sha256"),
        label="pools.fun proposed ledger",
    )
    base_sha = _sha256(
        row.get("base_ledger_sha256"),
        label="pools.fun proposal base ledger",
    )

    if row.get("source_id") != "pools_fun":
        raise ValueError("pools.fun proposal source identity drift")
    if row.get("promotion_workflow") != SOURCE_COVERAGE_PROMOTION_WORKFLOW:
        raise ValueError("pools.fun proposal workflow identity drift")
    if row.get("proposal_created") is not True:
        raise ValueError("pools.fun proposal receipt lacks proposal proof")
    if row.get("proposal_validated") is not True:
        raise ValueError("pools.fun proposal receipt lacks validation proof")
    if row.get("canonical_coverage_ledger_mutated") is not False:
        raise ValueError("pools.fun proposal unexpectedly mutates ledger")
    if row.get("ledger_commit_authorized") is not False:
        raise ValueError("pools.fun proposal unexpectedly authorizes ledger commit")
    if str(row.get("ledger_commit_approval_input") or "") != (
        "apply_proposed_ledger"
    ):
        raise ValueError("pools.fun proposal ledger approval input drift")
    if row.get("ledger_commit_approval_value_supplied") is not False:
        raise ValueError("pools.fun proposal already supplies ledger approval")

    generated = row.get("ledger_commit_generated_inputs")
    expected_generated = {
        "promotion_run_id": str(promotion_run_id),
        "expected_artifact_digest": promotion_digest,
        "expected_handoff_sha256": handoff_sha,
        "expected_proposed_ledger_sha256": proposed_sha,
        "expected_source_id": "pools_fun",
    }
    if not isinstance(generated, Mapping) or dict(generated) != expected_generated:
        raise ValueError("pools.fun proposal ledger-commit input drift")

    complete_before = [
        str(value) for value in row.get("complete_source_ids_before") or []
    ]
    complete_after = [
        str(value) for value in row.get("complete_source_ids_after") or []
    ]
    if complete_before != ["pons_v1", "pons_v2"]:
        raise ValueError("pools.fun proposal before-set drift")
    if complete_after != ["pons_v1", "pons_v2", "pools_fun"]:
        raise ValueError("pools.fun proposal after-set drift")
    if row.get("phase2_universe_coverage_complete") is not False:
        raise ValueError("pools.fun proposal unexpectedly closes Phase 2")

    return {
        **row,
        "promotion_proposal_control_run_id": control_run_id,
        "promotion_review_run_id": review_run_id,
        "node_dispatch_control_run_id": dispatcher_run_id,
        "promotion_run_id": promotion_run_id,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "promotion_review_artifact_digest": review_digest,
        "promotion_artifact_digest": promotion_digest,
        "promotion_handoff_sha256": handoff_sha,
        "proposed_ledger_sha256": proposed_sha,
        "base_ledger_sha256": base_sha,
        "source_id": "pools_fun",
        "ledger_commit_generated_inputs": expected_generated,
        "ledger_commit_approval_input": "apply_proposed_ledger",
        "ledger_commit_approval_value_supplied": False,
        "proposal_created": True,
        "proposal_validated": True,
        "canonical_coverage_ledger_mutated": False,
        "ledger_commit_authorized": False,
    }



def _commit_sha(value: object, *, label: str) -> str:
    text = str(value or "").lower()
    if len(text) != 40:
        raise ValueError(f"{label} must be a 40-char commit SHA")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} is not hexadecimal") from exc
    return text


def validate_phase2_pools_fun_ledger_commit_receipt(
    receipt: Mapping[str, object],
    *,
    expected_promotion_run_id: int,
    expected_promotion_artifact_digest: str,
    expected_promotion_handoff_sha256: str,
    expected_proposed_ledger_sha256: str,
) -> dict:
    """Validate the exact approved pools.fun canonical-ledger write."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        "phase2-source-coverage-ledger-commit-v1"
    ):
        raise ValueError("pools.fun ledger commit receipt version changed")
    if row.get("source_id") != "pools_fun":
        raise ValueError("pools.fun ledger commit source identity drift")

    promotion_run_id = _positive_run_id(
        row.get("promotion_run_id"),
        label="pools.fun ledger commit promotion run ID",
    )
    if promotion_run_id != int(expected_promotion_run_id):
        raise ValueError("pools.fun ledger commit promotion run drift")
    artifact_name = str(row.get("promotion_artifact_name") or "")
    if artifact_name != "phase2-source-coverage-promotion-pools_fun":
        raise ValueError("pools.fun ledger commit artifact-name drift")
    artifact_digest = _artifact_digest(
        row.get("promotion_artifact_digest"),
        label="pools.fun ledger commit promotion artifact digest",
    )
    if artifact_digest != _artifact_digest(
        expected_promotion_artifact_digest,
        label="expected pools.fun promotion artifact digest",
    ):
        raise ValueError("pools.fun ledger commit promotion artifact drift")

    handoff_sha = _sha256(
        row.get("promotion_handoff_sha256"),
        label="pools.fun ledger commit promotion handoff",
    )
    if handoff_sha != _sha256(
        expected_promotion_handoff_sha256,
        label="expected pools.fun promotion handoff",
    ):
        raise ValueError("pools.fun ledger commit promotion handoff drift")
    proposed_sha = _sha256(
        row.get("proposed_ledger_sha256"),
        label="pools.fun ledger commit proposed ledger",
    )
    if proposed_sha != _sha256(
        expected_proposed_ledger_sha256,
        label="expected pools.fun proposed ledger",
    ):
        raise ValueError("pools.fun ledger commit proposed-ledger drift")
    base_sha = _sha256(
        row.get("base_ledger_sha256"),
        label="pools.fun ledger commit base ledger",
    )

    before = [
        str(value) for value in row.get("complete_source_ids_before") or []
    ]
    after = [
        str(value) for value in row.get("complete_source_ids_after") or []
    ]
    if before != ["pons_v1", "pons_v2"]:
        raise ValueError("pools.fun ledger commit before-set drift")
    if after != ["pons_v1", "pons_v2", "pools_fun"]:
        raise ValueError("pools.fun ledger commit after-set drift")
    if row.get("phase2_universe_coverage_complete") is not False:
        raise ValueError("pools.fun ledger commit unexpectedly closes Phase 2")
    commit_sha = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="pools.fun canonical ledger commit",
    )
    if row.get("explicit_approval") is not True:
        raise ValueError("pools.fun ledger commit lacks explicit approval")
    if row.get("canonical_ledger_mutated") is not True:
        raise ValueError("pools.fun ledger commit lacks mutation proof")

    return {
        **row,
        "source_id": "pools_fun",
        "promotion_run_id": promotion_run_id,
        "promotion_artifact_name": artifact_name,
        "promotion_artifact_digest": artifact_digest,
        "promotion_handoff_sha256": handoff_sha,
        "base_ledger_sha256": base_sha,
        "proposed_ledger_sha256": proposed_sha,
        "complete_source_ids_before": before,
        "complete_source_ids_after": after,
        "canonical_ledger_commit_sha": commit_sha,
        "explicit_approval": True,
        "canonical_ledger_mutated": True,
    }


def validate_phase2_pools_fun_post_commit_frontier(
    execution_plan: Mapping[str, object],
    verified_receipts: Mapping[str, object],
    dispatch_plan: Mapping[str, object],
) -> dict:
    """Freeze the exact 3/14 planner boundary after pools.fun is canonical."""

    execution = dict(execution_plan)
    verified = dict(verified_receipts)
    dispatch = dict(dispatch_plan)

    expected_complete = ["pons_v1", "pons_v2", "pools_fun"]
    if execution.get("canonical_complete_source_ids") != expected_complete:
        raise ValueError("pools.fun post-commit canonical source set drift")
    if int(execution.get("complete_sources", -1)) != 3:
        raise ValueError("pools.fun post-commit source count drift")
    if int(execution.get("incomplete_sources", -1)) != 11:
        raise ValueError("pools.fun post-commit incomplete count drift")
    if execution.get("phase2_universe_coverage_complete") is not False:
        raise ValueError("pools.fun post-commit unexpectedly closes Phase 2")

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
    expected_active_completed = pre_frontier - {"coverage:pools_fun"}
    completed = execution.get("completed_node_ids")
    if not isinstance(completed, list) or set(completed) != expected_active_completed:
        raise ValueError("pools.fun post-commit active completion drift")

    ignored = execution.get("ignored_completed_node_ids")
    if not isinstance(ignored, list) or set(ignored) != {
        "coverage:pools_fun",
        "promote:pools_fun",
    }:
        raise ValueError("pools.fun post-commit ignored-completion drift")

    ready = execution.get("ready_to_dispatch_node_ids")
    if ready != ["promote:pools_trade_instant"]:
        raise ValueError("pools.fun post-commit next promotion drift")
    if execution.get("awaiting_explicit_approval_node_ids") != []:
        raise ValueError("pools.fun post-commit has unexpected approval nodes")
    if execution.get("ledger_commit_approval_node_ids") != []:
        raise ValueError("pools.fun post-commit has unexpected ledger approval")
    if execution.get("manual_ledger_commit_node_ids") != []:
        raise ValueError("pools.fun post-commit has unexpected manual commits")

    verified_completed = verified.get("completed_node_ids")
    expected_verified = pre_frontier | {"promote:pools_fun"}
    if (
        not isinstance(verified_completed, list)
        or set(verified_completed) != expected_verified
    ):
        raise ValueError("pools.fun post-commit verified completion drift")
    control_ids = verified.get("node_dispatch_run_ids_consumed")
    if (
        not isinstance(control_ids, list)
        or len(control_ids) != 41
        or len(set(int(value) for value in control_ids)) != 41
    ):
        raise ValueError(
            "pools.fun post-commit requires exactly 41 dispatcher receipts"
        )
    if verified.get("all_runs_current_or_ledger_only_ancestors") is not True:
        raise ValueError("pools.fun post-commit lacks lineage proof")

    rows = dispatch.get("nodes")
    if not isinstance(rows, list) or len(rows) != 1:
        raise ValueError("pools.fun post-commit dispatch row count drift")
    row = dict(rows[0])
    if row.get("node_id") != "promote:pools_trade_instant":
        raise ValueError("pools.fun post-commit dispatch node drift")
    if row.get("workflow") != SOURCE_COVERAGE_PROMOTION_WORKFLOW:
        raise ValueError("pools.fun post-commit promotion workflow drift")
    if row.get("status") != "ready_to_dispatch":
        raise ValueError("pools.trade Instant promotion is not ready")
    if set(dict(row.get("run_id_inputs") or {})) != {"coverage_run_id"}:
        raise ValueError("pools.trade Instant promotion run binding drift")
    expected_manual = sorted([
        "coverage_artifact_name",
        "coverage_report_path",
        "expected_artifact_digest",
        "expected_report_sha256",
        "expected_source_id",
    ])
    actual_manual = sorted(
        str(value) for value in row.get("remaining_manual_inputs") or []
    )
    if actual_manual != expected_manual:
        raise ValueError("pools.trade Instant promotion manual-input drift")

    return {
        "version": "phase2-pools-fun-post-commit-frontier-v1",
        "canonical_complete_source_ids": expected_complete,
        "complete_sources": 3,
        "incomplete_sources": 11,
        "active_completed_execution_nodes": len(expected_active_completed),
        "ignored_completed_node_ids": [
            "coverage:pools_fun",
            "promote:pools_fun",
        ],
        "node_dispatch_control_runs_consumed": len(control_ids),
        "next_promotion_node_id": "promote:pools_trade_instant",
        "next_promotion_manual_inputs": actual_manual,
        "automatic_acquisition_complete": True,
        "canonical_ledger_advanced": True,
        "phase2_universe_coverage_complete": False,
    }



PHASE2_POOLS_TRADE_INSTANT_PROMOTION_REVIEW_VERSION = (
    "phase2-pools-trade-instant-promotion-review-v1"
)
POOLS_TRADE_INSTANT_COVERAGE_WORKFLOW = (
    "phase2-pools-trade-instant-source-coverage.yml"
)
POOLS_TRADE_INSTANT_COVERAGE_ARTIFACT = (
    "phase2-pools-trade-instant-source-coverage"
)
POOLS_TRADE_INSTANT_COVERAGE_REPORT_PATH = (
    "pools-trade-instant-source-coverage-report.json"
)


def build_phase2_pools_trade_instant_promotion_review_handoff(
    current_ledger: Mapping[str, object],
    coverage_report: Mapping[str, object],
    source_inventory: Iterable[Mapping[str, object]],
    *,
    coverage_run_id: int,
    coverage_artifact_digest: str,
    coverage_report_sha256: str,
    planner_run_id: int,
    planner_artifact_digest: str,
    canonical_ledger_sha256: str,
) -> dict:
    """Prepare exact pools.trade Instant promotion inputs at 3/14."""

    inventory = [dict(row) for row in source_inventory]
    before = validate_phase2_coverage_ledger(
        dict(current_ledger),
        inventory,
    )
    if before["complete_source_ids"] != [
        "pons_v1",
        "pons_v2",
        "pools_fun",
    ]:
        raise ValueError(
            "pools.trade Instant review requires exact 3/14 pools.fun ledger"
        )
    report = dict(coverage_report)
    if report.get("source_id") != "pools_trade_instant":
        raise ValueError("pools.trade Instant review source identity drift")
    if report.get("coverage_status") != "complete":
        raise ValueError(
            "pools.trade Instant review requires complete coverage report"
        )

    _, after = apply_phase2_source_coverage_report(
        dict(current_ledger),
        inventory,
        report,
    )
    expected_after = [
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
    ]
    if after["complete_source_ids"] != expected_after:
        raise ValueError(
            "pools.trade Instant review does not complete exactly next source"
        )
    if after["phase2_universe_coverage_complete"]:
        raise ValueError(
            "pools.trade Instant review unexpectedly closes Phase 2"
        )

    run_id = _positive_run_id(
        coverage_run_id,
        label="pools.trade Instant coverage run ID",
    )
    artifact_digest = _artifact_digest(
        coverage_artifact_digest,
        label="pools.trade Instant coverage artifact digest",
    )
    report_sha = _sha256(
        coverage_report_sha256,
        label="pools.trade Instant coverage report",
    )
    planner_id = _positive_run_id(
        planner_run_id,
        label="pools.trade Instant promotion planner run ID",
    )
    planner_digest = _artifact_digest(
        planner_artifact_digest,
        label="pools.trade Instant planner artifact digest",
    )
    ledger_sha = _sha256(
        canonical_ledger_sha256,
        label="pools.trade Instant canonical ledger",
    )

    generated_inputs = {
        "coverage_run_id": str(run_id),
        "coverage_artifact_name": POOLS_TRADE_INSTANT_COVERAGE_ARTIFACT,
        "expected_artifact_digest": artifact_digest,
        "coverage_report_path": POOLS_TRADE_INSTANT_COVERAGE_REPORT_PATH,
        "expected_report_sha256": report_sha,
        "expected_source_id": "pools_trade_instant",
    }
    return {
        "version": PHASE2_POOLS_TRADE_INSTANT_PROMOTION_REVIEW_VERSION,
        "source_id": "pools_trade_instant",
        "coverage_workflow": POOLS_TRADE_INSTANT_COVERAGE_WORKFLOW,
        "coverage_run_id": run_id,
        "coverage_artifact_name": POOLS_TRADE_INSTANT_COVERAGE_ARTIFACT,
        "coverage_artifact_digest": artifact_digest,
        "coverage_report_path": POOLS_TRADE_INSTANT_COVERAGE_REPORT_PATH,
        "coverage_report_sha256": report_sha,
        "planner_run_id": planner_id,
        "planner_artifact_digest": planner_digest,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "complete_source_ids_before": [
            "pons_v1",
            "pons_v2",
            "pools_fun",
        ],
        "complete_source_ids_after_if_promoted": expected_after,
        "promotion_workflow": SOURCE_COVERAGE_PROMOTION_WORKFLOW,
        "promotion_generated_inputs": generated_inputs,
        "promotion_review_required": True,
        "promotion_dispatched": False,
        "proposal_created": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }


def validate_phase2_pools_trade_instant_promotion_review_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate the immutable 3/14 pools.trade Instant review handoff."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE2_POOLS_TRADE_INSTANT_PROMOTION_REVIEW_VERSION
    ):
        raise ValueError(
            "pools.trade Instant promotion review version changed"
        )
    control_run_id = _positive_run_id(
        row.get("promotion_review_control_run_id"),
        label="pools.trade Instant review control run ID",
    )
    prior_run_id = _positive_run_id(
        row.get("pools_fun_ledger_approval_run_id"),
        label="pools.fun ledger approval run ID",
    )
    coverage_run_id = _positive_run_id(
        row.get("coverage_run_id"),
        label="pools.trade Instant coverage run ID",
    )
    planner_run_id = _positive_run_id(
        row.get("planner_run_id"),
        label="pools.trade Instant planner run ID",
    )
    prior_digest = _artifact_digest(
        row.get("pools_fun_ledger_approval_artifact_digest"),
        label="pools.fun ledger approval artifact digest",
    )
    coverage_digest = _artifact_digest(
        row.get("coverage_artifact_digest"),
        label="pools.trade Instant coverage artifact digest",
    )
    planner_digest = _artifact_digest(
        row.get("planner_artifact_digest"),
        label="pools.trade Instant planner artifact digest",
    )
    report_sha = _sha256(
        row.get("coverage_report_sha256"),
        label="pools.trade Instant coverage report",
    )
    ledger_sha = _sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="pools.trade Instant canonical ledger",
    )
    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError(
            "pools.trade Instant review execution branch is empty"
        )
    head_sha = _commit_sha(
        row.get("execution_head_sha"),
        label="pools.trade Instant review execution head",
    )

    if row.get("source_id") != "pools_trade_instant":
        raise ValueError("pools.trade Instant review source drift")
    if row.get("coverage_workflow") != POOLS_TRADE_INSTANT_COVERAGE_WORKFLOW:
        raise ValueError("pools.trade Instant coverage workflow drift")
    if row.get("coverage_artifact_name") != (
        POOLS_TRADE_INSTANT_COVERAGE_ARTIFACT
    ):
        raise ValueError("pools.trade Instant artifact-name drift")
    if row.get("coverage_report_path") != (
        POOLS_TRADE_INSTANT_COVERAGE_REPORT_PATH
    ):
        raise ValueError("pools.trade Instant report-path drift")
    if row.get("promotion_workflow") != SOURCE_COVERAGE_PROMOTION_WORKFLOW:
        raise ValueError("pools.trade Instant promotion workflow drift")

    expected_inputs = {
        "coverage_run_id": str(coverage_run_id),
        "coverage_artifact_name": POOLS_TRADE_INSTANT_COVERAGE_ARTIFACT,
        "expected_artifact_digest": coverage_digest,
        "coverage_report_path": POOLS_TRADE_INSTANT_COVERAGE_REPORT_PATH,
        "expected_report_sha256": report_sha,
        "expected_source_id": "pools_trade_instant",
    }
    if row.get("promotion_generated_inputs") != expected_inputs:
        raise ValueError(
            "pools.trade Instant promotion generated-input drift"
        )
    if row.get("promotion_review_required") is not True:
        raise ValueError(
            "pools.trade Instant promotion lost review requirement"
        )
    for field in (
        "promotion_dispatched",
        "proposal_created",
        "canonical_coverage_ledger_mutated",
        "canonical_ledger_write_authorized",
    ):
        if row.get(field) is not False:
            raise ValueError(
                "pools.trade Instant review violates read-only field "
                f"{field}"
            )

    return {
        **row,
        "promotion_review_control_run_id": control_run_id,
        "pools_fun_ledger_approval_run_id": prior_run_id,
        "pools_fun_ledger_approval_artifact_digest": prior_digest,
        "coverage_run_id": coverage_run_id,
        "coverage_artifact_digest": coverage_digest,
        "coverage_report_sha256": report_sha,
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "promotion_generated_inputs": expected_inputs,
        "promotion_review_required": True,
        "promotion_dispatched": False,
        "proposal_created": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }



def validate_phase2_pools_fun_ledger_approved_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate the immutable 3/14 handoff after approved pools.fun commit."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        "phase2-pools-fun-ledger-approved-receipt-v1"
    ):
        raise ValueError("pools.fun approved-ledger receipt version changed")

    control_run_id = _positive_run_id(
        row.get("ledger_approval_control_run_id"),
        label="pools.fun ledger approval control run ID",
    )
    proposal_run_id = _positive_run_id(
        row.get("promotion_proposal_run_id"),
        label="pools.fun promotion proposal run ID",
    )
    ledger_run_id = _positive_run_id(
        row.get("ledger_commit_run_id"),
        label="pools.fun ledger commit run ID",
    )
    selector_run_id = _positive_run_id(
        row.get("selector_run_id"),
        label="pools.fun approved selector run ID",
    )
    planner_run_id = _positive_run_id(
        row.get("planner_run_id"),
        label="pools.fun post-commit planner run ID",
    )

    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError("pools.fun approved-ledger branch is empty")
    approval_head = _commit_sha(
        row.get("approval_execution_head_sha"),
        label="pools.fun ledger approval execution head",
    )
    proposal_digest = _artifact_digest(
        row.get("promotion_proposal_artifact_digest"),
        label="pools.fun proposal artifact digest",
    )
    ledger_artifact_digest = _artifact_digest(
        row.get("ledger_commit_artifact_digest"),
        label="pools.fun ledger commit artifact digest",
    )
    commit_sha = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="pools.fun canonical ledger commit",
    )
    base_sha = _sha256(
        row.get("base_ledger_sha256"),
        label="pools.fun approved base ledger",
    )
    canonical_sha = _sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="pools.fun approved canonical ledger",
    )
    planner_digest = _artifact_digest(
        row.get("planner_artifact_digest"),
        label="pools.fun post-commit planner artifact digest",
    )

    controls_raw = row.get("node_dispatch_control_run_ids_consumed")
    if not isinstance(controls_raw, list):
        raise ValueError("pools.fun approved control-run list is missing")
    controls = [int(value) for value in controls_raw]
    if (
        len(controls) != 41
        or len(set(controls)) != 41
        or min(controls) <= 0
    ):
        raise ValueError(
            "pools.fun approved handoff requires exactly 41 control runs"
        )
    if row.get("canonical_complete_source_ids") != [
        "pons_v1",
        "pons_v2",
        "pools_fun",
    ]:
        raise ValueError("pools.fun approved canonical source set drift")
    if row.get("next_promotion_node_id") != "promote:pools_trade_instant":
        raise ValueError("pools.fun approved next promotion drift")
    if row.get("human_approval_input") != "apply_pools_fun_ledger":
        raise ValueError("pools.fun approved human-input identity drift")
    if row.get("human_approval_value") is not True:
        raise ValueError("pools.fun approved receipt lacks affirmative approval")
    if row.get("canonical_ledger_mutated") is not True:
        raise ValueError("pools.fun approved receipt lacks ledger mutation")
    if row.get("automatic_acquisition_complete") is not True:
        raise ValueError("pools.fun approved receipt lost acquisition proof")
    if row.get("phase2_universe_coverage_complete") is not False:
        raise ValueError("pools.fun approved receipt unexpectedly closes Phase 2")

    return {
        **row,
        "ledger_approval_control_run_id": control_run_id,
        "execution_branch": branch,
        "approval_execution_head_sha": approval_head,
        "promotion_proposal_run_id": proposal_run_id,
        "promotion_proposal_artifact_digest": proposal_digest,
        "ledger_commit_run_id": ledger_run_id,
        "ledger_commit_artifact_digest": ledger_artifact_digest,
        "canonical_ledger_commit_sha": commit_sha,
        "base_ledger_sha256": base_sha,
        "canonical_coverage_ledger_sha256": canonical_sha,
        "node_dispatch_control_run_ids_consumed": sorted(controls),
        "selector_run_id": selector_run_id,
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
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



PHASE2_POOLS_TRADE_INSTANT_PROMOTION_PROPOSAL_VERSION = (
    "phase2-pools-trade-instant-promotion-proposal-v1"
)


def validate_phase2_pools_trade_instant_promotion_proposal_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate pools.trade Instant proposal before ledger approval."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE2_POOLS_TRADE_INSTANT_PROMOTION_PROPOSAL_VERSION
    ):
        raise ValueError(
            "pools.trade Instant promotion proposal receipt version changed"
        )
    control_run_id = _positive_run_id(
        row.get("promotion_proposal_control_run_id"),
        label="pools.trade Instant proposal control run ID",
    )
    review_run_id = _positive_run_id(
        row.get("promotion_review_run_id"),
        label="pools.trade Instant review run ID",
    )
    dispatcher_run_id = _positive_run_id(
        row.get("node_dispatch_control_run_id"),
        label="pools.trade Instant promotion dispatcher run ID",
    )
    promotion_run_id = _positive_run_id(
        row.get("promotion_run_id"),
        label="pools.trade Instant promotion run ID",
    )
    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError(
            "pools.trade Instant proposal execution branch is empty"
        )
    head_sha = _commit_sha(
        row.get("execution_head_sha"),
        label="pools.trade Instant proposal execution head",
    )
    review_digest = _artifact_digest(
        row.get("promotion_review_artifact_digest"),
        label="pools.trade Instant review artifact digest",
    )
    promotion_digest = _artifact_digest(
        row.get("promotion_artifact_digest"),
        label="pools.trade Instant promotion artifact digest",
    )
    handoff_sha = _sha256(
        row.get("promotion_handoff_sha256"),
        label="pools.trade Instant promotion handoff",
    )
    proposed_sha = _sha256(
        row.get("proposed_ledger_sha256"),
        label="pools.trade Instant proposed ledger",
    )
    base_sha = _sha256(
        row.get("base_ledger_sha256"),
        label="pools.trade Instant proposal base ledger",
    )

    if row.get("source_id") != "pools_trade_instant":
        raise ValueError("pools.trade Instant proposal source identity drift")
    if row.get("promotion_workflow") != SOURCE_COVERAGE_PROMOTION_WORKFLOW:
        raise ValueError("pools.trade Instant proposal workflow identity drift")
    if row.get("complete_source_ids_before") != [
        "pons_v1",
        "pons_v2",
        "pools_fun",
    ]:
        raise ValueError("pools.trade Instant proposal before-set drift")
    if row.get("complete_source_ids_after") != [
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
    ]:
        raise ValueError("pools.trade Instant proposal after-set drift")
    if row.get("phase2_universe_coverage_complete") is not False:
        raise ValueError(
            "pools.trade Instant proposal unexpectedly closes Phase 2"
        )
    if row.get("proposal_created") is not True:
        raise ValueError("pools.trade Instant proposal lacks proposal proof")
    if row.get("proposal_validated") is not True:
        raise ValueError("pools.trade Instant proposal lacks validation proof")
    if row.get("canonical_coverage_ledger_mutated") is not False:
        raise ValueError(
            "pools.trade Instant proposal unexpectedly mutates ledger"
        )
    if row.get("ledger_commit_authorized") is not False:
        raise ValueError(
            "pools.trade Instant proposal unexpectedly authorizes ledger commit"
        )
    if row.get("ledger_commit_approval_input") != "apply_proposed_ledger":
        raise ValueError(
            "pools.trade Instant proposal ledger approval input drift"
        )
    if row.get("ledger_commit_approval_value_supplied") is not False:
        raise ValueError(
            "pools.trade Instant proposal already supplies ledger approval"
        )

    expected_generated = {
        "promotion_run_id": str(promotion_run_id),
        "expected_artifact_digest": promotion_digest,
        "expected_handoff_sha256": handoff_sha,
        "expected_proposed_ledger_sha256": proposed_sha,
        "expected_source_id": "pools_trade_instant",
    }
    if row.get("ledger_commit_generated_inputs") != expected_generated:
        raise ValueError(
            "pools.trade Instant proposal ledger-commit input drift"
        )

    return {
        **row,
        "promotion_proposal_control_run_id": control_run_id,
        "promotion_review_run_id": review_run_id,
        "node_dispatch_control_run_id": dispatcher_run_id,
        "promotion_run_id": promotion_run_id,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "promotion_review_artifact_digest": review_digest,
        "promotion_artifact_digest": promotion_digest,
        "promotion_handoff_sha256": handoff_sha,
        "proposed_ledger_sha256": proposed_sha,
        "base_ledger_sha256": base_sha,
        "source_id": "pools_trade_instant",
        "ledger_commit_generated_inputs": expected_generated,
        "ledger_commit_approval_input": "apply_proposed_ledger",
        "ledger_commit_approval_value_supplied": False,
        "proposal_created": True,
        "proposal_validated": True,
        "canonical_coverage_ledger_mutated": False,
        "ledger_commit_authorized": False,
    }



def validate_phase2_pools_trade_instant_ledger_commit_receipt(
    receipt: Mapping[str, object],
    *,
    expected_promotion_run_id: int,
    expected_promotion_artifact_digest: str,
    expected_promotion_handoff_sha256: str,
    expected_proposed_ledger_sha256: str,
) -> dict:
    """Validate approved pools.trade Instant canonical-ledger write."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        "phase2-source-coverage-ledger-commit-v1"
    ):
        raise ValueError(
            "pools.trade Instant ledger commit receipt version changed"
        )
    if row.get("source_id") != "pools_trade_instant":
        raise ValueError(
            "pools.trade Instant ledger commit source identity drift"
        )
    promotion_run_id = _positive_run_id(
        row.get("promotion_run_id"),
        label="pools.trade Instant ledger promotion run ID",
    )
    if promotion_run_id != int(expected_promotion_run_id):
        raise ValueError(
            "pools.trade Instant ledger commit promotion run drift"
        )
    if row.get("promotion_artifact_name") != (
        "phase2-source-coverage-promotion-pools_trade_instant"
    ):
        raise ValueError(
            "pools.trade Instant ledger commit artifact-name drift"
        )
    artifact_digest = _artifact_digest(
        row.get("promotion_artifact_digest"),
        label="pools.trade Instant promotion artifact digest",
    )
    if artifact_digest != _artifact_digest(
        expected_promotion_artifact_digest,
        label="expected pools.trade Instant promotion artifact digest",
    ):
        raise ValueError(
            "pools.trade Instant ledger commit promotion artifact drift"
        )
    handoff_sha = _sha256(
        row.get("promotion_handoff_sha256"),
        label="pools.trade Instant promotion handoff",
    )
    if handoff_sha != _sha256(
        expected_promotion_handoff_sha256,
        label="expected pools.trade Instant promotion handoff",
    ):
        raise ValueError(
            "pools.trade Instant ledger commit promotion handoff drift"
        )
    proposed_sha = _sha256(
        row.get("proposed_ledger_sha256"),
        label="pools.trade Instant proposed ledger",
    )
    if proposed_sha != _sha256(
        expected_proposed_ledger_sha256,
        label="expected pools.trade Instant proposed ledger",
    ):
        raise ValueError(
            "pools.trade Instant ledger commit proposed-ledger drift"
        )
    base_sha = _sha256(
        row.get("base_ledger_sha256"),
        label="pools.trade Instant base ledger",
    )
    if row.get("complete_source_ids_before") != [
        "pons_v1",
        "pons_v2",
        "pools_fun",
    ]:
        raise ValueError(
            "pools.trade Instant ledger commit before-set drift"
        )
    if row.get("complete_source_ids_after") != [
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
    ]:
        raise ValueError(
            "pools.trade Instant ledger commit after-set drift"
        )
    if row.get("phase2_universe_coverage_complete") is not False:
        raise ValueError(
            "pools.trade Instant ledger commit unexpectedly closes Phase 2"
        )
    commit_sha = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="pools.trade Instant canonical ledger commit",
    )
    if row.get("explicit_approval") is not True:
        raise ValueError(
            "pools.trade Instant ledger commit lacks explicit approval"
        )
    if row.get("canonical_ledger_mutated") is not True:
        raise ValueError(
            "pools.trade Instant ledger commit lacks mutation proof"
        )
    return {
        **row,
        "promotion_run_id": promotion_run_id,
        "promotion_artifact_digest": artifact_digest,
        "promotion_handoff_sha256": handoff_sha,
        "base_ledger_sha256": base_sha,
        "proposed_ledger_sha256": proposed_sha,
        "canonical_ledger_commit_sha": commit_sha,
        "explicit_approval": True,
        "canonical_ledger_mutated": True,
    }


def validate_phase2_pools_trade_instant_post_commit_frontier(
    execution_plan: Mapping[str, object],
    verified_receipts: Mapping[str, object],
    dispatch_plan: Mapping[str, object],
) -> dict:
    """Freeze exact 4/14 frontier after pools.trade Instant is canonical."""

    execution = dict(execution_plan)
    verified = dict(verified_receipts)
    dispatch = dict(dispatch_plan)
    expected_complete = [
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
    ]
    if execution.get("canonical_complete_source_ids") != expected_complete:
        raise ValueError(
            "pools.trade Instant post-commit canonical source set drift"
        )
    if int(execution.get("complete_sources", -1)) != 4:
        raise ValueError(
            "pools.trade Instant post-commit source count drift"
        )
    if int(execution.get("incomplete_sources", -1)) != 10:
        raise ValueError(
            "pools.trade Instant post-commit incomplete count drift"
        )
    if execution.get("phase2_universe_coverage_complete") is not False:
        raise ValueError(
            "pools.trade Instant post-commit unexpectedly closes Phase 2"
        )

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
    removed = {
        "coverage:pools_fun",
        "promote:pools_fun",
        "coverage:pools_trade_instant",
        "promote:pools_trade_instant",
    }
    expected_active = pre_frontier - {
        "coverage:pools_fun",
        "coverage:pools_trade_instant",
    }
    if set(execution.get("completed_node_ids") or []) != expected_active:
        raise ValueError(
            "pools.trade Instant post-commit active completion drift"
        )
    if set(execution.get("ignored_completed_node_ids") or []) != removed:
        raise ValueError(
            "pools.trade Instant post-commit ignored-completion drift"
        )
    if execution.get("ready_to_dispatch_node_ids") != [
        "promote:pools_trade_lbp"
    ]:
        raise ValueError(
            "pools.trade Instant post-commit next promotion drift"
        )
    if execution.get("awaiting_explicit_approval_node_ids") != []:
        raise ValueError(
            "pools.trade Instant post-commit unexpected approval nodes"
        )
    if execution.get("ledger_commit_approval_node_ids") != []:
        raise ValueError(
            "pools.trade Instant post-commit unexpected ledger approval"
        )

    expected_verified = pre_frontier | {
        "promote:pools_fun",
        "promote:pools_trade_instant",
    }
    if set(verified.get("completed_node_ids") or []) != expected_verified:
        raise ValueError(
            "pools.trade Instant post-commit verified completion drift"
        )
    controls = verified.get("node_dispatch_run_ids_consumed")
    if (
        not isinstance(controls, list)
        or len(controls) != 42
        or len(set(int(value) for value in controls)) != 42
    ):
        raise ValueError(
            "pools.trade Instant post-commit requires exactly 42 "
            "dispatcher receipts"
        )
    if verified.get("all_runs_current_or_ledger_only_ancestors") is not True:
        raise ValueError(
            "pools.trade Instant post-commit lacks lineage proof"
        )

    rows = dispatch.get("nodes")
    if not isinstance(rows, list) or len(rows) != 1:
        raise ValueError(
            "pools.trade Instant post-commit dispatch row count drift"
        )
    row = dict(rows[0])
    if row.get("node_id") != "promote:pools_trade_lbp":
        raise ValueError(
            "pools.trade Instant post-commit dispatch node drift"
        )
    if row.get("workflow") != SOURCE_COVERAGE_PROMOTION_WORKFLOW:
        raise ValueError(
            "pools.trade Instant post-commit promotion workflow drift"
        )
    if set(dict(row.get("run_id_inputs") or {})) != {"coverage_run_id"}:
        raise ValueError(
            "pools.trade LBP promotion coverage-run binding drift"
        )
    expected_manual = sorted([
        "coverage_artifact_name",
        "coverage_report_path",
        "expected_artifact_digest",
        "expected_report_sha256",
        "expected_source_id",
    ])
    actual_manual = sorted(
        str(value) for value in row.get("remaining_manual_inputs") or []
    )
    if actual_manual != expected_manual:
        raise ValueError(
            "pools.trade LBP promotion manual-input drift"
        )

    return {
        "version": "phase2-pools-trade-instant-post-commit-frontier-v1",
        "canonical_complete_source_ids": expected_complete,
        "complete_sources": 4,
        "incomplete_sources": 10,
        "active_completed_execution_nodes": len(expected_active),
        "ignored_completed_node_ids": sorted(removed),
        "node_dispatch_control_runs_consumed": len(controls),
        "next_promotion_node_id": "promote:pools_trade_lbp",
        "next_promotion_manual_inputs": actual_manual,
        "automatic_acquisition_complete": True,
        "canonical_ledger_advanced": True,
        "phase2_universe_coverage_complete": False,
    }



def validate_phase2_pools_trade_instant_ledger_approved_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate immutable 4/14 handoff after pools.trade Instant commit."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        "phase2-pools-trade-instant-ledger-approved-receipt-v1"
    ):
        raise ValueError(
            "pools.trade Instant approved-ledger receipt version changed"
        )
    control_run_id = _positive_run_id(
        row.get("ledger_approval_control_run_id"),
        label="pools.trade Instant ledger approval control run ID",
    )
    proposal_run_id = _positive_run_id(
        row.get("promotion_proposal_run_id"),
        label="pools.trade Instant proposal run ID",
    )
    ledger_run_id = _positive_run_id(
        row.get("ledger_commit_run_id"),
        label="pools.trade Instant ledger commit run ID",
    )
    selector_run_id = _positive_run_id(
        row.get("selector_run_id"),
        label="pools.trade Instant selector run ID",
    )
    planner_run_id = _positive_run_id(
        row.get("planner_run_id"),
        label="pools.trade Instant post-commit planner run ID",
    )
    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError(
            "pools.trade Instant approved-ledger branch is empty"
        )
    approval_head = _commit_sha(
        row.get("approval_execution_head_sha"),
        label="pools.trade Instant approval execution head",
    )
    proposal_digest = _artifact_digest(
        row.get("promotion_proposal_artifact_digest"),
        label="pools.trade Instant proposal artifact digest",
    )
    ledger_digest = _artifact_digest(
        row.get("ledger_commit_artifact_digest"),
        label="pools.trade Instant ledger commit artifact digest",
    )
    commit_sha = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="pools.trade Instant canonical ledger commit",
    )
    base_sha = _sha256(
        row.get("base_ledger_sha256"),
        label="pools.trade Instant approved base ledger",
    )
    canonical_sha = _sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="pools.trade Instant approved canonical ledger",
    )
    planner_digest = _artifact_digest(
        row.get("planner_artifact_digest"),
        label="pools.trade Instant post-commit planner artifact digest",
    )
    controls_raw = row.get("node_dispatch_control_run_ids_consumed")
    if not isinstance(controls_raw, list):
        raise ValueError(
            "pools.trade Instant approved control-run list is missing"
        )
    controls = [int(value) for value in controls_raw]
    if (
        len(controls) != 42
        or len(set(controls)) != 42
        or min(controls) <= 0
    ):
        raise ValueError(
            "pools.trade Instant approved handoff requires exactly 42 "
            "control runs"
        )
    expected_complete = [
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
    ]
    if row.get("canonical_complete_source_ids") != expected_complete:
        raise ValueError(
            "pools.trade Instant approved canonical source set drift"
        )
    if row.get("next_promotion_node_id") != "promote:pools_trade_lbp":
        raise ValueError(
            "pools.trade Instant approved next promotion drift"
        )
    if row.get("human_approval_input") != (
        "apply_pools_trade_instant_ledger"
    ):
        raise ValueError(
            "pools.trade Instant approved human-input identity drift"
        )
    if row.get("human_approval_value") is not True:
        raise ValueError(
            "pools.trade Instant approved receipt lacks affirmative approval"
        )
    if row.get("canonical_ledger_mutated") is not True:
        raise ValueError(
            "pools.trade Instant approved receipt lacks ledger mutation"
        )
    if row.get("automatic_acquisition_complete") is not True:
        raise ValueError(
            "pools.trade Instant approved receipt lost acquisition proof"
        )
    if row.get("phase2_universe_coverage_complete") is not False:
        raise ValueError(
            "pools.trade Instant approved receipt unexpectedly closes Phase 2"
        )
    return {
        **row,
        "ledger_approval_control_run_id": control_run_id,
        "execution_branch": branch,
        "approval_execution_head_sha": approval_head,
        "promotion_proposal_run_id": proposal_run_id,
        "promotion_proposal_artifact_digest": proposal_digest,
        "ledger_commit_run_id": ledger_run_id,
        "ledger_commit_artifact_digest": ledger_digest,
        "canonical_ledger_commit_sha": commit_sha,
        "base_ledger_sha256": base_sha,
        "canonical_coverage_ledger_sha256": canonical_sha,
        "node_dispatch_control_run_ids_consumed": sorted(controls),
        "selector_run_id": selector_run_id,
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "canonical_complete_source_ids": expected_complete,
        "next_promotion_node_id": "promote:pools_trade_lbp",
        "human_approval_input": "apply_pools_trade_instant_ledger",
        "human_approval_value": True,
        "canonical_ledger_mutated": True,
        "automatic_acquisition_complete": True,
        "phase2_universe_coverage_complete": False,
    }



PHASE2_POOLS_TRADE_LBP_PROMOTION_REVIEW_VERSION = (
    "phase2-pools-trade-lbp-promotion-review-v1"
)
POOLS_TRADE_LBP_COVERAGE_WORKFLOW = (
    "phase2-pools-trade-lbp-source-coverage.yml"
)
POOLS_TRADE_LBP_COVERAGE_ARTIFACT = (
    "phase2-pools-trade-lbp-source-coverage"
)
POOLS_TRADE_LBP_COVERAGE_REPORT_PATH = (
    "pools-trade-lbp-source-coverage-report.json"
)


def build_phase2_pools_trade_lbp_promotion_review_handoff(
    current_ledger: Mapping[str, object],
    coverage_report: Mapping[str, object],
    source_inventory: Iterable[Mapping[str, object]],
    *,
    coverage_run_id: int,
    coverage_artifact_digest: str,
    coverage_report_sha256: str,
    planner_run_id: int,
    planner_artifact_digest: str,
    canonical_ledger_sha256: str,
) -> dict:
    """Prepare exact pools.trade LBP promotion inputs at 4/14."""

    inventory = [dict(row) for row in source_inventory]
    before = validate_phase2_coverage_ledger(
        dict(current_ledger),
        inventory,
    )
    expected_before = [
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
    ]
    if before["complete_source_ids"] != expected_before:
        raise ValueError(
            "pools.trade LBP review requires exact 4/14 Instant ledger"
        )

    report = dict(coverage_report)
    if report.get("source_id") != "pools_trade_lbp":
        raise ValueError("pools.trade LBP review source identity drift")
    if report.get("coverage_status") != "complete":
        raise ValueError(
            "pools.trade LBP review requires complete coverage report"
        )

    _, after = apply_phase2_source_coverage_report(
        dict(current_ledger),
        inventory,
        report,
    )
    expected_after = expected_before + ["pools_trade_lbp"]
    if after["complete_source_ids"] != expected_after:
        raise ValueError(
            "pools.trade LBP review does not complete exactly next source"
        )
    if after["phase2_universe_coverage_complete"]:
        raise ValueError(
            "pools.trade LBP review unexpectedly closes Phase 2"
        )

    run_id = _positive_run_id(
        coverage_run_id,
        label="pools.trade LBP coverage run ID",
    )
    artifact_digest = _artifact_digest(
        coverage_artifact_digest,
        label="pools.trade LBP coverage artifact digest",
    )
    report_sha = _sha256(
        coverage_report_sha256,
        label="pools.trade LBP coverage report",
    )
    planner_id = _positive_run_id(
        planner_run_id,
        label="pools.trade LBP promotion planner run ID",
    )
    planner_digest = _artifact_digest(
        planner_artifact_digest,
        label="pools.trade LBP planner artifact digest",
    )
    ledger_sha = _sha256(
        canonical_ledger_sha256,
        label="pools.trade LBP canonical ledger",
    )

    generated_inputs = {
        "coverage_run_id": str(run_id),
        "coverage_artifact_name": POOLS_TRADE_LBP_COVERAGE_ARTIFACT,
        "expected_artifact_digest": artifact_digest,
        "coverage_report_path": POOLS_TRADE_LBP_COVERAGE_REPORT_PATH,
        "expected_report_sha256": report_sha,
        "expected_source_id": "pools_trade_lbp",
    }
    return {
        "version": PHASE2_POOLS_TRADE_LBP_PROMOTION_REVIEW_VERSION,
        "source_id": "pools_trade_lbp",
        "coverage_workflow": POOLS_TRADE_LBP_COVERAGE_WORKFLOW,
        "coverage_run_id": run_id,
        "coverage_artifact_name": POOLS_TRADE_LBP_COVERAGE_ARTIFACT,
        "coverage_artifact_digest": artifact_digest,
        "coverage_report_path": POOLS_TRADE_LBP_COVERAGE_REPORT_PATH,
        "coverage_report_sha256": report_sha,
        "planner_run_id": planner_id,
        "planner_artifact_digest": planner_digest,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "complete_source_ids_before": expected_before,
        "complete_source_ids_after_if_promoted": expected_after,
        "promotion_workflow": SOURCE_COVERAGE_PROMOTION_WORKFLOW,
        "promotion_generated_inputs": generated_inputs,
        "promotion_review_required": True,
        "promotion_dispatched": False,
        "proposal_created": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }


def validate_phase2_pools_trade_lbp_promotion_review_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate immutable 4/14 pools.trade LBP review handoff."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE2_POOLS_TRADE_LBP_PROMOTION_REVIEW_VERSION
    ):
        raise ValueError("pools.trade LBP promotion review version changed")
    control_run_id = _positive_run_id(
        row.get("promotion_review_control_run_id"),
        label="pools.trade LBP review control run ID",
    )
    prior_run_id = _positive_run_id(
        row.get("pools_trade_instant_ledger_approval_run_id"),
        label="pools.trade Instant ledger approval run ID",
    )
    coverage_run_id = _positive_run_id(
        row.get("coverage_run_id"),
        label="pools.trade LBP coverage run ID",
    )
    planner_run_id = _positive_run_id(
        row.get("planner_run_id"),
        label="pools.trade LBP planner run ID",
    )
    prior_digest = _artifact_digest(
        row.get("pools_trade_instant_ledger_approval_artifact_digest"),
        label="pools.trade Instant ledger approval artifact digest",
    )
    coverage_digest = _artifact_digest(
        row.get("coverage_artifact_digest"),
        label="pools.trade LBP coverage artifact digest",
    )
    planner_digest = _artifact_digest(
        row.get("planner_artifact_digest"),
        label="pools.trade LBP planner artifact digest",
    )
    report_sha = _sha256(
        row.get("coverage_report_sha256"),
        label="pools.trade LBP coverage report",
    )
    ledger_sha = _sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="pools.trade LBP canonical ledger",
    )
    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError("pools.trade LBP review execution branch is empty")
    head_sha = _commit_sha(
        row.get("execution_head_sha"),
        label="pools.trade LBP review execution head",
    )

    if row.get("source_id") != "pools_trade_lbp":
        raise ValueError("pools.trade LBP review source drift")
    if row.get("coverage_workflow") != POOLS_TRADE_LBP_COVERAGE_WORKFLOW:
        raise ValueError("pools.trade LBP coverage workflow drift")
    if row.get("coverage_artifact_name") != POOLS_TRADE_LBP_COVERAGE_ARTIFACT:
        raise ValueError("pools.trade LBP artifact-name drift")
    if row.get("coverage_report_path") != POOLS_TRADE_LBP_COVERAGE_REPORT_PATH:
        raise ValueError("pools.trade LBP report-path drift")
    if row.get("promotion_workflow") != SOURCE_COVERAGE_PROMOTION_WORKFLOW:
        raise ValueError("pools.trade LBP promotion workflow drift")

    expected_inputs = {
        "coverage_run_id": str(coverage_run_id),
        "coverage_artifact_name": POOLS_TRADE_LBP_COVERAGE_ARTIFACT,
        "expected_artifact_digest": coverage_digest,
        "coverage_report_path": POOLS_TRADE_LBP_COVERAGE_REPORT_PATH,
        "expected_report_sha256": report_sha,
        "expected_source_id": "pools_trade_lbp",
    }
    if row.get("promotion_generated_inputs") != expected_inputs:
        raise ValueError("pools.trade LBP promotion generated-input drift")
    if row.get("promotion_review_required") is not True:
        raise ValueError("pools.trade LBP promotion lost review requirement")
    for field in (
        "promotion_dispatched",
        "proposal_created",
        "canonical_coverage_ledger_mutated",
        "canonical_ledger_write_authorized",
    ):
        if row.get(field) is not False:
            raise ValueError(
                f"pools.trade LBP review violates read-only field {field}"
            )

    return {
        **row,
        "promotion_review_control_run_id": control_run_id,
        "pools_trade_instant_ledger_approval_run_id": prior_run_id,
        "pools_trade_instant_ledger_approval_artifact_digest": prior_digest,
        "coverage_run_id": coverage_run_id,
        "coverage_artifact_digest": coverage_digest,
        "coverage_report_sha256": report_sha,
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "promotion_generated_inputs": expected_inputs,
        "promotion_review_required": True,
        "promotion_dispatched": False,
        "proposal_created": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }



PHASE2_POOLS_TRADE_LBP_PROMOTION_PROPOSAL_VERSION = (
    "phase2-pools-trade-lbp-promotion-proposal-v1"
)


def validate_phase2_pools_trade_lbp_promotion_proposal_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate pools.trade LBP proposal before ledger approval."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE2_POOLS_TRADE_LBP_PROMOTION_PROPOSAL_VERSION
    ):
        raise ValueError(
            "pools.trade LBP promotion proposal receipt version changed"
        )
    control_run_id = _positive_run_id(
        row.get("promotion_proposal_control_run_id"),
        label="pools.trade LBP proposal control run ID",
    )
    review_run_id = _positive_run_id(
        row.get("promotion_review_run_id"),
        label="pools.trade LBP review run ID",
    )
    dispatcher_run_id = _positive_run_id(
        row.get("node_dispatch_control_run_id"),
        label="pools.trade LBP promotion dispatcher run ID",
    )
    promotion_run_id = _positive_run_id(
        row.get("promotion_run_id"),
        label="pools.trade LBP promotion run ID",
    )
    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError("pools.trade LBP proposal execution branch is empty")
    head_sha = _commit_sha(
        row.get("execution_head_sha"),
        label="pools.trade LBP proposal execution head",
    )
    review_digest = _artifact_digest(
        row.get("promotion_review_artifact_digest"),
        label="pools.trade LBP review artifact digest",
    )
    promotion_digest = _artifact_digest(
        row.get("promotion_artifact_digest"),
        label="pools.trade LBP promotion artifact digest",
    )
    handoff_sha = _sha256(
        row.get("promotion_handoff_sha256"),
        label="pools.trade LBP promotion handoff",
    )
    proposed_sha = _sha256(
        row.get("proposed_ledger_sha256"),
        label="pools.trade LBP proposed ledger",
    )
    base_sha = _sha256(
        row.get("base_ledger_sha256"),
        label="pools.trade LBP proposal base ledger",
    )

    if row.get("source_id") != "pools_trade_lbp":
        raise ValueError("pools.trade LBP proposal source identity drift")
    if row.get("promotion_workflow") != SOURCE_COVERAGE_PROMOTION_WORKFLOW:
        raise ValueError("pools.trade LBP proposal workflow identity drift")
    if row.get("complete_source_ids_before") != [
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
    ]:
        raise ValueError("pools.trade LBP proposal before-set drift")
    if row.get("complete_source_ids_after") != [
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
    ]:
        raise ValueError("pools.trade LBP proposal after-set drift")
    if row.get("phase2_universe_coverage_complete") is not False:
        raise ValueError(
            "pools.trade LBP proposal unexpectedly closes Phase 2"
        )
    if row.get("proposal_created") is not True:
        raise ValueError("pools.trade LBP proposal lacks proposal proof")
    if row.get("proposal_validated") is not True:
        raise ValueError("pools.trade LBP proposal lacks validation proof")
    if row.get("canonical_coverage_ledger_mutated") is not False:
        raise ValueError("pools.trade LBP proposal unexpectedly mutates ledger")
    if row.get("ledger_commit_authorized") is not False:
        raise ValueError(
            "pools.trade LBP proposal unexpectedly authorizes ledger commit"
        )
    if row.get("ledger_commit_approval_input") != "apply_proposed_ledger":
        raise ValueError(
            "pools.trade LBP proposal ledger approval input drift"
        )
    if row.get("ledger_commit_approval_value_supplied") is not False:
        raise ValueError(
            "pools.trade LBP proposal already supplies ledger approval"
        )

    expected_generated = {
        "promotion_run_id": str(promotion_run_id),
        "expected_artifact_digest": promotion_digest,
        "expected_handoff_sha256": handoff_sha,
        "expected_proposed_ledger_sha256": proposed_sha,
        "expected_source_id": "pools_trade_lbp",
    }
    if row.get("ledger_commit_generated_inputs") != expected_generated:
        raise ValueError(
            "pools.trade LBP proposal ledger-commit input drift"
        )

    return {
        **row,
        "promotion_proposal_control_run_id": control_run_id,
        "promotion_review_run_id": review_run_id,
        "node_dispatch_control_run_id": dispatcher_run_id,
        "promotion_run_id": promotion_run_id,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "promotion_review_artifact_digest": review_digest,
        "promotion_artifact_digest": promotion_digest,
        "promotion_handoff_sha256": handoff_sha,
        "proposed_ledger_sha256": proposed_sha,
        "base_ledger_sha256": base_sha,
        "source_id": "pools_trade_lbp",
        "ledger_commit_generated_inputs": expected_generated,
        "ledger_commit_approval_input": "apply_proposed_ledger",
        "ledger_commit_approval_value_supplied": False,
        "proposal_created": True,
        "proposal_validated": True,
        "canonical_coverage_ledger_mutated": False,
        "ledger_commit_authorized": False,
    }



def validate_phase2_pools_trade_lbp_ledger_commit_receipt(
    receipt: Mapping[str, object],
    *,
    expected_promotion_run_id: int,
    expected_promotion_artifact_digest: str,
    expected_promotion_handoff_sha256: str,
    expected_proposed_ledger_sha256: str,
) -> dict:
    """Validate approved pools.trade LBP canonical-ledger write."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        "phase2-source-coverage-ledger-commit-v1"
    ):
        raise ValueError(
            "pools.trade LBP ledger commit receipt version changed"
        )
    if row.get("source_id") != "pools_trade_lbp":
        raise ValueError("pools.trade LBP ledger commit source identity drift")
    promotion_run_id = _positive_run_id(
        row.get("promotion_run_id"),
        label="pools.trade LBP ledger promotion run ID",
    )
    if promotion_run_id != int(expected_promotion_run_id):
        raise ValueError("pools.trade LBP ledger commit promotion run drift")
    if row.get("promotion_artifact_name") != (
        "phase2-source-coverage-promotion-pools_trade_lbp"
    ):
        raise ValueError("pools.trade LBP ledger commit artifact-name drift")
    artifact_digest = _artifact_digest(
        row.get("promotion_artifact_digest"),
        label="pools.trade LBP promotion artifact digest",
    )
    if artifact_digest != _artifact_digest(
        expected_promotion_artifact_digest,
        label="expected pools.trade LBP promotion artifact digest",
    ):
        raise ValueError(
            "pools.trade LBP ledger commit promotion artifact drift"
        )
    handoff_sha = _sha256(
        row.get("promotion_handoff_sha256"),
        label="pools.trade LBP promotion handoff",
    )
    if handoff_sha != _sha256(
        expected_promotion_handoff_sha256,
        label="expected pools.trade LBP promotion handoff",
    ):
        raise ValueError(
            "pools.trade LBP ledger commit promotion handoff drift"
        )
    proposed_sha = _sha256(
        row.get("proposed_ledger_sha256"),
        label="pools.trade LBP proposed ledger",
    )
    if proposed_sha != _sha256(
        expected_proposed_ledger_sha256,
        label="expected pools.trade LBP proposed ledger",
    ):
        raise ValueError(
            "pools.trade LBP ledger commit proposed-ledger drift"
        )
    base_sha = _sha256(
        row.get("base_ledger_sha256"),
        label="pools.trade LBP base ledger",
    )
    if row.get("complete_source_ids_before") != [
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
    ]:
        raise ValueError("pools.trade LBP ledger commit before-set drift")
    if row.get("complete_source_ids_after") != [
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
    ]:
        raise ValueError("pools.trade LBP ledger commit after-set drift")
    if row.get("phase2_universe_coverage_complete") is not False:
        raise ValueError(
            "pools.trade LBP ledger commit unexpectedly closes Phase 2"
        )
    commit_sha = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="pools.trade LBP canonical ledger commit",
    )
    if row.get("explicit_approval") is not True:
        raise ValueError("pools.trade LBP ledger commit lacks explicit approval")
    if row.get("canonical_ledger_mutated") is not True:
        raise ValueError("pools.trade LBP ledger commit lacks mutation proof")
    return {
        **row,
        "promotion_run_id": promotion_run_id,
        "promotion_artifact_digest": artifact_digest,
        "promotion_handoff_sha256": handoff_sha,
        "base_ledger_sha256": base_sha,
        "proposed_ledger_sha256": proposed_sha,
        "canonical_ledger_commit_sha": commit_sha,
        "explicit_approval": True,
        "canonical_ledger_mutated": True,
    }


def validate_phase2_pools_trade_lbp_post_commit_frontier(
    execution_plan: Mapping[str, object],
    verified_receipts: Mapping[str, object],
    dispatch_plan: Mapping[str, object],
) -> dict:
    """Freeze exact 5/14 frontier after pools.trade LBP is canonical."""

    execution = dict(execution_plan)
    verified = dict(verified_receipts)
    dispatch = dict(dispatch_plan)
    expected_complete = [
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
    ]
    if execution.get("canonical_complete_source_ids") != expected_complete:
        raise ValueError(
            "pools.trade LBP post-commit canonical source set drift"
        )
    if int(execution.get("complete_sources", -1)) != 5:
        raise ValueError("pools.trade LBP post-commit source count drift")
    if int(execution.get("incomplete_sources", -1)) != 9:
        raise ValueError("pools.trade LBP post-commit incomplete count drift")
    if execution.get("phase2_universe_coverage_complete") is not False:
        raise ValueError(
            "pools.trade LBP post-commit unexpectedly closes Phase 2"
        )

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
    removed = canonical_coverages | {
        "promote:pools_fun",
        "promote:pools_trade_instant",
        "promote:pools_trade_lbp",
    }
    expected_active = pre_frontier - canonical_coverages
    if set(execution.get("completed_node_ids") or []) != expected_active:
        raise ValueError("pools.trade LBP post-commit active completion drift")
    if set(execution.get("ignored_completed_node_ids") or []) != removed:
        raise ValueError(
            "pools.trade LBP post-commit ignored-completion drift"
        )
    if execution.get("ready_to_dispatch_node_ids") != ["promote:doppler"]:
        raise ValueError("pools.trade LBP post-commit next promotion drift")
    if execution.get("awaiting_explicit_approval_node_ids") != []:
        raise ValueError("pools.trade LBP post-commit unexpected approvals")
    if execution.get("ledger_commit_approval_node_ids") != []:
        raise ValueError(
            "pools.trade LBP post-commit unexpected ledger approval"
        )

    expected_verified = pre_frontier | {
        "promote:pools_fun",
        "promote:pools_trade_instant",
        "promote:pools_trade_lbp",
    }
    if set(verified.get("completed_node_ids") or []) != expected_verified:
        raise ValueError(
            "pools.trade LBP post-commit verified completion drift"
        )
    controls = verified.get("node_dispatch_run_ids_consumed")
    if (
        not isinstance(controls, list)
        or len(controls) != 43
        or len(set(int(value) for value in controls)) != 43
    ):
        raise ValueError(
            "pools.trade LBP post-commit requires exactly 43 "
            "dispatcher receipts"
        )
    if verified.get("all_runs_current_or_ledger_only_ancestors") is not True:
        raise ValueError("pools.trade LBP post-commit lacks lineage proof")

    rows = dispatch.get("nodes")
    if not isinstance(rows, list) or len(rows) != 1:
        raise ValueError("pools.trade LBP post-commit dispatch row count drift")
    row = dict(rows[0])
    if row.get("node_id") != "promote:doppler":
        raise ValueError("pools.trade LBP post-commit dispatch node drift")
    if row.get("workflow") != SOURCE_COVERAGE_PROMOTION_WORKFLOW:
        raise ValueError("pools.trade LBP post-commit promotion workflow drift")
    if set(dict(row.get("run_id_inputs") or {})) != {"coverage_run_id"}:
        raise ValueError("Doppler promotion coverage-run binding drift")
    expected_manual = sorted([
        "coverage_artifact_name",
        "coverage_report_path",
        "expected_artifact_digest",
        "expected_report_sha256",
        "expected_source_id",
    ])
    actual_manual = sorted(
        str(value) for value in row.get("remaining_manual_inputs") or []
    )
    if actual_manual != expected_manual:
        raise ValueError("Doppler promotion manual-input drift")

    return {
        "version": "phase2-pools-trade-lbp-post-commit-frontier-v1",
        "canonical_complete_source_ids": expected_complete,
        "complete_sources": 5,
        "incomplete_sources": 9,
        "active_completed_execution_nodes": len(expected_active),
        "ignored_completed_node_ids": sorted(removed),
        "node_dispatch_control_runs_consumed": len(controls),
        "next_promotion_node_id": "promote:doppler",
        "next_promotion_manual_inputs": actual_manual,
        "automatic_acquisition_complete": True,
        "canonical_ledger_advanced": True,
        "phase2_universe_coverage_complete": False,
    }



def validate_phase2_pools_trade_lbp_ledger_approved_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate immutable 5/14 handoff after pools.trade LBP commit."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        "phase2-pools-trade-lbp-ledger-approved-receipt-v1"
    ):
        raise ValueError(
            "pools.trade LBP approved-ledger receipt version changed"
        )
    control_run_id = _positive_run_id(
        row.get("ledger_approval_control_run_id"),
        label="pools.trade LBP ledger approval control run ID",
    )
    proposal_run_id = _positive_run_id(
        row.get("promotion_proposal_run_id"),
        label="pools.trade LBP proposal run ID",
    )
    ledger_run_id = _positive_run_id(
        row.get("ledger_commit_run_id"),
        label="pools.trade LBP ledger commit run ID",
    )
    selector_run_id = _positive_run_id(
        row.get("selector_run_id"),
        label="pools.trade LBP selector run ID",
    )
    planner_run_id = _positive_run_id(
        row.get("planner_run_id"),
        label="pools.trade LBP post-commit planner run ID",
    )
    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError("pools.trade LBP approved-ledger branch is empty")
    approval_head = _commit_sha(
        row.get("approval_execution_head_sha"),
        label="pools.trade LBP approval execution head",
    )
    proposal_digest = _artifact_digest(
        row.get("promotion_proposal_artifact_digest"),
        label="pools.trade LBP proposal artifact digest",
    )
    ledger_digest = _artifact_digest(
        row.get("ledger_commit_artifact_digest"),
        label="pools.trade LBP ledger commit artifact digest",
    )
    commit_sha = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="pools.trade LBP canonical ledger commit",
    )
    base_sha = _sha256(
        row.get("base_ledger_sha256"),
        label="pools.trade LBP approved base ledger",
    )
    canonical_sha = _sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="pools.trade LBP approved canonical ledger",
    )
    planner_digest = _artifact_digest(
        row.get("planner_artifact_digest"),
        label="pools.trade LBP post-commit planner artifact digest",
    )
    controls_raw = row.get("node_dispatch_control_run_ids_consumed")
    if not isinstance(controls_raw, list):
        raise ValueError(
            "pools.trade LBP approved control-run list is missing"
        )
    controls = [int(value) for value in controls_raw]
    if (
        len(controls) != 43
        or len(set(controls)) != 43
        or min(controls) <= 0
    ):
        raise ValueError(
            "pools.trade LBP approved handoff requires exactly 43 "
            "control runs"
        )
    expected_complete = [
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
    ]
    if row.get("canonical_complete_source_ids") != expected_complete:
        raise ValueError(
            "pools.trade LBP approved canonical source set drift"
        )
    if row.get("next_promotion_node_id") != "promote:doppler":
        raise ValueError(
            "pools.trade LBP approved next promotion drift"
        )
    if row.get("human_approval_input") != (
        "apply_pools_trade_lbp_ledger"
    ):
        raise ValueError(
            "pools.trade LBP approved human-input identity drift"
        )
    if row.get("human_approval_value") is not True:
        raise ValueError(
            "pools.trade LBP approved receipt lacks affirmative approval"
        )
    if row.get("canonical_ledger_mutated") is not True:
        raise ValueError(
            "pools.trade LBP approved receipt lacks ledger mutation"
        )
    if row.get("automatic_acquisition_complete") is not True:
        raise ValueError(
            "pools.trade LBP approved receipt lost acquisition proof"
        )
    if row.get("phase2_universe_coverage_complete") is not False:
        raise ValueError(
            "pools.trade LBP approved receipt unexpectedly closes Phase 2"
        )
    return {
        **row,
        "ledger_approval_control_run_id": control_run_id,
        "execution_branch": branch,
        "approval_execution_head_sha": approval_head,
        "promotion_proposal_run_id": proposal_run_id,
        "promotion_proposal_artifact_digest": proposal_digest,
        "ledger_commit_run_id": ledger_run_id,
        "ledger_commit_artifact_digest": ledger_digest,
        "canonical_ledger_commit_sha": commit_sha,
        "base_ledger_sha256": base_sha,
        "canonical_coverage_ledger_sha256": canonical_sha,
        "node_dispatch_control_run_ids_consumed": sorted(controls),
        "selector_run_id": selector_run_id,
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "canonical_complete_source_ids": expected_complete,
        "next_promotion_node_id": "promote:doppler",
        "human_approval_input": "apply_pools_trade_lbp_ledger",
        "human_approval_value": True,
        "canonical_ledger_mutated": True,
        "automatic_acquisition_complete": True,
        "phase2_universe_coverage_complete": False,
    }



PHASE2_DOPPLER_PROMOTION_REVIEW_VERSION = (
    "phase2-doppler-promotion-review-v1"
)
DOPPLER_COVERAGE_WORKFLOW = "phase2-doppler-source-coverage.yml"
DOPPLER_COVERAGE_ARTIFACT = "phase2-doppler-source-coverage"
DOPPLER_COVERAGE_REPORT_PATH = "doppler-source-coverage-report.json"
PHASE2_DOPPLER_PROMOTION_PROPOSAL_VERSION = (
    "phase2-doppler-promotion-proposal-v1"
)


def build_phase2_doppler_promotion_review_handoff(
    current_ledger: Mapping[str, object],
    coverage_report: Mapping[str, object],
    source_inventory: Iterable[Mapping[str, object]],
    *,
    coverage_run_id: int,
    coverage_artifact_digest: str,
    coverage_report_sha256: str,
    planner_run_id: int,
    planner_artifact_digest: str,
    canonical_ledger_sha256: str,
) -> dict:
    """Prepare exact Doppler promotion inputs at 5/14."""

    inventory = [dict(row) for row in source_inventory]
    before = validate_phase2_coverage_ledger(
        dict(current_ledger),
        inventory,
    )
    expected_before = [
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
    ]
    if before["complete_source_ids"] != expected_before:
        raise ValueError(
            "Doppler review requires exact 5/14 pools.trade LBP ledger"
        )

    report = dict(coverage_report)
    if report.get("source_id") != "doppler":
        raise ValueError("Doppler review source identity drift")
    if report.get("coverage_status") != "complete":
        raise ValueError(
            "Doppler review requires complete coverage report"
        )

    _, after = apply_phase2_source_coverage_report(
        dict(current_ledger),
        inventory,
        report,
    )
    expected_after = sorted(expected_before + ["doppler"])
    if after["complete_source_ids"] != expected_after:
        raise ValueError(
            "Doppler review does not complete exactly next source"
        )
    if after["phase2_universe_coverage_complete"]:
        raise ValueError("Doppler review unexpectedly closes Phase 2")

    run_id = _positive_run_id(
        coverage_run_id,
        label="Doppler coverage run ID",
    )
    artifact_digest = _artifact_digest(
        coverage_artifact_digest,
        label="Doppler coverage artifact digest",
    )
    report_sha = _sha256(
        coverage_report_sha256,
        label="Doppler coverage report",
    )
    planner_id = _positive_run_id(
        planner_run_id,
        label="Doppler promotion planner run ID",
    )
    planner_digest = _artifact_digest(
        planner_artifact_digest,
        label="Doppler planner artifact digest",
    )
    ledger_sha = _sha256(
        canonical_ledger_sha256,
        label="Doppler canonical ledger",
    )

    generated_inputs = {
        "coverage_run_id": str(run_id),
        "coverage_artifact_name": DOPPLER_COVERAGE_ARTIFACT,
        "expected_artifact_digest": artifact_digest,
        "coverage_report_path": DOPPLER_COVERAGE_REPORT_PATH,
        "expected_report_sha256": report_sha,
        "expected_source_id": "doppler",
    }
    return {
        "version": PHASE2_DOPPLER_PROMOTION_REVIEW_VERSION,
        "source_id": "doppler",
        "coverage_workflow": DOPPLER_COVERAGE_WORKFLOW,
        "coverage_run_id": run_id,
        "coverage_artifact_name": DOPPLER_COVERAGE_ARTIFACT,
        "coverage_artifact_digest": artifact_digest,
        "coverage_report_path": DOPPLER_COVERAGE_REPORT_PATH,
        "coverage_report_sha256": report_sha,
        "planner_run_id": planner_id,
        "planner_artifact_digest": planner_digest,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "complete_source_ids_before": expected_before,
        "complete_source_ids_after_if_promoted": expected_after,
        "promotion_workflow": SOURCE_COVERAGE_PROMOTION_WORKFLOW,
        "promotion_generated_inputs": generated_inputs,
        "promotion_review_required": True,
        "promotion_dispatched": False,
        "proposal_created": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }


def validate_phase2_doppler_promotion_review_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate immutable 5/14 Doppler review handoff."""

    row = dict(receipt)
    if str(row.get("version") or "") != PHASE2_DOPPLER_PROMOTION_REVIEW_VERSION:
        raise ValueError("Doppler promotion review version changed")
    control_run_id = _positive_run_id(
        row.get("promotion_review_control_run_id"),
        label="Doppler review control run ID",
    )
    prior_run_id = _positive_run_id(
        row.get("pools_trade_lbp_ledger_approval_run_id"),
        label="pools.trade LBP ledger approval run ID",
    )
    coverage_run_id = _positive_run_id(
        row.get("coverage_run_id"),
        label="Doppler coverage run ID",
    )
    planner_run_id = _positive_run_id(
        row.get("planner_run_id"),
        label="Doppler planner run ID",
    )
    prior_digest = _artifact_digest(
        row.get("pools_trade_lbp_ledger_approval_artifact_digest"),
        label="pools.trade LBP ledger approval artifact digest",
    )
    coverage_digest = _artifact_digest(
        row.get("coverage_artifact_digest"),
        label="Doppler coverage artifact digest",
    )
    planner_digest = _artifact_digest(
        row.get("planner_artifact_digest"),
        label="Doppler planner artifact digest",
    )
    report_sha = _sha256(
        row.get("coverage_report_sha256"),
        label="Doppler coverage report",
    )
    ledger_sha = _sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="Doppler canonical ledger",
    )
    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError("Doppler review execution branch is empty")
    head_sha = _commit_sha(
        row.get("execution_head_sha"),
        label="Doppler review execution head",
    )

    if row.get("source_id") != "doppler":
        raise ValueError("Doppler review source drift")
    if row.get("coverage_workflow") != DOPPLER_COVERAGE_WORKFLOW:
        raise ValueError("Doppler coverage workflow drift")
    if row.get("coverage_artifact_name") != DOPPLER_COVERAGE_ARTIFACT:
        raise ValueError("Doppler artifact-name drift")
    if row.get("coverage_report_path") != DOPPLER_COVERAGE_REPORT_PATH:
        raise ValueError("Doppler report-path drift")
    if row.get("promotion_workflow") != SOURCE_COVERAGE_PROMOTION_WORKFLOW:
        raise ValueError("Doppler promotion workflow drift")

    expected_inputs = {
        "coverage_run_id": str(coverage_run_id),
        "coverage_artifact_name": DOPPLER_COVERAGE_ARTIFACT,
        "expected_artifact_digest": coverage_digest,
        "coverage_report_path": DOPPLER_COVERAGE_REPORT_PATH,
        "expected_report_sha256": report_sha,
        "expected_source_id": "doppler",
    }
    if row.get("promotion_generated_inputs") != expected_inputs:
        raise ValueError("Doppler promotion generated-input drift")
    if row.get("promotion_review_required") is not True:
        raise ValueError("Doppler promotion lost review requirement")
    for field in (
        "promotion_dispatched",
        "proposal_created",
        "canonical_coverage_ledger_mutated",
        "canonical_ledger_write_authorized",
    ):
        if row.get(field) is not False:
            raise ValueError(
                f"Doppler review violates read-only field {field}"
            )

    return {
        **row,
        "promotion_review_control_run_id": control_run_id,
        "pools_trade_lbp_ledger_approval_run_id": prior_run_id,
        "pools_trade_lbp_ledger_approval_artifact_digest": prior_digest,
        "coverage_run_id": coverage_run_id,
        "coverage_artifact_digest": coverage_digest,
        "coverage_report_sha256": report_sha,
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "promotion_generated_inputs": expected_inputs,
        "promotion_review_required": True,
        "promotion_dispatched": False,
        "proposal_created": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }


def validate_phase2_doppler_promotion_proposal_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate Doppler proposal before ledger approval."""

    row = dict(receipt)
    if str(row.get("version") or "") != PHASE2_DOPPLER_PROMOTION_PROPOSAL_VERSION:
        raise ValueError("Doppler promotion proposal receipt version changed")
    control_run_id = _positive_run_id(
        row.get("promotion_proposal_control_run_id"),
        label="Doppler proposal control run ID",
    )
    review_run_id = _positive_run_id(
        row.get("promotion_review_run_id"),
        label="Doppler review run ID",
    )
    dispatcher_run_id = _positive_run_id(
        row.get("node_dispatch_control_run_id"),
        label="Doppler promotion dispatcher run ID",
    )
    promotion_run_id = _positive_run_id(
        row.get("promotion_run_id"),
        label="Doppler promotion run ID",
    )
    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError("Doppler proposal execution branch is empty")
    head_sha = _commit_sha(
        row.get("execution_head_sha"),
        label="Doppler proposal execution head",
    )
    review_digest = _artifact_digest(
        row.get("promotion_review_artifact_digest"),
        label="Doppler review artifact digest",
    )
    promotion_digest = _artifact_digest(
        row.get("promotion_artifact_digest"),
        label="Doppler promotion artifact digest",
    )
    handoff_sha = _sha256(
        row.get("promotion_handoff_sha256"),
        label="Doppler promotion handoff",
    )
    proposed_sha = _sha256(
        row.get("proposed_ledger_sha256"),
        label="Doppler proposed ledger",
    )
    base_sha = _sha256(
        row.get("base_ledger_sha256"),
        label="Doppler proposal base ledger",
    )
    expected_before = [
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
    ]
    expected_after = sorted(expected_before + ["doppler"])

    if row.get("source_id") != "doppler":
        raise ValueError("Doppler proposal source identity drift")
    if row.get("promotion_workflow") != SOURCE_COVERAGE_PROMOTION_WORKFLOW:
        raise ValueError("Doppler proposal workflow identity drift")
    if row.get("complete_source_ids_before") != expected_before:
        raise ValueError("Doppler proposal before-set drift")
    if row.get("complete_source_ids_after") != expected_after:
        raise ValueError("Doppler proposal after-set drift")
    if row.get("phase2_universe_coverage_complete") is not False:
        raise ValueError("Doppler proposal unexpectedly closes Phase 2")
    if row.get("proposal_created") is not True:
        raise ValueError("Doppler proposal lacks proposal proof")
    if row.get("proposal_validated") is not True:
        raise ValueError("Doppler proposal lacks validation proof")
    if row.get("canonical_coverage_ledger_mutated") is not False:
        raise ValueError("Doppler proposal unexpectedly mutates ledger")
    if row.get("ledger_commit_authorized") is not False:
        raise ValueError("Doppler proposal unexpectedly authorizes ledger commit")
    if row.get("ledger_commit_approval_input") != "apply_proposed_ledger":
        raise ValueError("Doppler proposal ledger approval input drift")
    if row.get("ledger_commit_approval_value_supplied") is not False:
        raise ValueError("Doppler proposal already supplies ledger approval")

    expected_generated = {
        "promotion_run_id": str(promotion_run_id),
        "expected_artifact_digest": promotion_digest,
        "expected_handoff_sha256": handoff_sha,
        "expected_proposed_ledger_sha256": proposed_sha,
        "expected_source_id": "doppler",
    }
    if row.get("ledger_commit_generated_inputs") != expected_generated:
        raise ValueError("Doppler proposal ledger-commit input drift")

    return {
        **row,
        "promotion_proposal_control_run_id": control_run_id,
        "promotion_review_run_id": review_run_id,
        "node_dispatch_control_run_id": dispatcher_run_id,
        "promotion_run_id": promotion_run_id,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "promotion_review_artifact_digest": review_digest,
        "promotion_artifact_digest": promotion_digest,
        "promotion_handoff_sha256": handoff_sha,
        "proposed_ledger_sha256": proposed_sha,
        "base_ledger_sha256": base_sha,
        "source_id": "doppler",
        "ledger_commit_generated_inputs": expected_generated,
        "ledger_commit_approval_input": "apply_proposed_ledger",
        "ledger_commit_approval_value_supplied": False,
        "proposal_created": True,
        "proposal_validated": True,
        "canonical_coverage_ledger_mutated": False,
        "ledger_commit_authorized": False,
    }


def validate_phase2_doppler_ledger_commit_receipt(
    receipt: Mapping[str, object],
    *,
    expected_promotion_run_id: int,
    expected_promotion_artifact_digest: str,
    expected_promotion_handoff_sha256: str,
    expected_proposed_ledger_sha256: str,
) -> dict:
    """Validate approved Doppler canonical-ledger write."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        "phase2-source-coverage-ledger-commit-v1"
    ):
        raise ValueError("Doppler ledger commit receipt version changed")
    if row.get("source_id") != "doppler":
        raise ValueError("Doppler ledger commit source identity drift")
    promotion_run_id = _positive_run_id(
        row.get("promotion_run_id"),
        label="Doppler ledger promotion run ID",
    )
    if promotion_run_id != int(expected_promotion_run_id):
        raise ValueError("Doppler ledger commit promotion run drift")
    if row.get("promotion_artifact_name") != (
        "phase2-source-coverage-promotion-doppler"
    ):
        raise ValueError("Doppler ledger commit artifact-name drift")
    artifact_digest = _artifact_digest(
        row.get("promotion_artifact_digest"),
        label="Doppler promotion artifact digest",
    )
    if artifact_digest != _artifact_digest(
        expected_promotion_artifact_digest,
        label="expected Doppler promotion artifact digest",
    ):
        raise ValueError("Doppler ledger commit promotion artifact drift")
    handoff_sha = _sha256(
        row.get("promotion_handoff_sha256"),
        label="Doppler promotion handoff",
    )
    if handoff_sha != _sha256(
        expected_promotion_handoff_sha256,
        label="expected Doppler promotion handoff",
    ):
        raise ValueError("Doppler ledger commit promotion handoff drift")
    proposed_sha = _sha256(
        row.get("proposed_ledger_sha256"),
        label="Doppler proposed ledger",
    )
    if proposed_sha != _sha256(
        expected_proposed_ledger_sha256,
        label="expected Doppler proposed ledger",
    ):
        raise ValueError("Doppler ledger commit proposed-ledger drift")
    base_sha = _sha256(
        row.get("base_ledger_sha256"),
        label="Doppler base ledger",
    )
    expected_before = [
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
    ]
    expected_after = sorted(expected_before + ["doppler"])
    if row.get("complete_source_ids_before") != expected_before:
        raise ValueError("Doppler ledger commit before-set drift")
    if row.get("complete_source_ids_after") != expected_after:
        raise ValueError("Doppler ledger commit after-set drift")
    if row.get("phase2_universe_coverage_complete") is not False:
        raise ValueError("Doppler ledger commit unexpectedly closes Phase 2")
    commit_sha = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="Doppler canonical ledger commit",
    )
    if row.get("explicit_approval") is not True:
        raise ValueError("Doppler ledger commit lacks explicit approval")
    if row.get("canonical_ledger_mutated") is not True:
        raise ValueError("Doppler ledger commit lacks mutation proof")
    return {
        **row,
        "promotion_run_id": promotion_run_id,
        "promotion_artifact_digest": artifact_digest,
        "promotion_handoff_sha256": handoff_sha,
        "base_ledger_sha256": base_sha,
        "proposed_ledger_sha256": proposed_sha,
        "canonical_ledger_commit_sha": commit_sha,
        "explicit_approval": True,
        "canonical_ledger_mutated": True,
    }


def validate_phase2_doppler_post_commit_frontier(
    execution_plan: Mapping[str, object],
    verified_receipts: Mapping[str, object],
    dispatch_plan: Mapping[str, object],
) -> dict:
    """Freeze exact 6/14 frontier after Doppler is canonical."""

    execution = dict(execution_plan)
    verified = dict(verified_receipts)
    dispatch = dict(dispatch_plan)
    expected_complete = [
        "doppler",
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
    ]
    if execution.get("canonical_complete_source_ids") != expected_complete:
        raise ValueError("Doppler post-commit canonical source set drift")
    if int(execution.get("complete_sources", -1)) != 6:
        raise ValueError("Doppler post-commit source count drift")
    if int(execution.get("incomplete_sources", -1)) != 8:
        raise ValueError("Doppler post-commit incomplete count drift")
    if execution.get("phase2_universe_coverage_complete") is not False:
        raise ValueError("Doppler post-commit unexpectedly closes Phase 2")

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
        "coverage:doppler",
    }
    removed = canonical_coverages | {
        "promote:pools_fun",
        "promote:pools_trade_instant",
        "promote:pools_trade_lbp",
        "promote:doppler",
    }
    expected_active = pre_frontier - canonical_coverages
    if set(execution.get("completed_node_ids") or []) != expected_active:
        raise ValueError("Doppler post-commit active completion drift")
    if set(execution.get("ignored_completed_node_ids") or []) != removed:
        raise ValueError("Doppler post-commit ignored-completion drift")
    if execution.get("ready_to_dispatch_node_ids") != ["promote:flap"]:
        raise ValueError("Doppler post-commit next promotion drift")
    if execution.get("awaiting_explicit_approval_node_ids") != []:
        raise ValueError("Doppler post-commit unexpected approvals")
    if execution.get("ledger_commit_approval_node_ids") != []:
        raise ValueError("Doppler post-commit unexpected ledger approval")

    expected_verified = pre_frontier | {
        "promote:pools_fun",
        "promote:pools_trade_instant",
        "promote:pools_trade_lbp",
        "promote:doppler",
    }
    if set(verified.get("completed_node_ids") or []) != expected_verified:
        raise ValueError("Doppler post-commit verified completion drift")
    controls = verified.get("node_dispatch_run_ids_consumed")
    if (
        not isinstance(controls, list)
        or len(controls) != 44
        or len(set(int(value) for value in controls)) != 44
    ):
        raise ValueError(
            "Doppler post-commit requires exactly 44 dispatcher receipts"
        )
    if verified.get("all_runs_current_or_ledger_only_ancestors") is not True:
        raise ValueError("Doppler post-commit lacks lineage proof")

    rows = dispatch.get("nodes")
    if not isinstance(rows, list) or len(rows) != 1:
        raise ValueError("Doppler post-commit dispatch row count drift")
    row = dict(rows[0])
    if row.get("node_id") != "promote:flap":
        raise ValueError("Doppler post-commit dispatch node drift")
    if row.get("workflow") != SOURCE_COVERAGE_PROMOTION_WORKFLOW:
        raise ValueError("Doppler post-commit promotion workflow drift")
    if set(dict(row.get("run_id_inputs") or {})) != {"coverage_run_id"}:
        raise ValueError("Flap promotion coverage-run binding drift")
    expected_manual = sorted([
        "coverage_artifact_name",
        "coverage_report_path",
        "expected_artifact_digest",
        "expected_report_sha256",
        "expected_source_id",
    ])
    actual_manual = sorted(
        str(value) for value in row.get("remaining_manual_inputs") or []
    )
    if actual_manual != expected_manual:
        raise ValueError("Flap promotion manual-input drift")

    return {
        "version": "phase2-doppler-post-commit-frontier-v1",
        "canonical_complete_source_ids": expected_complete,
        "complete_sources": 6,
        "incomplete_sources": 8,
        "active_completed_execution_nodes": len(expected_active),
        "ignored_completed_node_ids": sorted(removed),
        "node_dispatch_control_runs_consumed": len(controls),
        "next_promotion_node_id": "promote:flap",
        "next_promotion_manual_inputs": actual_manual,
        "automatic_acquisition_complete": True,
        "canonical_ledger_advanced": True,
        "phase2_universe_coverage_complete": False,
    }



def validate_phase2_doppler_ledger_approved_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate immutable 6/14 handoff after Doppler commit."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        "phase2-doppler-ledger-approved-receipt-v1"
    ):
        raise ValueError("Doppler approved-ledger receipt version changed")
    control_run_id = _positive_run_id(
        row.get("ledger_approval_control_run_id"),
        label="Doppler ledger approval control run ID",
    )
    proposal_run_id = _positive_run_id(
        row.get("promotion_proposal_run_id"),
        label="Doppler proposal run ID",
    )
    ledger_run_id = _positive_run_id(
        row.get("ledger_commit_run_id"),
        label="Doppler ledger commit run ID",
    )
    selector_run_id = _positive_run_id(
        row.get("selector_run_id"),
        label="Doppler selector run ID",
    )
    planner_run_id = _positive_run_id(
        row.get("planner_run_id"),
        label="Doppler post-commit planner run ID",
    )
    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError("Doppler approved-ledger branch is empty")
    approval_head = _commit_sha(
        row.get("approval_execution_head_sha"),
        label="Doppler approval execution head",
    )
    proposal_digest = _artifact_digest(
        row.get("promotion_proposal_artifact_digest"),
        label="Doppler proposal artifact digest",
    )
    ledger_digest = _artifact_digest(
        row.get("ledger_commit_artifact_digest"),
        label="Doppler ledger commit artifact digest",
    )
    commit_sha = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="Doppler canonical ledger commit",
    )
    base_sha = _sha256(
        row.get("base_ledger_sha256"),
        label="Doppler approved base ledger",
    )
    canonical_sha = _sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="Doppler approved canonical ledger",
    )
    planner_digest = _artifact_digest(
        row.get("planner_artifact_digest"),
        label="Doppler post-commit planner artifact digest",
    )
    controls_raw = row.get("node_dispatch_control_run_ids_consumed")
    if not isinstance(controls_raw, list):
        raise ValueError("Doppler approved control-run list is missing")
    controls = [int(value) for value in controls_raw]
    if (
        len(controls) != 44
        or len(set(controls)) != 44
        or min(controls) <= 0
    ):
        raise ValueError(
            "Doppler approved handoff requires exactly 44 control runs"
        )
    expected_complete = [
        "doppler",
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
    ]
    if row.get("canonical_complete_source_ids") != expected_complete:
        raise ValueError("Doppler approved canonical source set drift")
    if row.get("next_promotion_node_id") != "promote:flap":
        raise ValueError("Doppler approved next promotion drift")
    if row.get("human_approval_input") != "apply_doppler_ledger":
        raise ValueError("Doppler approved human-input identity drift")
    if row.get("human_approval_value") is not True:
        raise ValueError(
            "Doppler approved receipt lacks affirmative approval"
        )
    if row.get("canonical_ledger_mutated") is not True:
        raise ValueError("Doppler approved receipt lacks ledger mutation")
    if row.get("automatic_acquisition_complete") is not True:
        raise ValueError("Doppler approved receipt lost acquisition proof")
    if row.get("phase2_universe_coverage_complete") is not False:
        raise ValueError(
            "Doppler approved receipt unexpectedly closes Phase 2"
        )
    return {
        **row,
        "ledger_approval_control_run_id": control_run_id,
        "execution_branch": branch,
        "approval_execution_head_sha": approval_head,
        "promotion_proposal_run_id": proposal_run_id,
        "promotion_proposal_artifact_digest": proposal_digest,
        "ledger_commit_run_id": ledger_run_id,
        "ledger_commit_artifact_digest": ledger_digest,
        "canonical_ledger_commit_sha": commit_sha,
        "base_ledger_sha256": base_sha,
        "canonical_coverage_ledger_sha256": canonical_sha,
        "node_dispatch_control_run_ids_consumed": sorted(controls),
        "selector_run_id": selector_run_id,
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "canonical_complete_source_ids": expected_complete,
        "next_promotion_node_id": "promote:flap",
        "human_approval_input": "apply_doppler_ledger",
        "human_approval_value": True,
        "canonical_ledger_mutated": True,
        "automatic_acquisition_complete": True,
        "phase2_universe_coverage_complete": False,
    }



PHASE2_FLAP_PROMOTION_REVIEW_VERSION = "phase2-flap-promotion-review-v1"
FLAP_COVERAGE_WORKFLOW = "phase2-flap-source-coverage.yml"
FLAP_COVERAGE_ARTIFACT = "phase2-flap-source-coverage"
FLAP_COVERAGE_REPORT_PATH = "flap-source-coverage-report.json"
PHASE2_FLAP_PROMOTION_PROPOSAL_VERSION = "phase2-flap-promotion-proposal-v1"


def build_phase2_flap_promotion_review_handoff(
    current_ledger: Mapping[str, object],
    coverage_report: Mapping[str, object],
    source_inventory: Iterable[Mapping[str, object]],
    *,
    coverage_run_id: int,
    coverage_artifact_digest: str,
    coverage_report_sha256: str,
    planner_run_id: int,
    planner_artifact_digest: str,
    canonical_ledger_sha256: str,
) -> dict:
    """Prepare exact Flap promotion inputs at 6/14."""

    inventory = [dict(row) for row in source_inventory]
    before = validate_phase2_coverage_ledger(
        dict(current_ledger),
        inventory,
    )
    expected_before = [
        "doppler",
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
    ]
    if before["complete_source_ids"] != expected_before:
        raise ValueError(
            "Flap review requires exact 6/14 Doppler ledger"
        )

    report = dict(coverage_report)
    if report.get("source_id") != "flap":
        raise ValueError("Flap review source identity drift")
    if report.get("coverage_status") != "complete":
        raise ValueError("Flap review requires complete coverage report")

    _, after = apply_phase2_source_coverage_report(
        dict(current_ledger),
        inventory,
        report,
    )
    expected_after = sorted(expected_before + ["flap"])
    if after["complete_source_ids"] != expected_after:
        raise ValueError(
            "Flap review does not complete exactly next source"
        )
    if after["phase2_universe_coverage_complete"]:
        raise ValueError("Flap review unexpectedly closes Phase 2")

    run_id = _positive_run_id(coverage_run_id, label="Flap coverage run ID")
    artifact_digest = _artifact_digest(
        coverage_artifact_digest,
        label="Flap coverage artifact digest",
    )
    report_sha = _sha256(
        coverage_report_sha256,
        label="Flap coverage report",
    )
    planner_id = _positive_run_id(
        planner_run_id,
        label="Flap promotion planner run ID",
    )
    planner_digest = _artifact_digest(
        planner_artifact_digest,
        label="Flap planner artifact digest",
    )
    ledger_sha = _sha256(
        canonical_ledger_sha256,
        label="Flap canonical ledger",
    )

    generated_inputs = {
        "coverage_run_id": str(run_id),
        "coverage_artifact_name": FLAP_COVERAGE_ARTIFACT,
        "expected_artifact_digest": artifact_digest,
        "coverage_report_path": FLAP_COVERAGE_REPORT_PATH,
        "expected_report_sha256": report_sha,
        "expected_source_id": "flap",
    }
    return {
        "version": PHASE2_FLAP_PROMOTION_REVIEW_VERSION,
        "source_id": "flap",
        "coverage_workflow": FLAP_COVERAGE_WORKFLOW,
        "coverage_run_id": run_id,
        "coverage_artifact_name": FLAP_COVERAGE_ARTIFACT,
        "coverage_artifact_digest": artifact_digest,
        "coverage_report_path": FLAP_COVERAGE_REPORT_PATH,
        "coverage_report_sha256": report_sha,
        "planner_run_id": planner_id,
        "planner_artifact_digest": planner_digest,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "complete_source_ids_before": expected_before,
        "complete_source_ids_after_if_promoted": expected_after,
        "promotion_workflow": SOURCE_COVERAGE_PROMOTION_WORKFLOW,
        "promotion_generated_inputs": generated_inputs,
        "promotion_review_required": True,
        "promotion_dispatched": False,
        "proposal_created": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }


def validate_phase2_flap_promotion_review_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate immutable 6/14 Flap review handoff."""

    row = dict(receipt)
    if str(row.get("version") or "") != PHASE2_FLAP_PROMOTION_REVIEW_VERSION:
        raise ValueError("Flap promotion review version changed")
    control_run_id = _positive_run_id(
        row.get("promotion_review_control_run_id"),
        label="Flap review control run ID",
    )
    prior_run_id = _positive_run_id(
        row.get("doppler_ledger_approval_run_id"),
        label="Doppler ledger approval run ID",
    )
    coverage_run_id = _positive_run_id(
        row.get("coverage_run_id"),
        label="Flap coverage run ID",
    )
    planner_run_id = _positive_run_id(
        row.get("planner_run_id"),
        label="Flap planner run ID",
    )
    prior_digest = _artifact_digest(
        row.get("doppler_ledger_approval_artifact_digest"),
        label="Doppler ledger approval artifact digest",
    )
    coverage_digest = _artifact_digest(
        row.get("coverage_artifact_digest"),
        label="Flap coverage artifact digest",
    )
    planner_digest = _artifact_digest(
        row.get("planner_artifact_digest"),
        label="Flap planner artifact digest",
    )
    report_sha = _sha256(
        row.get("coverage_report_sha256"),
        label="Flap coverage report",
    )
    ledger_sha = _sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="Flap canonical ledger",
    )
    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError("Flap review execution branch is empty")
    head_sha = _commit_sha(
        row.get("execution_head_sha"),
        label="Flap review execution head",
    )

    if row.get("source_id") != "flap":
        raise ValueError("Flap review source drift")
    if row.get("coverage_workflow") != FLAP_COVERAGE_WORKFLOW:
        raise ValueError("Flap coverage workflow drift")
    if row.get("coverage_artifact_name") != FLAP_COVERAGE_ARTIFACT:
        raise ValueError("Flap artifact-name drift")
    if row.get("coverage_report_path") != FLAP_COVERAGE_REPORT_PATH:
        raise ValueError("Flap report-path drift")
    if row.get("promotion_workflow") != SOURCE_COVERAGE_PROMOTION_WORKFLOW:
        raise ValueError("Flap promotion workflow drift")

    expected_inputs = {
        "coverage_run_id": str(coverage_run_id),
        "coverage_artifact_name": FLAP_COVERAGE_ARTIFACT,
        "expected_artifact_digest": coverage_digest,
        "coverage_report_path": FLAP_COVERAGE_REPORT_PATH,
        "expected_report_sha256": report_sha,
        "expected_source_id": "flap",
    }
    if row.get("promotion_generated_inputs") != expected_inputs:
        raise ValueError("Flap promotion generated-input drift")
    if row.get("promotion_review_required") is not True:
        raise ValueError("Flap promotion lost review requirement")
    for field in (
        "promotion_dispatched",
        "proposal_created",
        "canonical_coverage_ledger_mutated",
        "canonical_ledger_write_authorized",
    ):
        if row.get(field) is not False:
            raise ValueError(
                f"Flap review violates read-only field {field}"
            )

    return {
        **row,
        "promotion_review_control_run_id": control_run_id,
        "doppler_ledger_approval_run_id": prior_run_id,
        "doppler_ledger_approval_artifact_digest": prior_digest,
        "coverage_run_id": coverage_run_id,
        "coverage_artifact_digest": coverage_digest,
        "coverage_report_sha256": report_sha,
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "promotion_generated_inputs": expected_inputs,
        "promotion_review_required": True,
        "promotion_dispatched": False,
        "proposal_created": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }


def validate_phase2_flap_promotion_proposal_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate Flap proposal before ledger approval."""

    row = dict(receipt)
    if str(row.get("version") or "") != PHASE2_FLAP_PROMOTION_PROPOSAL_VERSION:
        raise ValueError("Flap promotion proposal receipt version changed")
    control_run_id = _positive_run_id(
        row.get("promotion_proposal_control_run_id"),
        label="Flap proposal control run ID",
    )
    review_run_id = _positive_run_id(
        row.get("promotion_review_run_id"),
        label="Flap review run ID",
    )
    dispatcher_run_id = _positive_run_id(
        row.get("node_dispatch_control_run_id"),
        label="Flap promotion dispatcher run ID",
    )
    promotion_run_id = _positive_run_id(
        row.get("promotion_run_id"),
        label="Flap promotion run ID",
    )
    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError("Flap proposal execution branch is empty")
    head_sha = _commit_sha(
        row.get("execution_head_sha"),
        label="Flap proposal execution head",
    )
    review_digest = _artifact_digest(
        row.get("promotion_review_artifact_digest"),
        label="Flap review artifact digest",
    )
    promotion_digest = _artifact_digest(
        row.get("promotion_artifact_digest"),
        label="Flap promotion artifact digest",
    )
    handoff_sha = _sha256(
        row.get("promotion_handoff_sha256"),
        label="Flap promotion handoff",
    )
    proposed_sha = _sha256(
        row.get("proposed_ledger_sha256"),
        label="Flap proposed ledger",
    )
    base_sha = _sha256(
        row.get("base_ledger_sha256"),
        label="Flap proposal base ledger",
    )
    expected_before = [
        "doppler",
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
    ]
    expected_after = sorted(expected_before + ["flap"])

    if row.get("source_id") != "flap":
        raise ValueError("Flap proposal source identity drift")
    if row.get("promotion_workflow") != SOURCE_COVERAGE_PROMOTION_WORKFLOW:
        raise ValueError("Flap proposal workflow identity drift")
    if row.get("complete_source_ids_before") != expected_before:
        raise ValueError("Flap proposal before-set drift")
    if row.get("complete_source_ids_after") != expected_after:
        raise ValueError("Flap proposal after-set drift")
    if row.get("phase2_universe_coverage_complete") is not False:
        raise ValueError("Flap proposal unexpectedly closes Phase 2")
    if row.get("proposal_created") is not True:
        raise ValueError("Flap proposal lacks proposal proof")
    if row.get("proposal_validated") is not True:
        raise ValueError("Flap proposal lacks validation proof")
    if row.get("canonical_coverage_ledger_mutated") is not False:
        raise ValueError("Flap proposal unexpectedly mutates ledger")
    if row.get("ledger_commit_authorized") is not False:
        raise ValueError("Flap proposal unexpectedly authorizes ledger commit")
    if row.get("ledger_commit_approval_input") != "apply_proposed_ledger":
        raise ValueError("Flap proposal ledger approval input drift")
    if row.get("ledger_commit_approval_value_supplied") is not False:
        raise ValueError("Flap proposal already supplies ledger approval")

    expected_generated = {
        "promotion_run_id": str(promotion_run_id),
        "expected_artifact_digest": promotion_digest,
        "expected_handoff_sha256": handoff_sha,
        "expected_proposed_ledger_sha256": proposed_sha,
        "expected_source_id": "flap",
    }
    if row.get("ledger_commit_generated_inputs") != expected_generated:
        raise ValueError("Flap proposal ledger-commit input drift")

    return {
        **row,
        "promotion_proposal_control_run_id": control_run_id,
        "promotion_review_run_id": review_run_id,
        "node_dispatch_control_run_id": dispatcher_run_id,
        "promotion_run_id": promotion_run_id,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "promotion_review_artifact_digest": review_digest,
        "promotion_artifact_digest": promotion_digest,
        "promotion_handoff_sha256": handoff_sha,
        "proposed_ledger_sha256": proposed_sha,
        "base_ledger_sha256": base_sha,
        "source_id": "flap",
        "ledger_commit_generated_inputs": expected_generated,
        "ledger_commit_approval_input": "apply_proposed_ledger",
        "ledger_commit_approval_value_supplied": False,
        "proposal_created": True,
        "proposal_validated": True,
        "canonical_coverage_ledger_mutated": False,
        "ledger_commit_authorized": False,
    }


def validate_phase2_flap_ledger_commit_receipt(
    receipt: Mapping[str, object],
    *,
    expected_promotion_run_id: int,
    expected_promotion_artifact_digest: str,
    expected_promotion_handoff_sha256: str,
    expected_proposed_ledger_sha256: str,
) -> dict:
    """Validate approved Flap canonical-ledger write."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        "phase2-source-coverage-ledger-commit-v1"
    ):
        raise ValueError("Flap ledger commit receipt version changed")
    if row.get("source_id") != "flap":
        raise ValueError("Flap ledger commit source identity drift")
    promotion_run_id = _positive_run_id(
        row.get("promotion_run_id"),
        label="Flap ledger promotion run ID",
    )
    if promotion_run_id != int(expected_promotion_run_id):
        raise ValueError("Flap ledger commit promotion run drift")
    if row.get("promotion_artifact_name") != (
        "phase2-source-coverage-promotion-flap"
    ):
        raise ValueError("Flap ledger commit artifact-name drift")
    artifact_digest = _artifact_digest(
        row.get("promotion_artifact_digest"),
        label="Flap promotion artifact digest",
    )
    if artifact_digest != _artifact_digest(
        expected_promotion_artifact_digest,
        label="expected Flap promotion artifact digest",
    ):
        raise ValueError("Flap ledger commit promotion artifact drift")
    handoff_sha = _sha256(
        row.get("promotion_handoff_sha256"),
        label="Flap promotion handoff",
    )
    if handoff_sha != _sha256(
        expected_promotion_handoff_sha256,
        label="expected Flap promotion handoff",
    ):
        raise ValueError("Flap ledger commit promotion handoff drift")
    proposed_sha = _sha256(
        row.get("proposed_ledger_sha256"),
        label="Flap proposed ledger",
    )
    if proposed_sha != _sha256(
        expected_proposed_ledger_sha256,
        label="expected Flap proposed ledger",
    ):
        raise ValueError("Flap ledger commit proposed-ledger drift")
    base_sha = _sha256(
        row.get("base_ledger_sha256"),
        label="Flap base ledger",
    )
    expected_before = [
        "doppler",
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
    ]
    expected_after = sorted(expected_before + ["flap"])
    if row.get("complete_source_ids_before") != expected_before:
        raise ValueError("Flap ledger commit before-set drift")
    if row.get("complete_source_ids_after") != expected_after:
        raise ValueError("Flap ledger commit after-set drift")
    if row.get("phase2_universe_coverage_complete") is not False:
        raise ValueError("Flap ledger commit unexpectedly closes Phase 2")
    commit_sha = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="Flap canonical ledger commit",
    )
    if row.get("explicit_approval") is not True:
        raise ValueError("Flap ledger commit lacks explicit approval")
    if row.get("canonical_ledger_mutated") is not True:
        raise ValueError("Flap ledger commit lacks mutation proof")
    return {
        **row,
        "promotion_run_id": promotion_run_id,
        "promotion_artifact_digest": artifact_digest,
        "promotion_handoff_sha256": handoff_sha,
        "base_ledger_sha256": base_sha,
        "proposed_ledger_sha256": proposed_sha,
        "canonical_ledger_commit_sha": commit_sha,
        "explicit_approval": True,
        "canonical_ledger_mutated": True,
    }


def validate_phase2_flap_post_commit_frontier(
    execution_plan: Mapping[str, object],
    verified_receipts: Mapping[str, object],
    dispatch_plan: Mapping[str, object],
) -> dict:
    """Freeze exact 7/14 frontier after Flap is canonical."""

    execution = dict(execution_plan)
    verified = dict(verified_receipts)
    dispatch = dict(dispatch_plan)
    expected_complete = [
        "doppler",
        "flap",
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
    ]
    if execution.get("canonical_complete_source_ids") != expected_complete:
        raise ValueError("Flap post-commit canonical source set drift")
    if int(execution.get("complete_sources", -1)) != 7:
        raise ValueError("Flap post-commit source count drift")
    if int(execution.get("incomplete_sources", -1)) != 7:
        raise ValueError("Flap post-commit incomplete count drift")
    if execution.get("phase2_universe_coverage_complete") is not False:
        raise ValueError("Flap post-commit unexpectedly closes Phase 2")

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
        "coverage:doppler",
        "coverage:flap",
    }
    removed = canonical_coverages | {
        "promote:pools_fun",
        "promote:pools_trade_instant",
        "promote:pools_trade_lbp",
        "promote:doppler",
        "promote:flap",
    }
    expected_active = pre_frontier - canonical_coverages
    if set(execution.get("completed_node_ids") or []) != expected_active:
        raise ValueError("Flap post-commit active completion drift")
    if set(execution.get("ignored_completed_node_ids") or []) != removed:
        raise ValueError("Flap post-commit ignored-completion drift")
    if execution.get("ready_to_dispatch_node_ids") != ["promote:trench_today"]:
        raise ValueError("Flap post-commit next promotion drift")
    if execution.get("awaiting_explicit_approval_node_ids") != []:
        raise ValueError("Flap post-commit unexpected approvals")
    if execution.get("ledger_commit_approval_node_ids") != []:
        raise ValueError("Flap post-commit unexpected ledger approval")

    expected_verified = pre_frontier | {
        "promote:pools_fun",
        "promote:pools_trade_instant",
        "promote:pools_trade_lbp",
        "promote:doppler",
        "promote:flap",
    }
    if set(verified.get("completed_node_ids") or []) != expected_verified:
        raise ValueError("Flap post-commit verified completion drift")
    controls = verified.get("node_dispatch_run_ids_consumed")
    if (
        not isinstance(controls, list)
        or len(controls) != 45
        or len(set(int(value) for value in controls)) != 45
    ):
        raise ValueError(
            "Flap post-commit requires exactly 45 dispatcher receipts"
        )
    if verified.get("all_runs_current_or_ledger_only_ancestors") is not True:
        raise ValueError("Flap post-commit lacks lineage proof")

    rows = dispatch.get("nodes")
    if not isinstance(rows, list) or len(rows) != 1:
        raise ValueError("Flap post-commit dispatch row count drift")
    row = dict(rows[0])
    if row.get("node_id") != "promote:trench_today":
        raise ValueError("Flap post-commit dispatch node drift")
    if row.get("workflow") != SOURCE_COVERAGE_PROMOTION_WORKFLOW:
        raise ValueError("Flap post-commit promotion workflow drift")
    if set(dict(row.get("run_id_inputs") or {})) != {"coverage_run_id"}:
        raise ValueError("trench.today promotion coverage-run binding drift")
    expected_manual = sorted([
        "coverage_artifact_name",
        "coverage_report_path",
        "expected_artifact_digest",
        "expected_report_sha256",
        "expected_source_id",
    ])
    actual_manual = sorted(
        str(value) for value in row.get("remaining_manual_inputs") or []
    )
    if actual_manual != expected_manual:
        raise ValueError("trench.today promotion manual-input drift")

    return {
        "version": "phase2-flap-post-commit-frontier-v1",
        "canonical_complete_source_ids": expected_complete,
        "complete_sources": 7,
        "incomplete_sources": 7,
        "active_completed_execution_nodes": len(expected_active),
        "ignored_completed_node_ids": sorted(removed),
        "node_dispatch_control_runs_consumed": len(controls),
        "next_promotion_node_id": "promote:trench_today",
        "next_promotion_manual_inputs": actual_manual,
        "automatic_acquisition_complete": True,
        "canonical_ledger_advanced": True,
        "phase2_universe_coverage_complete": False,
    }



def validate_phase2_flap_ledger_approved_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate immutable 7/14 handoff after Flap commit."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        "phase2-flap-ledger-approved-receipt-v1"
    ):
        raise ValueError("Flap approved-ledger receipt version changed")
    control_run_id = _positive_run_id(
        row.get("ledger_approval_control_run_id"),
        label="Flap ledger approval control run ID",
    )
    proposal_run_id = _positive_run_id(
        row.get("promotion_proposal_run_id"),
        label="Flap proposal run ID",
    )
    ledger_run_id = _positive_run_id(
        row.get("ledger_commit_run_id"),
        label="Flap ledger commit run ID",
    )
    selector_run_id = _positive_run_id(
        row.get("selector_run_id"),
        label="Flap selector run ID",
    )
    planner_run_id = _positive_run_id(
        row.get("planner_run_id"),
        label="Flap post-commit planner run ID",
    )
    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError("Flap approved-ledger branch is empty")
    approval_head = _commit_sha(
        row.get("approval_execution_head_sha"),
        label="Flap approval execution head",
    )
    proposal_digest = _artifact_digest(
        row.get("promotion_proposal_artifact_digest"),
        label="Flap proposal artifact digest",
    )
    ledger_digest = _artifact_digest(
        row.get("ledger_commit_artifact_digest"),
        label="Flap ledger commit artifact digest",
    )
    commit_sha = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="Flap canonical ledger commit",
    )
    base_sha = _sha256(
        row.get("base_ledger_sha256"),
        label="Flap approved base ledger",
    )
    canonical_sha = _sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="Flap approved canonical ledger",
    )
    planner_digest = _artifact_digest(
        row.get("planner_artifact_digest"),
        label="Flap post-commit planner artifact digest",
    )
    controls_raw = row.get("node_dispatch_control_run_ids_consumed")
    if not isinstance(controls_raw, list):
        raise ValueError("Flap approved control-run list is missing")
    controls = [int(value) for value in controls_raw]
    if (
        len(controls) != 45
        or len(set(controls)) != 45
        or min(controls) <= 0
    ):
        raise ValueError(
            "Flap approved handoff requires exactly 45 control runs"
        )
    expected_complete = [
        "doppler",
        "flap",
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
    ]
    if row.get("canonical_complete_source_ids") != expected_complete:
        raise ValueError("Flap approved canonical source set drift")
    if row.get("next_promotion_node_id") != "promote:trench_today":
        raise ValueError("Flap approved next promotion drift")
    if row.get("human_approval_input") != "apply_flap_ledger":
        raise ValueError("Flap approved human-input identity drift")
    if row.get("human_approval_value") is not True:
        raise ValueError(
            "Flap approved receipt lacks affirmative approval"
        )
    if row.get("canonical_ledger_mutated") is not True:
        raise ValueError("Flap approved receipt lacks ledger mutation")
    if row.get("automatic_acquisition_complete") is not True:
        raise ValueError("Flap approved receipt lost acquisition proof")
    if row.get("phase2_universe_coverage_complete") is not False:
        raise ValueError(
            "Flap approved receipt unexpectedly closes Phase 2"
        )
    return {
        **row,
        "ledger_approval_control_run_id": control_run_id,
        "execution_branch": branch,
        "approval_execution_head_sha": approval_head,
        "promotion_proposal_run_id": proposal_run_id,
        "promotion_proposal_artifact_digest": proposal_digest,
        "ledger_commit_run_id": ledger_run_id,
        "ledger_commit_artifact_digest": ledger_digest,
        "canonical_ledger_commit_sha": commit_sha,
        "base_ledger_sha256": base_sha,
        "canonical_coverage_ledger_sha256": canonical_sha,
        "node_dispatch_control_run_ids_consumed": sorted(controls),
        "selector_run_id": selector_run_id,
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "canonical_complete_source_ids": expected_complete,
        "next_promotion_node_id": "promote:trench_today",
        "human_approval_input": "apply_flap_ledger",
        "human_approval_value": True,
        "canonical_ledger_mutated": True,
        "automatic_acquisition_complete": True,
        "phase2_universe_coverage_complete": False,
    }



PHASE2_TRENCH_TODAY_PROMOTION_REVIEW_VERSION = (
    "phase2-trench-today-promotion-review-v1"
)
TRENCH_TODAY_COVERAGE_WORKFLOW = "phase2-trench-source-coverage.yml"
TRENCH_TODAY_COVERAGE_ARTIFACT = "phase2-trench-source-coverage"
TRENCH_TODAY_COVERAGE_REPORT_PATH = "trench-source-coverage-report.json"
PHASE2_TRENCH_TODAY_PROMOTION_PROPOSAL_VERSION = (
    "phase2-trench-today-promotion-proposal-v1"
)


def build_phase2_trench_today_promotion_review_handoff(
    current_ledger: Mapping[str, object],
    coverage_report: Mapping[str, object],
    source_inventory: Iterable[Mapping[str, object]],
    *,
    coverage_run_id: int,
    coverage_artifact_digest: str,
    coverage_report_sha256: str,
    planner_run_id: int,
    planner_artifact_digest: str,
    canonical_ledger_sha256: str,
) -> dict:
    """Prepare exact trench.today promotion inputs at 7/14."""

    inventory = [dict(row) for row in source_inventory]
    before = validate_phase2_coverage_ledger(dict(current_ledger), inventory)
    expected_before = [
        "doppler",
        "flap",
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
    ]
    if before["complete_source_ids"] != expected_before:
        raise ValueError("trench.today review requires exact 7/14 Flap ledger")

    report = dict(coverage_report)
    if report.get("source_id") != "trench_today":
        raise ValueError("trench.today review source identity drift")
    if report.get("coverage_status") != "complete":
        raise ValueError("trench.today review requires complete coverage report")

    _, after = apply_phase2_source_coverage_report(
        dict(current_ledger), inventory, report
    )
    expected_after = sorted(expected_before + ["trench_today"])
    if after["complete_source_ids"] != expected_after:
        raise ValueError(
            "trench.today review does not complete exactly next source"
        )
    if after["phase2_universe_coverage_complete"]:
        raise ValueError("trench.today review unexpectedly closes Phase 2")

    run_id = _positive_run_id(
        coverage_run_id, label="trench.today coverage run ID"
    )
    artifact_digest = _artifact_digest(
        coverage_artifact_digest,
        label="trench.today coverage artifact digest",
    )
    report_sha = _sha256(
        coverage_report_sha256, label="trench.today coverage report"
    )
    planner_id = _positive_run_id(
        planner_run_id, label="trench.today promotion planner run ID"
    )
    planner_digest = _artifact_digest(
        planner_artifact_digest,
        label="trench.today planner artifact digest",
    )
    ledger_sha = _sha256(
        canonical_ledger_sha256, label="trench.today canonical ledger"
    )
    generated_inputs = {
        "coverage_run_id": str(run_id),
        "coverage_artifact_name": TRENCH_TODAY_COVERAGE_ARTIFACT,
        "expected_artifact_digest": artifact_digest,
        "coverage_report_path": TRENCH_TODAY_COVERAGE_REPORT_PATH,
        "expected_report_sha256": report_sha,
        "expected_source_id": "trench_today",
    }
    return {
        "version": PHASE2_TRENCH_TODAY_PROMOTION_REVIEW_VERSION,
        "source_id": "trench_today",
        "coverage_workflow": TRENCH_TODAY_COVERAGE_WORKFLOW,
        "coverage_run_id": run_id,
        "coverage_artifact_name": TRENCH_TODAY_COVERAGE_ARTIFACT,
        "coverage_artifact_digest": artifact_digest,
        "coverage_report_path": TRENCH_TODAY_COVERAGE_REPORT_PATH,
        "coverage_report_sha256": report_sha,
        "planner_run_id": planner_id,
        "planner_artifact_digest": planner_digest,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "complete_source_ids_before": expected_before,
        "complete_source_ids_after_if_promoted": expected_after,
        "promotion_workflow": SOURCE_COVERAGE_PROMOTION_WORKFLOW,
        "promotion_generated_inputs": generated_inputs,
        "promotion_review_required": True,
        "promotion_dispatched": False,
        "proposal_created": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }


def validate_phase2_trench_today_promotion_review_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate immutable 7/14 trench.today review handoff."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE2_TRENCH_TODAY_PROMOTION_REVIEW_VERSION
    ):
        raise ValueError("trench.today promotion review version changed")
    control_run_id = _positive_run_id(
        row.get("promotion_review_control_run_id"),
        label="trench.today review control run ID",
    )
    prior_run_id = _positive_run_id(
        row.get("flap_ledger_approval_run_id"),
        label="Flap ledger approval run ID",
    )
    coverage_run_id = _positive_run_id(
        row.get("coverage_run_id"),
        label="trench.today coverage run ID",
    )
    planner_run_id = _positive_run_id(
        row.get("planner_run_id"),
        label="trench.today planner run ID",
    )
    prior_digest = _artifact_digest(
        row.get("flap_ledger_approval_artifact_digest"),
        label="Flap ledger approval artifact digest",
    )
    coverage_digest = _artifact_digest(
        row.get("coverage_artifact_digest"),
        label="trench.today coverage artifact digest",
    )
    planner_digest = _artifact_digest(
        row.get("planner_artifact_digest"),
        label="trench.today planner artifact digest",
    )
    report_sha = _sha256(
        row.get("coverage_report_sha256"),
        label="trench.today coverage report",
    )
    ledger_sha = _sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="trench.today canonical ledger",
    )
    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError("trench.today review execution branch is empty")
    head_sha = _commit_sha(
        row.get("execution_head_sha"),
        label="trench.today review execution head",
    )
    if row.get("source_id") != "trench_today":
        raise ValueError("trench.today review source drift")
    if row.get("coverage_workflow") != TRENCH_TODAY_COVERAGE_WORKFLOW:
        raise ValueError("trench.today coverage workflow drift")
    if row.get("coverage_artifact_name") != TRENCH_TODAY_COVERAGE_ARTIFACT:
        raise ValueError("trench.today artifact-name drift")
    if row.get("coverage_report_path") != TRENCH_TODAY_COVERAGE_REPORT_PATH:
        raise ValueError("trench.today report-path drift")
    if row.get("promotion_workflow") != SOURCE_COVERAGE_PROMOTION_WORKFLOW:
        raise ValueError("trench.today promotion workflow drift")
    expected_inputs = {
        "coverage_run_id": str(coverage_run_id),
        "coverage_artifact_name": TRENCH_TODAY_COVERAGE_ARTIFACT,
        "expected_artifact_digest": coverage_digest,
        "coverage_report_path": TRENCH_TODAY_COVERAGE_REPORT_PATH,
        "expected_report_sha256": report_sha,
        "expected_source_id": "trench_today",
    }
    if row.get("promotion_generated_inputs") != expected_inputs:
        raise ValueError("trench.today promotion generated-input drift")
    if row.get("promotion_review_required") is not True:
        raise ValueError("trench.today promotion lost review requirement")
    for field in (
        "promotion_dispatched",
        "proposal_created",
        "canonical_coverage_ledger_mutated",
        "canonical_ledger_write_authorized",
    ):
        if row.get(field) is not False:
            raise ValueError(
                f"trench.today review violates read-only field {field}"
            )
    return {
        **row,
        "promotion_review_control_run_id": control_run_id,
        "flap_ledger_approval_run_id": prior_run_id,
        "flap_ledger_approval_artifact_digest": prior_digest,
        "coverage_run_id": coverage_run_id,
        "coverage_artifact_digest": coverage_digest,
        "coverage_report_sha256": report_sha,
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "promotion_generated_inputs": expected_inputs,
        "promotion_review_required": True,
        "promotion_dispatched": False,
        "proposal_created": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }


def validate_phase2_trench_today_promotion_proposal_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate trench.today proposal before ledger approval."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE2_TRENCH_TODAY_PROMOTION_PROPOSAL_VERSION
    ):
        raise ValueError("trench.today promotion proposal receipt version changed")
    control_run_id = _positive_run_id(
        row.get("promotion_proposal_control_run_id"),
        label="trench.today proposal control run ID",
    )
    review_run_id = _positive_run_id(
        row.get("promotion_review_run_id"),
        label="trench.today review run ID",
    )
    dispatcher_run_id = _positive_run_id(
        row.get("node_dispatch_control_run_id"),
        label="trench.today promotion dispatcher run ID",
    )
    promotion_run_id = _positive_run_id(
        row.get("promotion_run_id"),
        label="trench.today promotion run ID",
    )
    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError("trench.today proposal execution branch is empty")
    head_sha = _commit_sha(
        row.get("execution_head_sha"),
        label="trench.today proposal execution head",
    )
    review_digest = _artifact_digest(
        row.get("promotion_review_artifact_digest"),
        label="trench.today review artifact digest",
    )
    promotion_digest = _artifact_digest(
        row.get("promotion_artifact_digest"),
        label="trench.today promotion artifact digest",
    )
    handoff_sha = _sha256(
        row.get("promotion_handoff_sha256"),
        label="trench.today promotion handoff",
    )
    proposed_sha = _sha256(
        row.get("proposed_ledger_sha256"),
        label="trench.today proposed ledger",
    )
    base_sha = _sha256(
        row.get("base_ledger_sha256"),
        label="trench.today proposal base ledger",
    )
    expected_before = [
        "doppler",
        "flap",
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
    ]
    expected_after = sorted(expected_before + ["trench_today"])
    if row.get("source_id") != "trench_today":
        raise ValueError("trench.today proposal source identity drift")
    if row.get("promotion_workflow") != SOURCE_COVERAGE_PROMOTION_WORKFLOW:
        raise ValueError("trench.today proposal workflow identity drift")
    if row.get("complete_source_ids_before") != expected_before:
        raise ValueError("trench.today proposal before-set drift")
    if row.get("complete_source_ids_after") != expected_after:
        raise ValueError("trench.today proposal after-set drift")
    if row.get("phase2_universe_coverage_complete") is not False:
        raise ValueError("trench.today proposal unexpectedly closes Phase 2")
    if row.get("proposal_created") is not True:
        raise ValueError("trench.today proposal lacks proposal proof")
    if row.get("proposal_validated") is not True:
        raise ValueError("trench.today proposal lacks validation proof")
    if row.get("canonical_coverage_ledger_mutated") is not False:
        raise ValueError("trench.today proposal unexpectedly mutates ledger")
    if row.get("ledger_commit_authorized") is not False:
        raise ValueError("trench.today proposal authorizes ledger commit")
    if row.get("ledger_commit_approval_input") != "apply_proposed_ledger":
        raise ValueError("trench.today proposal ledger approval input drift")
    if row.get("ledger_commit_approval_value_supplied") is not False:
        raise ValueError("trench.today proposal already supplies approval")
    expected_generated = {
        "promotion_run_id": str(promotion_run_id),
        "expected_artifact_digest": promotion_digest,
        "expected_handoff_sha256": handoff_sha,
        "expected_proposed_ledger_sha256": proposed_sha,
        "expected_source_id": "trench_today",
    }
    if row.get("ledger_commit_generated_inputs") != expected_generated:
        raise ValueError("trench.today proposal ledger-commit input drift")
    return {
        **row,
        "promotion_proposal_control_run_id": control_run_id,
        "promotion_review_run_id": review_run_id,
        "node_dispatch_control_run_id": dispatcher_run_id,
        "promotion_run_id": promotion_run_id,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "promotion_review_artifact_digest": review_digest,
        "promotion_artifact_digest": promotion_digest,
        "promotion_handoff_sha256": handoff_sha,
        "proposed_ledger_sha256": proposed_sha,
        "base_ledger_sha256": base_sha,
        "source_id": "trench_today",
        "ledger_commit_generated_inputs": expected_generated,
        "ledger_commit_approval_input": "apply_proposed_ledger",
        "ledger_commit_approval_value_supplied": False,
        "proposal_created": True,
        "proposal_validated": True,
        "canonical_coverage_ledger_mutated": False,
        "ledger_commit_authorized": False,
    }


def validate_phase2_trench_today_ledger_commit_receipt(
    receipt: Mapping[str, object],
    *,
    expected_promotion_run_id: int,
    expected_promotion_artifact_digest: str,
    expected_promotion_handoff_sha256: str,
    expected_proposed_ledger_sha256: str,
) -> dict:
    """Validate approved trench.today canonical-ledger write."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        "phase2-source-coverage-ledger-commit-v1"
    ):
        raise ValueError("trench.today ledger commit receipt version changed")
    if row.get("source_id") != "trench_today":
        raise ValueError("trench.today ledger commit source identity drift")
    promotion_run_id = _positive_run_id(
        row.get("promotion_run_id"),
        label="trench.today ledger promotion run ID",
    )
    if promotion_run_id != int(expected_promotion_run_id):
        raise ValueError("trench.today ledger commit promotion run drift")
    if row.get("promotion_artifact_name") != (
        "phase2-source-coverage-promotion-trench_today"
    ):
        raise ValueError("trench.today ledger commit artifact-name drift")
    artifact_digest = _artifact_digest(
        row.get("promotion_artifact_digest"),
        label="trench.today promotion artifact digest",
    )
    if artifact_digest != _artifact_digest(
        expected_promotion_artifact_digest,
        label="expected trench.today promotion artifact digest",
    ):
        raise ValueError("trench.today ledger commit promotion artifact drift")
    handoff_sha = _sha256(
        row.get("promotion_handoff_sha256"),
        label="trench.today promotion handoff",
    )
    if handoff_sha != _sha256(
        expected_promotion_handoff_sha256,
        label="expected trench.today promotion handoff",
    ):
        raise ValueError("trench.today ledger commit promotion handoff drift")
    proposed_sha = _sha256(
        row.get("proposed_ledger_sha256"),
        label="trench.today proposed ledger",
    )
    if proposed_sha != _sha256(
        expected_proposed_ledger_sha256,
        label="expected trench.today proposed ledger",
    ):
        raise ValueError("trench.today ledger commit proposed-ledger drift")
    base_sha = _sha256(
        row.get("base_ledger_sha256"),
        label="trench.today base ledger",
    )
    expected_before = [
        "doppler",
        "flap",
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
    ]
    expected_after = sorted(expected_before + ["trench_today"])
    if row.get("complete_source_ids_before") != expected_before:
        raise ValueError("trench.today ledger commit before-set drift")
    if row.get("complete_source_ids_after") != expected_after:
        raise ValueError("trench.today ledger commit after-set drift")
    if row.get("phase2_universe_coverage_complete") is not False:
        raise ValueError("trench.today commit unexpectedly closes Phase 2")
    commit_sha = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="trench.today canonical ledger commit",
    )
    if row.get("explicit_approval") is not True:
        raise ValueError("trench.today ledger commit lacks explicit approval")
    if row.get("canonical_ledger_mutated") is not True:
        raise ValueError("trench.today ledger commit lacks mutation proof")
    return {
        **row,
        "promotion_run_id": promotion_run_id,
        "promotion_artifact_digest": artifact_digest,
        "promotion_handoff_sha256": handoff_sha,
        "base_ledger_sha256": base_sha,
        "proposed_ledger_sha256": proposed_sha,
        "canonical_ledger_commit_sha": commit_sha,
        "explicit_approval": True,
        "canonical_ledger_mutated": True,
    }


def validate_phase2_trench_today_post_commit_frontier(
    execution_plan: Mapping[str, object],
    verified_receipts: Mapping[str, object],
    dispatch_plan: Mapping[str, object],
) -> dict:
    """Freeze exact 8/14 frontier after trench.today is canonical."""

    execution = dict(execution_plan)
    verified = dict(verified_receipts)
    dispatch = dict(dispatch_plan)
    expected_complete = [
        "doppler",
        "flap",
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
        "trench_today",
    ]
    if execution.get("canonical_complete_source_ids") != expected_complete:
        raise ValueError("trench.today post-commit canonical source set drift")
    if int(execution.get("complete_sources", -1)) != 8:
        raise ValueError("trench.today post-commit source count drift")
    if int(execution.get("incomplete_sources", -1)) != 6:
        raise ValueError("trench.today post-commit incomplete count drift")
    if execution.get("phase2_universe_coverage_complete") is not False:
        raise ValueError("trench.today post-commit unexpectedly closes Phase 2")

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
        "coverage:doppler",
        "coverage:flap",
        "coverage:trench_today",
    }
    removed = canonical_coverages | {
        "promote:pools_fun",
        "promote:pools_trade_instant",
        "promote:pools_trade_lbp",
        "promote:doppler",
        "promote:flap",
        "promote:trench_today",
    }
    expected_active = pre_frontier - canonical_coverages
    if set(execution.get("completed_node_ids") or []) != expected_active:
        raise ValueError("trench.today post-commit active completion drift")
    if set(execution.get("ignored_completed_node_ids") or []) != removed:
        raise ValueError("trench.today post-commit ignored-completion drift")
    if execution.get("ready_to_dispatch_node_ids") != [
        "promote:hood_fun_current"
    ]:
        raise ValueError("trench.today post-commit next promotion drift")
    if execution.get("awaiting_explicit_approval_node_ids") != []:
        raise ValueError("trench.today post-commit unexpected approvals")
    if execution.get("ledger_commit_approval_node_ids") != []:
        raise ValueError("trench.today post-commit unexpected ledger approval")

    expected_verified = pre_frontier | {
        "promote:pools_fun",
        "promote:pools_trade_instant",
        "promote:pools_trade_lbp",
        "promote:doppler",
        "promote:flap",
        "promote:trench_today",
    }
    if set(verified.get("completed_node_ids") or []) != expected_verified:
        raise ValueError("trench.today post-commit verified completion drift")
    controls = verified.get("node_dispatch_run_ids_consumed")
    if (
        not isinstance(controls, list)
        or len(controls) != 46
        or len(set(int(value) for value in controls)) != 46
    ):
        raise ValueError(
            "trench.today post-commit requires exactly 46 dispatcher receipts"
        )
    if verified.get("all_runs_current_or_ledger_only_ancestors") is not True:
        raise ValueError("trench.today post-commit lacks lineage proof")

    rows = dispatch.get("nodes")
    if not isinstance(rows, list) or len(rows) != 1:
        raise ValueError("trench.today post-commit dispatch row count drift")
    row = dict(rows[0])
    if row.get("node_id") != "promote:hood_fun_current":
        raise ValueError("trench.today post-commit dispatch node drift")
    if row.get("workflow") != SOURCE_COVERAGE_PROMOTION_WORKFLOW:
        raise ValueError("trench.today post-commit promotion workflow drift")
    if set(dict(row.get("run_id_inputs") or {})) != {"coverage_run_id"}:
        raise ValueError("hood.fun current promotion coverage-run binding drift")
    expected_manual = sorted([
        "coverage_artifact_name",
        "coverage_report_path",
        "expected_artifact_digest",
        "expected_report_sha256",
        "expected_source_id",
    ])
    actual_manual = sorted(
        str(value) for value in row.get("remaining_manual_inputs") or []
    )
    if actual_manual != expected_manual:
        raise ValueError("hood.fun current promotion manual-input drift")
    return {
        "version": "phase2-trench-today-post-commit-frontier-v1",
        "canonical_complete_source_ids": expected_complete,
        "complete_sources": 8,
        "incomplete_sources": 6,
        "active_completed_execution_nodes": len(expected_active),
        "ignored_completed_node_ids": sorted(removed),
        "node_dispatch_control_runs_consumed": len(controls),
        "next_promotion_node_id": "promote:hood_fun_current",
        "next_promotion_manual_inputs": actual_manual,
        "automatic_acquisition_complete": True,
        "canonical_ledger_advanced": True,
        "phase2_universe_coverage_complete": False,
    }



def validate_phase2_trench_today_ledger_approved_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate immutable 8/14 handoff after trench.today commit."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        "phase2-trench-today-ledger-approved-receipt-v1"
    ):
        raise ValueError(
            "trench.today approved-ledger receipt version changed"
        )
    control_run_id = _positive_run_id(
        row.get("ledger_approval_control_run_id"),
        label="trench.today ledger approval control run ID",
    )
    proposal_run_id = _positive_run_id(
        row.get("promotion_proposal_run_id"),
        label="trench.today proposal run ID",
    )
    ledger_run_id = _positive_run_id(
        row.get("ledger_commit_run_id"),
        label="trench.today ledger commit run ID",
    )
    selector_run_id = _positive_run_id(
        row.get("selector_run_id"),
        label="trench.today selector run ID",
    )
    planner_run_id = _positive_run_id(
        row.get("planner_run_id"),
        label="trench.today post-commit planner run ID",
    )
    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError("trench.today approved-ledger branch is empty")
    approval_head = _commit_sha(
        row.get("approval_execution_head_sha"),
        label="trench.today approval execution head",
    )
    proposal_digest = _artifact_digest(
        row.get("promotion_proposal_artifact_digest"),
        label="trench.today proposal artifact digest",
    )
    ledger_digest = _artifact_digest(
        row.get("ledger_commit_artifact_digest"),
        label="trench.today ledger commit artifact digest",
    )
    commit_sha = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="trench.today canonical ledger commit",
    )
    base_sha = _sha256(
        row.get("base_ledger_sha256"),
        label="trench.today approved base ledger",
    )
    canonical_sha = _sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="trench.today approved canonical ledger",
    )
    planner_digest = _artifact_digest(
        row.get("planner_artifact_digest"),
        label="trench.today post-commit planner artifact digest",
    )
    controls_raw = row.get("node_dispatch_control_run_ids_consumed")
    if not isinstance(controls_raw, list):
        raise ValueError(
            "trench.today approved control-run list is missing"
        )
    controls = [int(value) for value in controls_raw]
    if (
        len(controls) != 46
        or len(set(controls)) != 46
        or min(controls) <= 0
    ):
        raise ValueError(
            "trench.today approved handoff requires exactly 46 control runs"
        )
    expected_complete = [
        "doppler",
        "flap",
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
        "trench_today",
    ]
    if row.get("canonical_complete_source_ids") != expected_complete:
        raise ValueError(
            "trench.today approved canonical source set drift"
        )
    if row.get("next_promotion_node_id") != "promote:hood_fun_current":
        raise ValueError("trench.today approved next promotion drift")
    if row.get("human_approval_input") != "apply_trench_today_ledger":
        raise ValueError(
            "trench.today approved human-input identity drift"
        )
    if row.get("human_approval_value") is not True:
        raise ValueError(
            "trench.today approved receipt lacks affirmative approval"
        )
    if row.get("canonical_ledger_mutated") is not True:
        raise ValueError(
            "trench.today approved receipt lacks ledger mutation"
        )
    if row.get("automatic_acquisition_complete") is not True:
        raise ValueError(
            "trench.today approved receipt lost acquisition proof"
        )
    if row.get("phase2_universe_coverage_complete") is not False:
        raise ValueError(
            "trench.today approved receipt unexpectedly closes Phase 2"
        )
    return {
        **row,
        "ledger_approval_control_run_id": control_run_id,
        "execution_branch": branch,
        "approval_execution_head_sha": approval_head,
        "promotion_proposal_run_id": proposal_run_id,
        "promotion_proposal_artifact_digest": proposal_digest,
        "ledger_commit_run_id": ledger_run_id,
        "ledger_commit_artifact_digest": ledger_digest,
        "canonical_ledger_commit_sha": commit_sha,
        "base_ledger_sha256": base_sha,
        "canonical_coverage_ledger_sha256": canonical_sha,
        "node_dispatch_control_run_ids_consumed": sorted(controls),
        "selector_run_id": selector_run_id,
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "canonical_complete_source_ids": expected_complete,
        "next_promotion_node_id": "promote:hood_fun_current",
        "human_approval_input": "apply_trench_today_ledger",
        "human_approval_value": True,
        "canonical_ledger_mutated": True,
        "automatic_acquisition_complete": True,
        "phase2_universe_coverage_complete": False,
    }


PHASE2_HOOD_FUN_CURRENT_PROMOTION_REVIEW_VERSION = (
    "phase2-hood-fun-current-promotion-review-v1"
)
HOOD_FUN_CURRENT_COVERAGE_WORKFLOW = "phase2-hoodfun-current-coverage.yml"
HOOD_FUN_CURRENT_COVERAGE_ARTIFACT = "phase2-hoodfun-current-coverage"
HOOD_FUN_CURRENT_COVERAGE_REPORT_PATH = "hood-current-coverage.json"
PHASE2_HOOD_FUN_CURRENT_PROMOTION_PROPOSAL_VERSION = (
    "phase2-hood-fun-current-promotion-proposal-v1"
)


def build_phase2_hood_fun_current_promotion_review_handoff(
    current_ledger: Mapping[str, object],
    coverage_report: Mapping[str, object],
    source_inventory: Iterable[Mapping[str, object]],
    *,
    coverage_run_id: int,
    coverage_artifact_digest: str,
    coverage_report_sha256: str,
    planner_run_id: int,
    planner_artifact_digest: str,
    canonical_ledger_sha256: str,
) -> dict:
    """Prepare exact hood.fun current promotion inputs at 8/14."""

    inventory = [dict(row) for row in source_inventory]
    before = validate_phase2_coverage_ledger(dict(current_ledger), inventory)
    expected_before = [
        "doppler",
        "flap",
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
        "trench_today",
    ]
    if before["complete_source_ids"] != expected_before:
        raise ValueError("hood.fun current review requires exact 8/14 trench.today ledger")

    report = dict(coverage_report)
    if report.get("source_id") != "hood_fun_current":
        raise ValueError("hood.fun current review source identity drift")
    if report.get("coverage_status") != "complete":
        raise ValueError("hood.fun current review requires complete coverage report")

    _, after = apply_phase2_source_coverage_report(
        dict(current_ledger), inventory, report
    )
    expected_after = sorted(expected_before + ["hood_fun_current"])
    if after["complete_source_ids"] != expected_after:
        raise ValueError(
            "hood.fun current review does not complete exactly next source"
        )
    if after["phase2_universe_coverage_complete"]:
        raise ValueError("hood.fun current review unexpectedly closes Phase 2")

    run_id = _positive_run_id(
        coverage_run_id, label="hood.fun current coverage run ID"
    )
    artifact_digest = _artifact_digest(
        coverage_artifact_digest,
        label="hood.fun current coverage artifact digest",
    )
    report_sha = _sha256(
        coverage_report_sha256, label="hood.fun current coverage report"
    )
    planner_id = _positive_run_id(
        planner_run_id, label="hood.fun current promotion planner run ID"
    )
    planner_digest = _artifact_digest(
        planner_artifact_digest,
        label="hood.fun current planner artifact digest",
    )
    ledger_sha = _sha256(
        canonical_ledger_sha256, label="hood.fun current canonical ledger"
    )
    generated_inputs = {
        "coverage_run_id": str(run_id),
        "coverage_artifact_name": HOOD_FUN_CURRENT_COVERAGE_ARTIFACT,
        "expected_artifact_digest": artifact_digest,
        "coverage_report_path": HOOD_FUN_CURRENT_COVERAGE_REPORT_PATH,
        "expected_report_sha256": report_sha,
        "expected_source_id": "hood_fun_current",
    }
    return {
        "version": PHASE2_HOOD_FUN_CURRENT_PROMOTION_REVIEW_VERSION,
        "source_id": "hood_fun_current",
        "coverage_workflow": HOOD_FUN_CURRENT_COVERAGE_WORKFLOW,
        "coverage_run_id": run_id,
        "coverage_artifact_name": HOOD_FUN_CURRENT_COVERAGE_ARTIFACT,
        "coverage_artifact_digest": artifact_digest,
        "coverage_report_path": HOOD_FUN_CURRENT_COVERAGE_REPORT_PATH,
        "coverage_report_sha256": report_sha,
        "planner_run_id": planner_id,
        "planner_artifact_digest": planner_digest,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "complete_source_ids_before": expected_before,
        "complete_source_ids_after_if_promoted": expected_after,
        "promotion_workflow": SOURCE_COVERAGE_PROMOTION_WORKFLOW,
        "promotion_generated_inputs": generated_inputs,
        "promotion_review_required": True,
        "promotion_dispatched": False,
        "proposal_created": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }


def validate_phase2_hood_fun_current_promotion_review_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate immutable 8/14 hood.fun current review handoff."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE2_HOOD_FUN_CURRENT_PROMOTION_REVIEW_VERSION
    ):
        raise ValueError("hood.fun current promotion review version changed")
    control_run_id = _positive_run_id(
        row.get("promotion_review_control_run_id"),
        label="hood.fun current review control run ID",
    )
    prior_run_id = _positive_run_id(
        row.get("trench_today_ledger_approval_run_id"),
        label="trench.today ledger approval run ID",
    )
    coverage_run_id = _positive_run_id(
        row.get("coverage_run_id"),
        label="hood.fun current coverage run ID",
    )
    planner_run_id = _positive_run_id(
        row.get("planner_run_id"),
        label="hood.fun current planner run ID",
    )
    prior_digest = _artifact_digest(
        row.get("trench_today_ledger_approval_artifact_digest"),
        label="trench.today ledger approval artifact digest",
    )
    coverage_digest = _artifact_digest(
        row.get("coverage_artifact_digest"),
        label="hood.fun current coverage artifact digest",
    )
    planner_digest = _artifact_digest(
        row.get("planner_artifact_digest"),
        label="hood.fun current planner artifact digest",
    )
    report_sha = _sha256(
        row.get("coverage_report_sha256"),
        label="hood.fun current coverage report",
    )
    ledger_sha = _sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="hood.fun current canonical ledger",
    )
    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError("hood.fun current review execution branch is empty")
    head_sha = _commit_sha(
        row.get("execution_head_sha"),
        label="hood.fun current review execution head",
    )
    if row.get("source_id") != "hood_fun_current":
        raise ValueError("hood.fun current review source drift")
    if row.get("coverage_workflow") != HOOD_FUN_CURRENT_COVERAGE_WORKFLOW:
        raise ValueError("hood.fun current coverage workflow drift")
    if row.get("coverage_artifact_name") != HOOD_FUN_CURRENT_COVERAGE_ARTIFACT:
        raise ValueError("hood.fun current artifact-name drift")
    if row.get("coverage_report_path") != HOOD_FUN_CURRENT_COVERAGE_REPORT_PATH:
        raise ValueError("hood.fun current report-path drift")
    if row.get("promotion_workflow") != SOURCE_COVERAGE_PROMOTION_WORKFLOW:
        raise ValueError("hood.fun current promotion workflow drift")
    expected_inputs = {
        "coverage_run_id": str(coverage_run_id),
        "coverage_artifact_name": HOOD_FUN_CURRENT_COVERAGE_ARTIFACT,
        "expected_artifact_digest": coverage_digest,
        "coverage_report_path": HOOD_FUN_CURRENT_COVERAGE_REPORT_PATH,
        "expected_report_sha256": report_sha,
        "expected_source_id": "hood_fun_current",
    }
    if row.get("promotion_generated_inputs") != expected_inputs:
        raise ValueError("hood.fun current promotion generated-input drift")
    if row.get("promotion_review_required") is not True:
        raise ValueError("hood.fun current promotion lost review requirement")
    for field in (
        "promotion_dispatched",
        "proposal_created",
        "canonical_coverage_ledger_mutated",
        "canonical_ledger_write_authorized",
    ):
        if row.get(field) is not False:
            raise ValueError(
                f"hood.fun current review violates read-only field {field}"
            )
    return {
        **row,
        "promotion_review_control_run_id": control_run_id,
        "trench_today_ledger_approval_run_id": prior_run_id,
        "trench_today_ledger_approval_artifact_digest": prior_digest,
        "coverage_run_id": coverage_run_id,
        "coverage_artifact_digest": coverage_digest,
        "coverage_report_sha256": report_sha,
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "promotion_generated_inputs": expected_inputs,
        "promotion_review_required": True,
        "promotion_dispatched": False,
        "proposal_created": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }


def validate_phase2_hood_fun_current_promotion_proposal_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate hood.fun current proposal before ledger approval."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE2_HOOD_FUN_CURRENT_PROMOTION_PROPOSAL_VERSION
    ):
        raise ValueError("hood.fun current promotion proposal receipt version changed")
    control_run_id = _positive_run_id(
        row.get("promotion_proposal_control_run_id"),
        label="hood.fun current proposal control run ID",
    )
    review_run_id = _positive_run_id(
        row.get("promotion_review_run_id"),
        label="hood.fun current review run ID",
    )
    dispatcher_run_id = _positive_run_id(
        row.get("node_dispatch_control_run_id"),
        label="hood.fun current promotion dispatcher run ID",
    )
    promotion_run_id = _positive_run_id(
        row.get("promotion_run_id"),
        label="hood.fun current promotion run ID",
    )
    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError("hood.fun current proposal execution branch is empty")
    head_sha = _commit_sha(
        row.get("execution_head_sha"),
        label="hood.fun current proposal execution head",
    )
    review_digest = _artifact_digest(
        row.get("promotion_review_artifact_digest"),
        label="hood.fun current review artifact digest",
    )
    promotion_digest = _artifact_digest(
        row.get("promotion_artifact_digest"),
        label="hood.fun current promotion artifact digest",
    )
    handoff_sha = _sha256(
        row.get("promotion_handoff_sha256"),
        label="hood.fun current promotion handoff",
    )
    proposed_sha = _sha256(
        row.get("proposed_ledger_sha256"),
        label="hood.fun current proposed ledger",
    )
    base_sha = _sha256(
        row.get("base_ledger_sha256"),
        label="hood.fun current proposal base ledger",
    )
    expected_before = [
        "doppler",
        "flap",
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
        "trench_today",
    ]
    expected_after = sorted(expected_before + ["hood_fun_current"])
    if row.get("source_id") != "hood_fun_current":
        raise ValueError("hood.fun current proposal source identity drift")
    if row.get("promotion_workflow") != SOURCE_COVERAGE_PROMOTION_WORKFLOW:
        raise ValueError("hood.fun current proposal workflow identity drift")
    if row.get("complete_source_ids_before") != expected_before:
        raise ValueError("hood.fun current proposal before-set drift")
    if row.get("complete_source_ids_after") != expected_after:
        raise ValueError("hood.fun current proposal after-set drift")
    if row.get("phase2_universe_coverage_complete") is not False:
        raise ValueError("hood.fun current proposal unexpectedly closes Phase 2")
    if row.get("proposal_created") is not True:
        raise ValueError("hood.fun current proposal lacks proposal proof")
    if row.get("proposal_validated") is not True:
        raise ValueError("hood.fun current proposal lacks validation proof")
    if row.get("canonical_coverage_ledger_mutated") is not False:
        raise ValueError("hood.fun current proposal unexpectedly mutates ledger")
    if row.get("ledger_commit_authorized") is not False:
        raise ValueError("hood.fun current proposal authorizes ledger commit")
    if row.get("ledger_commit_approval_input") != "apply_proposed_ledger":
        raise ValueError("hood.fun current proposal ledger approval input drift")
    if row.get("ledger_commit_approval_value_supplied") is not False:
        raise ValueError("hood.fun current proposal already supplies approval")
    expected_generated = {
        "promotion_run_id": str(promotion_run_id),
        "expected_artifact_digest": promotion_digest,
        "expected_handoff_sha256": handoff_sha,
        "expected_proposed_ledger_sha256": proposed_sha,
        "expected_source_id": "hood_fun_current",
    }
    if row.get("ledger_commit_generated_inputs") != expected_generated:
        raise ValueError("hood.fun current proposal ledger-commit input drift")
    return {
        **row,
        "promotion_proposal_control_run_id": control_run_id,
        "promotion_review_run_id": review_run_id,
        "node_dispatch_control_run_id": dispatcher_run_id,
        "promotion_run_id": promotion_run_id,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "promotion_review_artifact_digest": review_digest,
        "promotion_artifact_digest": promotion_digest,
        "promotion_handoff_sha256": handoff_sha,
        "proposed_ledger_sha256": proposed_sha,
        "base_ledger_sha256": base_sha,
        "source_id": "hood_fun_current",
        "ledger_commit_generated_inputs": expected_generated,
        "ledger_commit_approval_input": "apply_proposed_ledger",
        "ledger_commit_approval_value_supplied": False,
        "proposal_created": True,
        "proposal_validated": True,
        "canonical_coverage_ledger_mutated": False,
        "ledger_commit_authorized": False,
    }


def validate_phase2_hood_fun_current_ledger_commit_receipt(
    receipt: Mapping[str, object],
    *,
    expected_promotion_run_id: int,
    expected_promotion_artifact_digest: str,
    expected_promotion_handoff_sha256: str,
    expected_proposed_ledger_sha256: str,
) -> dict:
    """Validate approved hood.fun current canonical-ledger write."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        "phase2-source-coverage-ledger-commit-v1"
    ):
        raise ValueError("hood.fun current ledger commit receipt version changed")
    if row.get("source_id") != "hood_fun_current":
        raise ValueError("hood.fun current ledger commit source identity drift")
    promotion_run_id = _positive_run_id(
        row.get("promotion_run_id"),
        label="hood.fun current ledger promotion run ID",
    )
    if promotion_run_id != int(expected_promotion_run_id):
        raise ValueError("hood.fun current ledger commit promotion run drift")
    if row.get("promotion_artifact_name") != (
        "phase2-source-coverage-promotion-hood_fun_current"
    ):
        raise ValueError("hood.fun current ledger commit artifact-name drift")
    artifact_digest = _artifact_digest(
        row.get("promotion_artifact_digest"),
        label="hood.fun current promotion artifact digest",
    )
    if artifact_digest != _artifact_digest(
        expected_promotion_artifact_digest,
        label="expected hood.fun current promotion artifact digest",
    ):
        raise ValueError("hood.fun current ledger commit promotion artifact drift")
    handoff_sha = _sha256(
        row.get("promotion_handoff_sha256"),
        label="hood.fun current promotion handoff",
    )
    if handoff_sha != _sha256(
        expected_promotion_handoff_sha256,
        label="expected hood.fun current promotion handoff",
    ):
        raise ValueError("hood.fun current ledger commit promotion handoff drift")
    proposed_sha = _sha256(
        row.get("proposed_ledger_sha256"),
        label="hood.fun current proposed ledger",
    )
    if proposed_sha != _sha256(
        expected_proposed_ledger_sha256,
        label="expected hood.fun current proposed ledger",
    ):
        raise ValueError("hood.fun current ledger commit proposed-ledger drift")
    base_sha = _sha256(
        row.get("base_ledger_sha256"),
        label="hood.fun current base ledger",
    )
    expected_before = [
        "doppler",
        "flap",
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
        "trench_today",
    ]
    expected_after = sorted(expected_before + ["hood_fun_current"])
    if row.get("complete_source_ids_before") != expected_before:
        raise ValueError("hood.fun current ledger commit before-set drift")
    if row.get("complete_source_ids_after") != expected_after:
        raise ValueError("hood.fun current ledger commit after-set drift")
    if row.get("phase2_universe_coverage_complete") is not False:
        raise ValueError("hood.fun current commit unexpectedly closes Phase 2")
    commit_sha = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="hood.fun current canonical ledger commit",
    )
    if row.get("explicit_approval") is not True:
        raise ValueError("hood.fun current ledger commit lacks explicit approval")
    if row.get("canonical_ledger_mutated") is not True:
        raise ValueError("hood.fun current ledger commit lacks mutation proof")
    return {
        **row,
        "promotion_run_id": promotion_run_id,
        "promotion_artifact_digest": artifact_digest,
        "promotion_handoff_sha256": handoff_sha,
        "base_ledger_sha256": base_sha,
        "proposed_ledger_sha256": proposed_sha,
        "canonical_ledger_commit_sha": commit_sha,
        "explicit_approval": True,
        "canonical_ledger_mutated": True,
    }


def validate_phase2_hood_fun_current_post_commit_frontier(
    execution_plan: Mapping[str, object],
    verified_receipts: Mapping[str, object],
    dispatch_plan: Mapping[str, object],
) -> dict:
    """Freeze exact 9/14 frontier after hood.fun current is canonical."""

    execution = dict(execution_plan)
    verified = dict(verified_receipts)
    dispatch = dict(dispatch_plan)
    expected_complete = [
        "doppler",
        "flap",
        "hood_fun_current",
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
        "trench_today",
    ]
    if execution.get("canonical_complete_source_ids") != expected_complete:
        raise ValueError("hood.fun current post-commit canonical source set drift")
    if int(execution.get("complete_sources", -1)) != 9:
        raise ValueError("hood.fun current post-commit source count drift")
    if int(execution.get("incomplete_sources", -1)) != 5:
        raise ValueError("hood.fun current post-commit incomplete count drift")
    if execution.get("phase2_universe_coverage_complete") is not False:
        raise ValueError("hood.fun current post-commit unexpectedly closes Phase 2")

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
        "coverage:doppler",
        "coverage:flap",
        "coverage:trench_today",
        "coverage:hood_fun_current",
    }
    removed = canonical_coverages | {
        "promote:pools_fun",
        "promote:pools_trade_instant",
        "promote:pools_trade_lbp",
        "promote:doppler",
        "promote:flap",
        "promote:trench_today",
        "promote:hood_fun_current",
    }
    expected_active = pre_frontier - canonical_coverages
    if set(execution.get("completed_node_ids") or []) != expected_active:
        raise ValueError("hood.fun current post-commit active completion drift")
    if set(execution.get("ignored_completed_node_ids") or []) != removed:
        raise ValueError("hood.fun current post-commit ignored-completion drift")
    if execution.get("ready_to_dispatch_node_ids") != [
        "promote:hood_fun_previous"
    ]:
        raise ValueError("hood.fun current post-commit next promotion drift")
    if execution.get("awaiting_explicit_approval_node_ids") != []:
        raise ValueError("hood.fun current post-commit unexpected approvals")
    if execution.get("ledger_commit_approval_node_ids") != []:
        raise ValueError("hood.fun current post-commit unexpected ledger approval")

    expected_verified = pre_frontier | {
        "promote:pools_fun",
        "promote:pools_trade_instant",
        "promote:pools_trade_lbp",
        "promote:doppler",
        "promote:flap",
        "promote:trench_today",
        "promote:hood_fun_current",
    }
    if set(verified.get("completed_node_ids") or []) != expected_verified:
        raise ValueError("hood.fun current post-commit verified completion drift")
    controls = verified.get("node_dispatch_run_ids_consumed")
    if (
        not isinstance(controls, list)
        or len(controls) != 47
        or len(set(int(value) for value in controls)) != 47
    ):
        raise ValueError(
            "hood.fun current post-commit requires exactly 47 dispatcher receipts"
        )
    if verified.get("all_runs_current_or_ledger_only_ancestors") is not True:
        raise ValueError("hood.fun current post-commit lacks lineage proof")

    rows = dispatch.get("nodes")
    if not isinstance(rows, list) or len(rows) != 1:
        raise ValueError("hood.fun current post-commit dispatch row count drift")
    row = dict(rows[0])
    if row.get("node_id") != "promote:hood_fun_previous":
        raise ValueError("hood.fun current post-commit dispatch node drift")
    if row.get("workflow") != SOURCE_COVERAGE_PROMOTION_WORKFLOW:
        raise ValueError("hood.fun current post-commit promotion workflow drift")
    if set(dict(row.get("run_id_inputs") or {})) != {"coverage_run_id"}:
        raise ValueError("hood.fun previous promotion coverage-run binding drift")
    expected_manual = sorted([
        "coverage_artifact_name",
        "coverage_report_path",
        "expected_artifact_digest",
        "expected_report_sha256",
        "expected_source_id",
    ])
    actual_manual = sorted(
        str(value) for value in row.get("remaining_manual_inputs") or []
    )
    if actual_manual != expected_manual:
        raise ValueError("hood.fun previous promotion manual-input drift")
    return {
        "version": "phase2-hood-fun-current-post-commit-frontier-v1",
        "canonical_complete_source_ids": expected_complete,
        "complete_sources": 9,
        "incomplete_sources": 5,
        "active_completed_execution_nodes": len(expected_active),
        "ignored_completed_node_ids": sorted(removed),
        "node_dispatch_control_runs_consumed": len(controls),
        "next_promotion_node_id": "promote:hood_fun_previous",
        "next_promotion_manual_inputs": actual_manual,
        "automatic_acquisition_complete": True,
        "canonical_ledger_advanced": True,
        "phase2_universe_coverage_complete": False,
    }



def validate_phase2_hood_fun_current_ledger_approved_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate immutable 9/14 handoff after hood.fun current commit."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        "phase2-hood-fun-current-ledger-approved-receipt-v1"
    ):
        raise ValueError(
            "hood.fun current approved-ledger receipt version changed"
        )
    control_run_id = _positive_run_id(
        row.get("ledger_approval_control_run_id"),
        label="hood.fun current ledger approval control run ID",
    )
    proposal_run_id = _positive_run_id(
        row.get("promotion_proposal_run_id"),
        label="hood.fun current proposal run ID",
    )
    ledger_run_id = _positive_run_id(
        row.get("ledger_commit_run_id"),
        label="hood.fun current ledger commit run ID",
    )
    selector_run_id = _positive_run_id(
        row.get("selector_run_id"),
        label="hood.fun current selector run ID",
    )
    planner_run_id = _positive_run_id(
        row.get("planner_run_id"),
        label="hood.fun current post-commit planner run ID",
    )
    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError("hood.fun current approved-ledger branch is empty")
    approval_head = _commit_sha(
        row.get("approval_execution_head_sha"),
        label="hood.fun current approval execution head",
    )
    proposal_digest = _artifact_digest(
        row.get("promotion_proposal_artifact_digest"),
        label="hood.fun current proposal artifact digest",
    )
    ledger_digest = _artifact_digest(
        row.get("ledger_commit_artifact_digest"),
        label="hood.fun current ledger commit artifact digest",
    )
    commit_sha = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="hood.fun current canonical ledger commit",
    )
    base_sha = _sha256(
        row.get("base_ledger_sha256"),
        label="hood.fun current approved base ledger",
    )
    canonical_sha = _sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="hood.fun current approved canonical ledger",
    )
    planner_digest = _artifact_digest(
        row.get("planner_artifact_digest"),
        label="hood.fun current post-commit planner artifact digest",
    )
    controls_raw = row.get("node_dispatch_control_run_ids_consumed")
    if not isinstance(controls_raw, list):
        raise ValueError(
            "hood.fun current approved control-run list is missing"
        )
    controls = [int(value) for value in controls_raw]
    if (
        len(controls) != 47
        or len(set(controls)) != 47
        or min(controls) <= 0
    ):
        raise ValueError(
            "hood.fun current approved handoff requires exactly 47 control runs"
        )
    expected_complete = [
        "doppler",
        "flap",
        "hood_fun_current",
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
        "trench_today",
    ]
    if row.get("canonical_complete_source_ids") != expected_complete:
        raise ValueError(
            "hood.fun current approved canonical source set drift"
        )
    if row.get("next_promotion_node_id") != "promote:hood_fun_previous":
        raise ValueError("hood.fun current approved next promotion drift")
    if row.get("human_approval_input") != "apply_hood_fun_current_ledger":
        raise ValueError(
            "hood.fun current approved human-input identity drift"
        )
    if row.get("human_approval_value") is not True:
        raise ValueError(
            "hood.fun current approved receipt lacks affirmative approval"
        )
    if row.get("canonical_ledger_mutated") is not True:
        raise ValueError(
            "hood.fun current approved receipt lacks ledger mutation"
        )
    if row.get("automatic_acquisition_complete") is not True:
        raise ValueError(
            "hood.fun current approved receipt lost acquisition proof"
        )
    if row.get("phase2_universe_coverage_complete") is not False:
        raise ValueError(
            "hood.fun current approved receipt unexpectedly closes Phase 2"
        )
    return {
        **row,
        "ledger_approval_control_run_id": control_run_id,
        "execution_branch": branch,
        "approval_execution_head_sha": approval_head,
        "promotion_proposal_run_id": proposal_run_id,
        "promotion_proposal_artifact_digest": proposal_digest,
        "ledger_commit_run_id": ledger_run_id,
        "ledger_commit_artifact_digest": ledger_digest,
        "canonical_ledger_commit_sha": commit_sha,
        "base_ledger_sha256": base_sha,
        "canonical_coverage_ledger_sha256": canonical_sha,
        "node_dispatch_control_run_ids_consumed": sorted(controls),
        "selector_run_id": selector_run_id,
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "canonical_complete_source_ids": expected_complete,
        "next_promotion_node_id": "promote:hood_fun_previous",
        "human_approval_input": "apply_hood_fun_current_ledger",
        "human_approval_value": True,
        "canonical_ledger_mutated": True,
        "automatic_acquisition_complete": True,
        "phase2_universe_coverage_complete": False,
    }
