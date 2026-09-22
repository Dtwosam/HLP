"""Explicit freeze contract for the direct multi-pool selector."""

from __future__ import annotations

from typing import Mapping

from hlp.data.market_quality import MARKET_SELECTION_CANDIDATE_VERSION


DIRECT_SELECTOR_EVIDENCE_VERSION = (
    "phase2-direct-market-quality-evidence-v2"
)
DIRECT_SELECTOR_VERSION = "active-quote-liquidity-causal-v1"
DIRECT_SELECTOR_FREEZE_VERSION = "phase2-direct-market-selector-freeze-v1"
DIRECT_SOURCE_IDS = frozenset({
    "direct_uniswap_v3",
    "direct_sushiswap_v3",
    "direct_uniswap_v4",
})


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower().removeprefix("sha256:")
    if len(text) != 64:
        raise ValueError(f"{label} SHA-256 is invalid")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} SHA-256 is invalid") from exc
    return text


def build_direct_selector_freeze(
    evidence_handoff: Mapping[str, object],
    *,
    evidence_run_id: int,
    evidence_artifact_digest: str,
    evidence_handoff_sha256: str,
) -> dict:
    """Freeze the causal active-quote-liquidity selector from exact evidence.

    This function freezes only the selector semantics. It cannot mark any
    direct DEX source historically complete.
    """
    version = str(evidence_handoff.get("version") or "")
    if version != DIRECT_SELECTOR_EVIDENCE_VERSION:
        raise ValueError(
            f"direct selector evidence version changed: {version!r}"
        )
    if evidence_handoff.get("selector_freeze_ready") is not False:
        raise ValueError(
            "direct selector evidence unexpectedly claims freeze readiness"
        )
    if evidence_handoff.get("source_coverage_complete") is not False:
        raise ValueError(
            "direct selector evidence unexpectedly closes source coverage"
        )

    run_id = int(evidence_run_id)
    if run_id <= 0:
        raise ValueError("direct selector evidence run id is invalid")
    artifact_digest = str(evidence_artifact_digest or "").lower()
    if not artifact_digest.startswith("sha256:"):
        raise ValueError(
            "direct selector evidence artifact digest must use sha256:<hex>"
        )
    _sha256(
        artifact_digest,
        label="direct selector evidence artifact",
    )
    handoff_sha = _sha256(
        evidence_handoff_sha256,
        label="direct selector evidence handoff",
    )

    snapshot = int(evidence_handoff.get("snapshot_head_block", -1))
    sample_tokens = int(evidence_handoff.get("sample_tokens", 0))
    sample_markets = int(evidence_handoff.get("sample_markets", 0))
    if snapshot <= 0:
        raise ValueError("direct selector evidence snapshot is invalid")
    if sample_tokens <= 0 or sample_markets <= sample_tokens:
        raise ValueError(
            "direct selector evidence lacks a competing-market sample"
        )

    for field in (
        "plan_sha256",
        "quote_registry_sha256",
        "quote_decimals_sha256",
        "quote_feed_specs_sha256",
        "trace_sha256",
        "candidate_series_sha256",
        "market_quality_report_sha256",
    ):
        _sha256(
            evidence_handoff.get(field),
            label=f"direct selector evidence {field}",
        )

    point_sha256 = evidence_handoff.get("point_sha256")
    if not isinstance(point_sha256, Mapping):
        raise ValueError("direct selector point SHA map is missing")
    if set(map(str, point_sha256)) != DIRECT_SOURCE_IDS:
        raise ValueError("direct selector point SHA source set changed")
    normalized_point_sha = {
        str(source_id): _sha256(
            digest,
            label=f"direct selector point {source_id}",
        )
        for source_id, digest in point_sha256.items()
    }

    report = evidence_handoff.get("market_quality_report")
    if not isinstance(report, Mapping):
        raise ValueError("direct selector market-quality report is missing")
    if report.get("selection_rule_frozen") is not False:
        raise ValueError(
            "direct selector evidence report already freezes selection"
        )

    trace = report.get("causal_trace")
    if not isinstance(trace, Mapping):
        raise ValueError("direct selector causal trace summary is missing")
    if int(trace.get("multi_market_snapshots", 0)) <= 0:
        raise ValueError(
            "direct selector evidence has no competing usable snapshots"
        )
    if int(trace.get("tokens", 0)) <= 0:
        raise ValueError("direct selector evidence trace has no tokens")

    candidate = report.get("candidate_canonical_series")
    if not isinstance(candidate, Mapping):
        raise ValueError(
            "direct selector candidate canonical summary is missing"
        )
    if (
        str(candidate.get("selection_policy_candidate_version") or "")
        != MARKET_SELECTION_CANDIDATE_VERSION
    ):
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
    if int(candidate.get("points", 0)) <= 0:
        raise ValueError("direct selector candidate series has no points")

    return {
        "version": DIRECT_SELECTOR_FREEZE_VERSION,
        "chain_id": int(evidence_handoff.get("chain_id", 0)),
        "snapshot_head_block": snapshot,
        "selector_version": DIRECT_SELECTOR_VERSION,
        "selection_policy_candidate_version": (
            MARKET_SELECTION_CANDIDATE_VERSION
        ),
        "selection_metric": "active_quote_liquidity_usd",
        "selection_rule": (
            "highest causal active quote-side USD liquidity"
        ),
        "tie_break_rule": "stable market_id ascending",
        "state_semantics": "latest already-observed usable market state",
        "emission_rule": (
            "emit only when selected market updates or becomes leader"
        ),
        "canonical_volume_policy": "selected market only",
        "cross_pool_volume_double_counting_allowed": False,
        "evidence_run_id": run_id,
        "evidence_artifact_name": (
            "phase2-direct-market-quality-evidence"
        ),
        "evidence_artifact_digest": artifact_digest,
        "evidence_handoff_sha256": handoff_sha,
        "plan_sha256": _sha256(
            evidence_handoff["plan_sha256"],
            label="direct selector evidence plan",
        ),
        "trace_sha256": _sha256(
            evidence_handoff["trace_sha256"],
            label="direct selector evidence trace",
        ),
        "candidate_series_sha256": _sha256(
            evidence_handoff["candidate_series_sha256"],
            label="direct selector evidence candidate series",
        ),
        "market_quality_report_sha256": _sha256(
            evidence_handoff["market_quality_report_sha256"],
            label="direct selector evidence report",
        ),
        "point_sha256": dict(sorted(normalized_point_sha.items())),
        "sample_tokens": sample_tokens,
        "sample_markets": sample_markets,
        "multi_market_snapshots": int(
            trace["multi_market_snapshots"]
        ),
        "candidate_points": int(candidate["points"]),
        "selection_rule_frozen": True,
        "selector_freeze_ready": True,
        "source_coverage_complete": False,
    }



def validate_direct_selector_freeze(
    descriptor: Mapping[str, object],
    *,
    expected_evidence_run_id: int,
    expected_evidence_artifact_digest: str,
    expected_evidence_handoff_sha256: str,
) -> dict:
    """Validate an immutable selector-freeze descriptor after workflow success."""

    row = dict(descriptor)
    if str(row.get("version") or "") != DIRECT_SELECTOR_FREEZE_VERSION:
        raise ValueError("direct selector freeze version changed")
    if int(row.get("chain_id", 0)) != 4663:
        raise ValueError("direct selector freeze chain ID changed")
    if int(row.get("snapshot_head_block", -1)) <= 0:
        raise ValueError("direct selector freeze snapshot is invalid")
    if str(row.get("selector_version") or "") != DIRECT_SELECTOR_VERSION:
        raise ValueError("direct selector frozen selector version changed")
    if str(row.get("selection_policy_candidate_version") or "") != (
        MARKET_SELECTION_CANDIDATE_VERSION
    ):
        raise ValueError("direct selector frozen candidate policy changed")

    if str(row.get("selection_metric") or "") != "active_quote_liquidity_usd":
        raise ValueError("direct selector frozen metric changed")
    if str(row.get("tie_break_rule") or "") != "stable market_id ascending":
        raise ValueError("direct selector frozen tie-break rule changed")
    if row.get("cross_pool_volume_double_counting_allowed") is not False:
        raise ValueError("direct selector freeze permits cross-pool double counting")
    if row.get("selection_rule_frozen") is not True:
        raise ValueError("direct selector descriptor is not frozen")
    if row.get("selector_freeze_ready") is not True:
        raise ValueError("direct selector descriptor is not freeze-ready")
    if row.get("source_coverage_complete") is not False:
        raise ValueError("direct selector freeze cannot close source coverage")

    run_id = int(row.get("evidence_run_id") or 0)
    if run_id != int(expected_evidence_run_id) or run_id <= 0:
        raise ValueError("direct selector frozen evidence run identity drift")
    artifact_digest = str(row.get("evidence_artifact_digest") or "").lower()
    expected_artifact = str(expected_evidence_artifact_digest or "").lower()
    if artifact_digest != expected_artifact:
        raise ValueError("direct selector frozen evidence artifact drift")
    _sha256(artifact_digest, label="direct selector frozen evidence artifact")

    handoff_sha = _sha256(
        row.get("evidence_handoff_sha256"),
        label="direct selector frozen evidence handoff",
    )
    expected_handoff = _sha256(
        expected_evidence_handoff_sha256,
        label="expected direct selector evidence handoff",
    )
    if handoff_sha != expected_handoff:
        raise ValueError("direct selector frozen evidence handoff drift")

    if int(row.get("sample_tokens", 0)) <= 0:
        raise ValueError("direct selector freeze has no sample tokens")
    if int(row.get("sample_markets", 0)) <= int(row.get("sample_tokens", 0)):
        raise ValueError("direct selector freeze lacks competing markets")
    if int(row.get("multi_market_snapshots", 0)) <= 0:
        raise ValueError("direct selector freeze has no multi-market snapshots")
    if int(row.get("candidate_points", 0)) <= 0:
        raise ValueError("direct selector freeze has no candidate points")

    point_sha = row.get("point_sha256")
    if not isinstance(point_sha, Mapping):
        raise ValueError("direct selector frozen point SHA map is missing")
    if set(map(str, point_sha)) != DIRECT_SOURCE_IDS:
        raise ValueError("direct selector frozen point SHA source set changed")
    normalized_points = {
        str(source_id): _sha256(
            digest,
            label=f"direct selector frozen point {source_id}",
        )
        for source_id, digest in point_sha.items()
    }

    for field in (
        "plan_sha256",
        "trace_sha256",
        "candidate_series_sha256",
        "market_quality_report_sha256",
    ):
        _sha256(row.get(field), label=f"direct selector frozen {field}")

    return {
        **row,
        "evidence_run_id": run_id,
        "evidence_artifact_digest": artifact_digest,
        "evidence_handoff_sha256": handoff_sha,
        "point_sha256": dict(sorted(normalized_points.items())),
        "selection_rule_frozen": True,
        "selector_freeze_ready": True,
        "source_coverage_complete": False,
    }
