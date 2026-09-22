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
