"""Validation policy for applying Phase-2 coverage-ledger proposals."""

from __future__ import annotations

from typing import Iterable, Mapping

from hlp.data.phase2_coverage import (
    apply_phase2_source_coverage_report,
    validate_phase2_coverage_ledger,
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
