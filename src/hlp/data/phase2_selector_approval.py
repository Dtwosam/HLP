"""Read-only approval handoff for the direct-market selector freeze."""

from __future__ import annotations

from typing import Mapping

from hlp.data.direct_selector import (
    DIRECT_SELECTOR_EVIDENCE_VERSION,
    DIRECT_SELECTOR_VERSION,
    DIRECT_SOURCE_IDS,
)
from hlp.data.market_quality import MARKET_SELECTION_CANDIDATE_VERSION


PHASE2_SELECTOR_APPROVAL_HANDOFF_VERSION = (
    "phase2-direct-selector-approval-handoff-v1"
)
SELECTOR_EVIDENCE_ARTIFACT_NAME = (
    "phase2-direct-market-quality-evidence"
)
SELECTOR_FREEZE_WORKFLOW = "phase2-direct-market-selector-freeze.yml"


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower().removeprefix("sha256:")
    if len(text) != 64:
        raise ValueError(f"{label} SHA-256 is invalid")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} SHA-256 is invalid") from exc
    return text


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


def build_phase2_selector_approval_handoff(
    evidence_handoff: Mapping[str, object],
    *,
    evidence_run_id: int,
    evidence_artifact_digest: str,
    evidence_handoff_sha256: str,
    final_file_sha256: Mapping[str, object],
) -> dict:
    """Validate exact research evidence without making the freeze decision."""

    evidence = dict(evidence_handoff)
    if str(evidence.get("version") or "") != DIRECT_SELECTOR_EVIDENCE_VERSION:
        raise ValueError("direct selector evidence handoff version changed")
    if evidence.get("selector_freeze_ready") is not False:
        raise ValueError(
            "direct selector research evidence unexpectedly claims freeze readiness"
        )
    if evidence.get("source_coverage_complete") is not False:
        raise ValueError(
            "direct selector research evidence unexpectedly closes coverage"
        )

    run_id = _positive_run_id(
        evidence_run_id,
        label="direct selector evidence run ID",
    )
    artifact_digest = _artifact_digest(
        evidence_artifact_digest,
        label="direct selector evidence artifact digest",
    )
    handoff_sha = _sha256(
        evidence_handoff_sha256,
        label="direct selector evidence handoff",
    )

    if int(evidence.get("chain_id", 0)) != 4663:
        raise ValueError("direct selector evidence chain ID changed")
    snapshot = int(evidence.get("snapshot_head_block", -1))
    sample_tokens = int(evidence.get("sample_tokens", 0))
    sample_markets = int(evidence.get("sample_markets", 0))
    if snapshot <= 0:
        raise ValueError("direct selector evidence snapshot is invalid")
    if sample_tokens <= 0 or sample_markets <= sample_tokens:
        raise ValueError(
            "direct selector evidence lacks competing-market coverage"
        )

    upstream_run_fields = (
        "quote_run_id",
        "registry_run_id",
        "cohort_run_id",
        "v3_initialize_run_id",
        "v3_swap_run_id",
        "v4_initialize_run_id",
        "v4_swap_run_id",
        "supply_delta_run_id",
    )
    upstream_runs = {
        field: _positive_run_id(
            evidence.get(field),
            label=f"direct selector evidence {field}",
        )
        for field in upstream_run_fields
    }

    evidence_hash_fields = (
        "plan_sha256",
        "quote_registry_sha256",
        "quote_decimals_sha256",
        "quote_feed_specs_sha256",
        "trace_sha256",
        "candidate_series_sha256",
        "market_quality_report_sha256",
    )
    hashes = {
        field: _sha256(
            evidence.get(field),
            label=f"direct selector evidence {field}",
        )
        for field in evidence_hash_fields
    }

    point_sha_raw = evidence.get("point_sha256")
    if not isinstance(point_sha_raw, Mapping):
        raise ValueError("direct selector point SHA map is missing")
    if set(map(str, point_sha_raw)) != DIRECT_SOURCE_IDS:
        raise ValueError("direct selector point SHA source set changed")
    point_sha = {
        str(source_id): _sha256(
            digest,
            label=f"direct selector point {source_id}",
        )
        for source_id, digest in point_sha_raw.items()
    }

    files = {
        str(name): _sha256(
            digest,
            label=f"direct selector final file {name}",
        )
        for name, digest in final_file_sha256.items()
    }
    expected_files = {
        "direct-market-quality-trace.jsonl": hashes["trace_sha256"],
        "direct-market-candidate-series.jsonl": hashes[
            "candidate_series_sha256"
        ],
        "direct-market-quality-report.json": hashes[
            "market_quality_report_sha256"
        ],
    }
    if files != expected_files:
        raise ValueError("direct selector final evidence file SHA drift")

    report = evidence.get("market_quality_report")
    if not isinstance(report, Mapping):
        raise ValueError("direct selector market-quality report is missing")
    if report.get("selection_rule_frozen") is not False:
        raise ValueError(
            "direct selector evidence report already freezes selection"
        )
    trace = report.get("causal_trace")
    if not isinstance(trace, Mapping):
        raise ValueError("direct selector causal trace summary is missing")
    multi_market_snapshots = int(
        trace.get("multi_market_snapshots", 0)
    )
    trace_tokens = int(trace.get("tokens", 0))
    if multi_market_snapshots <= 0 or trace_tokens <= 0:
        raise ValueError(
            "direct selector evidence lacks usable competing snapshots"
        )

    candidate = report.get("candidate_canonical_series")
    if not isinstance(candidate, Mapping):
        raise ValueError(
            "direct selector candidate canonical summary is missing"
        )
    if str(
        candidate.get("selection_policy_candidate_version") or ""
    ) != MARKET_SELECTION_CANDIDATE_VERSION:
        raise ValueError(
            "direct selector candidate policy version changed"
        )
    if candidate.get("selection_rule_frozen") is not False:
        raise ValueError(
            "direct selector candidate unexpectedly freezes selection"
        )
    if candidate.get(
        "cross_pool_volume_double_counting_allowed"
    ) is not False:
        raise ValueError(
            "direct selector candidate permits cross-pool volume double counting"
        )
    candidate_points = int(candidate.get("points", 0))
    if candidate_points <= 0:
        raise ValueError("direct selector candidate series has no points")

    remaining_steps = evidence.get("remaining_steps")
    if not isinstance(remaining_steps, list):
        raise ValueError("direct selector evidence remaining steps are missing")
    normalized_steps = [str(value) for value in remaining_steps]
    if not any(
        "explicit" in value.lower() and "freeze" in value.lower()
        for value in normalized_steps
    ):
        raise ValueError(
            "direct selector evidence no longer preserves explicit freeze review"
        )

    return {
        "version": PHASE2_SELECTOR_APPROVAL_HANDOFF_VERSION,
        "chain_id": 4663,
        "snapshot_head_block": snapshot,
        "selector_version": DIRECT_SELECTOR_VERSION,
        "selection_policy_candidate_version": (
            MARKET_SELECTION_CANDIDATE_VERSION
        ),
        "selector_freeze_workflow": SELECTOR_FREEZE_WORKFLOW,
        "evidence_run_id": run_id,
        "evidence_artifact_name": SELECTOR_EVIDENCE_ARTIFACT_NAME,
        "evidence_artifact_digest": artifact_digest,
        "evidence_handoff_sha256": handoff_sha,
        "sample_tokens": sample_tokens,
        "sample_markets": sample_markets,
        "multi_market_snapshots": multi_market_snapshots,
        "trace_tokens": trace_tokens,
        "candidate_points": candidate_points,
        "upstream_run_ids": dict(sorted(upstream_runs.items())),
        "evidence_sha256": dict(sorted(hashes.items())),
        "point_sha256": dict(sorted(point_sha.items())),
        "final_file_sha256": dict(sorted(files.items())),
        "remaining_research_steps": normalized_steps,
        "selector_freeze_generated_inputs": {
            "evidence_run_id": str(run_id),
            "expected_artifact_digest": artifact_digest,
            "expected_handoff_sha256": handoff_sha,
        },
        "selector_freeze_approval_input": (
            "freeze_active_quote_liquidity_causal_v1"
        ),
        "selector_freeze_approval_value_supplied": False,
        "approval_required": True,
        "selector_freeze_ready_from_evidence": False,
        "selector_approval_performed": False,
        "selector_workflow_dispatched": False,
        "coverage_promotion_performed": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
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


def validate_phase2_selector_approval_handoff_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate the immutable read-only handoff before human approval."""

    row = dict(receipt)
    if str(row.get("version") or "") != PHASE2_SELECTOR_APPROVAL_HANDOFF_VERSION:
        raise ValueError("direct selector approval handoff version changed")

    control_run_id = _positive_run_id(
        row.get("approval_handoff_control_run_id"),
        label="selector approval handoff control run ID",
    )
    pre_selector_run_id = _positive_run_id(
        row.get("pre_selector_completion_run_id"),
        label="pre-selector completion run ID",
    )
    planner_run_id = _positive_run_id(
        row.get("planner_run_id"),
        label="selector approval planner run ID",
    )
    pre_selector_digest = _artifact_digest(
        row.get("pre_selector_completion_artifact_digest"),
        label="pre-selector completion artifact digest",
    )
    planner_digest = _artifact_digest(
        row.get("planner_artifact_digest"),
        label="selector approval planner artifact digest",
    )

    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError("selector approval handoff execution branch is empty")
    head_sha = _commit_sha(
        row.get("execution_head_sha"),
        label="selector approval handoff execution head",
    )
    ledger_sha = _sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="selector approval handoff coverage ledger",
    )

    if str(row.get("selector_freeze_workflow") or "") != SELECTOR_FREEZE_WORKFLOW:
        raise ValueError("selector approval handoff workflow identity drift")
    evidence_run_id = _positive_run_id(
        row.get("evidence_run_id"),
        label="selector approval evidence run ID",
    )
    evidence_artifact_digest = _artifact_digest(
        row.get("evidence_artifact_digest"),
        label="selector approval evidence artifact digest",
    )
    evidence_handoff_sha = _sha256(
        row.get("evidence_handoff_sha256"),
        label="selector approval evidence handoff",
    )

    generated = row.get("selector_freeze_generated_inputs")
    if not isinstance(generated, Mapping):
        raise ValueError("selector approval generated input map is missing")
    expected_generated = {
        "evidence_run_id": str(evidence_run_id),
        "expected_artifact_digest": evidence_artifact_digest,
        "expected_handoff_sha256": evidence_handoff_sha,
    }
    if dict(generated) != expected_generated:
        raise ValueError("selector approval generated input map drift")

    if str(row.get("selector_freeze_approval_input") or "") != (
        "freeze_active_quote_liquidity_causal_v1"
    ):
        raise ValueError("selector approval boolean input identity drift")
    if row.get("selector_freeze_approval_value_supplied") is not False:
        raise ValueError("selector approval handoff already supplies approval")
    if row.get("approval_required") is not True:
        raise ValueError("selector approval handoff lost approval requirement")
    if row.get("selector_freeze_ready_from_evidence") is not False:
        raise ValueError("selector approval handoff claims evidence-only readiness")

    for field in (
        "selector_approval_performed",
        "selector_workflow_dispatched",
        "coverage_promotion_performed",
        "canonical_coverage_ledger_mutated",
        "canonical_ledger_write_authorized",
    ):
        if row.get(field) is not False:
            raise ValueError(
                f"selector approval handoff violates read-only field {field}"
            )

    return {
        **row,
        "approval_handoff_control_run_id": control_run_id,
        "pre_selector_completion_run_id": pre_selector_run_id,
        "pre_selector_completion_artifact_digest": pre_selector_digest,
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "selector_freeze_workflow": SELECTOR_FREEZE_WORKFLOW,
        "evidence_run_id": evidence_run_id,
        "evidence_artifact_digest": evidence_artifact_digest,
        "evidence_handoff_sha256": evidence_handoff_sha,
        "selector_freeze_generated_inputs": expected_generated,
        "selector_freeze_approval_value_supplied": False,
        "approval_required": True,
        "selector_approval_performed": False,
        "selector_workflow_dispatched": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }



def validate_phase2_selector_approved_freeze_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate the immutable handoff after explicit selector approval."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        "phase2-direct-selector-approved-freeze-receipt-v1"
    ):
        raise ValueError("approved selector freeze receipt version changed")

    control_run_id = _positive_run_id(
        row.get("approved_freeze_control_run_id"),
        label="approved selector freeze control run ID",
    )
    handoff_run_id = _positive_run_id(
        row.get("approval_handoff_run_id"),
        label="selector approval handoff run ID",
    )
    pre_selector_run_id = _positive_run_id(
        row.get("pre_selector_completion_run_id"),
        label="pre-selector completion run ID",
    )
    selector_run_id = _positive_run_id(
        row.get("selector_run_id"),
        label="selector freeze run ID",
    )
    planner_run_id = _positive_run_id(
        row.get("planner_run_id"),
        label="post-selector planner run ID",
    )

    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError("approved selector freeze execution branch is empty")
    head_sha = _commit_sha(
        row.get("execution_head_sha"),
        label="approved selector freeze execution head",
    )
    ledger_sha = _sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="approved selector freeze coverage ledger",
    )
    handoff_digest = _artifact_digest(
        row.get("approval_handoff_artifact_digest"),
        label="selector approval handoff artifact digest",
    )
    pre_selector_digest = _artifact_digest(
        row.get("pre_selector_completion_artifact_digest"),
        label="pre-selector completion artifact digest",
    )
    selector_digest = _artifact_digest(
        row.get("selector_artifact_digest"),
        label="selector freeze artifact digest",
    )
    planner_digest = _artifact_digest(
        row.get("planner_artifact_digest"),
        label="post-selector planner artifact digest",
    )
    descriptor_sha = _sha256(
        row.get("selector_descriptor_sha256"),
        label="selector freeze descriptor",
    )
    evidence_run_id = _positive_run_id(
        row.get("evidence_run_id"),
        label="approved selector evidence run ID",
    )
    evidence_digest = _artifact_digest(
        row.get("evidence_artifact_digest"),
        label="approved selector evidence artifact digest",
    )
    evidence_handoff_sha = _sha256(
        row.get("evidence_handoff_sha256"),
        label="approved selector evidence handoff",
    )

    if str(row.get("selector_version") or "") != "active-quote-liquidity-causal-v1":
        raise ValueError("approved selector frozen version drift")
    if str(row.get("human_approval_input") or "") != "approve_freeze":
        raise ValueError("approved selector human-approval input drift")
    if row.get("human_approval_value") is not True:
        raise ValueError("approved selector receipt lacks affirmative approval")
    if row.get("selector_approval_performed") is not True:
        raise ValueError("approved selector receipt lacks approval proof")
    if row.get("selector_freeze_completed") is not True:
        raise ValueError("approved selector receipt lacks freeze completion")

    controls = row.get("node_dispatch_control_run_ids_consumed")
    if not isinstance(controls, list):
        raise ValueError("approved selector prior control-run list is missing")
    normalized_controls = [int(value) for value in controls]
    if (
        len(normalized_controls) != 35
        or len(set(normalized_controls)) != 35
        or min(normalized_controls) <= 0
    ):
        raise ValueError(
            "approved selector receipt requires exactly 35 prior control runs"
        )

    auto_nodes = row.get("auto_node_ids")
    expected_auto = [
        "shared:direct_source_population",
        "coverage:trench_today",
    ]
    if auto_nodes != expected_auto:
        raise ValueError("approved selector post-freeze auto-node drift")
    manual_nodes = row.get("manual_promotion_node_ids")
    if manual_nodes != ["promote:pools_fun"]:
        raise ValueError("approved selector promotion-hold drift")

    for field in (
        "coverage_promotion_performed",
        "canonical_coverage_ledger_mutated",
        "canonical_ledger_write_authorized",
    ):
        if row.get(field) is not False:
            raise ValueError(
                f"approved selector receipt violates {field}"
            )

    return {
        **row,
        "approved_freeze_control_run_id": control_run_id,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "approval_handoff_run_id": handoff_run_id,
        "approval_handoff_artifact_digest": handoff_digest,
        "pre_selector_completion_run_id": pre_selector_run_id,
        "pre_selector_completion_artifact_digest": pre_selector_digest,
        "selector_run_id": selector_run_id,
        "selector_artifact_digest": selector_digest,
        "selector_descriptor_sha256": descriptor_sha,
        "evidence_run_id": evidence_run_id,
        "evidence_artifact_digest": evidence_digest,
        "evidence_handoff_sha256": evidence_handoff_sha,
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "node_dispatch_control_run_ids_consumed": sorted(
            normalized_controls
        ),
        "auto_node_ids": expected_auto,
        "manual_promotion_node_ids": ["promote:pools_fun"],
        "human_approval_value": True,
        "selector_approval_performed": True,
        "selector_freeze_completed": True,
        "coverage_promotion_performed": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }
