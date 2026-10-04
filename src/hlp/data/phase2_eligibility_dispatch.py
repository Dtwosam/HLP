"""Deterministic Phase-2 eligibility dispatch plan after 14/14 coverage."""

from __future__ import annotations

from typing import Mapping


PHASE2_ELIGIBILITY_DISPATCH_PLAN_VERSION = (
    "phase2-eligibility-dispatch-plan-v1"
)
LAUNCHPAD_ELIGIBILITY_WORKFLOW = "phase2-launchpad-eligibility-handoff.yml"
DIRECT_ELIGIBILITY_WORKFLOW = "phase2-direct-eligibility-handoff.yml"

LAUNCHPAD_SOURCES = (
    "pons_v1",
    "pons_v2",
    "pools_fun",
    "pools_trade_instant",
    "pools_trade_lbp",
    "doppler",
    "flap",
    "trench_today",
    "hood_fun_current",
    "hood_fun_previous",
    "noxa",
)
DIRECT_SOURCES = (
    "direct_uniswap_v3",
    "direct_sushiswap_v3",
    "direct_uniswap_v4",
)

LAUNCHPAD_COVERAGE_ARTIFACTS = {
    "pons_v1": "phase2-pons-source-coverage-pons_v1",
    "pons_v2": "phase2-pons-source-coverage-pons_v2",
    "pools_fun": "phase2-pools-fun-source-coverage",
    "pools_trade_instant": "phase2-pools-trade-instant-source-coverage",
    "pools_trade_lbp": "phase2-pools-trade-lbp-source-coverage",
    "doppler": "phase2-doppler-source-coverage",
    "flap": "phase2-flap-source-coverage",
    "trench_today": "phase2-trench-source-coverage",
    "hood_fun_current": "phase2-hoodfun-current-coverage",
    "hood_fun_previous": "phase2-hoodfun-previous-coverage",
    "noxa": "phase2-noxa-source-coverage",
}
LAUNCHPAD_COVERAGE_REPORT_PATHS = {
    "pons_v1": "pons-v1-source-coverage-report.json",
    "pons_v2": "pons-v2-source-coverage-report.json",
    "pools_fun": "pools-fun-source-coverage-report.json",
    "pools_trade_instant": "pools-trade-instant-source-coverage-report.json",
    "pools_trade_lbp": "pools-trade-lbp-source-coverage-report.json",
    "doppler": "doppler-source-coverage-report.json",
    "flap": "flap-source-coverage-report.json",
    "trench_today": "trench-source-coverage-report.json",
    "hood_fun_current": "hood-current-coverage.json",
    "hood_fun_previous": "hood-previous-coverage.json",
    "noxa": "noxa-source-coverage-report.json",
}
LAUNCHPAD_SUMMARY_PATHS = {
    "pons_v1": "pons-v1-lifecycle-eligibility.jsonl",
    "pons_v2": "pons-v2-lifecycle-eligibility.jsonl",
    "pools_fun": "pools-fun-market-cap-summary.jsonl",
    "pools_trade_instant": "pools-trade-instant-market-cap-summary.jsonl",
    "pools_trade_lbp": "pools-trade-lbp-lifecycle-summary.jsonl",
    "doppler": "doppler-market-cap-summary.jsonl",
    "flap": "flap-lifecycle-summary.jsonl",
    "trench_today": "trench-lifecycle-summary.jsonl",
    "hood_fun_current": "hood-current-token-summary.jsonl",
    "hood_fun_previous": "hood-previous-token-summary.jsonl",
    "noxa": "noxa-market-cap-summary.jsonl",
}
DIRECT_COVERAGE_ARTIFACTS = {
    source: f"phase2-direct-source-coverage-{source}"
    for source in DIRECT_SOURCES
}
DIRECT_COVERAGE_REPORT_PATH = "direct-source-coverage-report.json"


def _positive_run_id(value: object, *, label: str) -> int:
    run_id = int(value or 0)
    if run_id <= 0:
        raise ValueError(f"{label} must be positive")
    return run_id


def _artifact_digest(value: object, *, label: str) -> str:
    text = str(value or "").lower()
    if not text.startswith("sha256:") or len(text) != 71:
        raise ValueError(f"{label} must use sha256:<64 hex chars>")
    try:
        int(text.removeprefix("sha256:"), 16)
    except ValueError as exc:
        raise ValueError(f"{label} is not hexadecimal") from exc
    return text


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower().removeprefix("sha256:")
    if len(text) != 64:
        raise ValueError(f"{label} must be 64 hex chars")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} is not hexadecimal") from exc
    return text


def _coverage_binding(
    source_id: str,
    raw: Mapping[str, object],
    *,
    artifact_name: str,
    report_path: str,
    summary_path: str | None,
) -> dict:
    row = dict(raw)
    run_id = _positive_run_id(
        row.get("run_id"),
        label=f"{source_id} coverage run ID",
    )
    digest = _artifact_digest(
        row.get("artifact_digest"),
        label=f"{source_id} coverage artifact digest",
    )
    if str(row.get("artifact_name") or "") != artifact_name:
        raise ValueError(f"{source_id} coverage artifact name drift")
    if str(row.get("report_path") or "") != report_path:
        raise ValueError(f"{source_id} coverage report path drift")
    report_sha = _sha256(
        row.get("report_sha256"),
        label=f"{source_id} coverage report",
    )
    output = {
        "run_id": run_id,
        "artifact_name": artifact_name,
        "artifact_digest": digest,
        "report_path": report_path,
        "report_sha256": report_sha,
    }
    if summary_path is not None:
        if str(row.get("summary_path") or "") != summary_path:
            raise ValueError(f"{source_id} eligibility summary path drift")
        output["summary_path"] = summary_path
        output["summary_sha256"] = _sha256(
            row.get("summary_sha256"),
            label=f"{source_id} eligibility summary",
        )
    return output


def build_phase2_eligibility_dispatch_plan(
    coverage_bindings: Mapping[str, Mapping[str, object]],
    selector_binding: Mapping[str, object],
) -> dict:
    """Build exact manual-dispatch inputs for all Phase-2 eligibility handoffs."""

    supplied = {str(key) for key in coverage_bindings}
    expected = set(LAUNCHPAD_SOURCES) | set(DIRECT_SOURCES)
    if supplied != expected:
        raise ValueError(
            "Phase-2 eligibility coverage binding set drift: "
            f"missing={sorted(expected - supplied)} "
            f"extra={sorted(supplied - expected)}"
        )

    normalized: dict[str, dict] = {}
    for source in LAUNCHPAD_SOURCES:
        normalized[source] = _coverage_binding(
            source,
            coverage_bindings[source],
            artifact_name=LAUNCHPAD_COVERAGE_ARTIFACTS[source],
            report_path=LAUNCHPAD_COVERAGE_REPORT_PATHS[source],
            summary_path=LAUNCHPAD_SUMMARY_PATHS[source],
        )
    for source in DIRECT_SOURCES:
        normalized[source] = _coverage_binding(
            source,
            coverage_bindings[source],
            artifact_name=DIRECT_COVERAGE_ARTIFACTS[source],
            report_path=DIRECT_COVERAGE_REPORT_PATH,
            summary_path=None,
        )

    selector = dict(selector_binding)
    selector_run_id = _positive_run_id(
        selector.get("run_id"),
        label="direct selector run ID",
    )
    selector_digest = _artifact_digest(
        selector.get("artifact_digest"),
        label="direct selector artifact digest",
    )
    selector_sha = _sha256(
        selector.get("descriptor_sha256"),
        label="direct selector descriptor",
    )
    if str(selector.get("artifact_name") or "") != (
        "phase2-direct-market-selector-freeze"
    ):
        raise ValueError("direct selector artifact name drift")

    launchpad_dispatches = []
    for source in LAUNCHPAD_SOURCES:
        row = normalized[source]
        launchpad_dispatches.append({
            "source_id": source,
            "workflow": LAUNCHPAD_ELIGIBILITY_WORKFLOW,
            "inputs": {
                "source_id": source,
                "coverage_run_id": str(row["run_id"]),
                "coverage_artifact_name": row["artifact_name"],
                "expected_coverage_artifact_digest": row["artifact_digest"],
                "coverage_report_path": row["report_path"],
                "expected_coverage_report_sha256": row["report_sha256"],
                "eligibility_run_id": str(row["run_id"]),
                "eligibility_artifact_name": row["artifact_name"],
                "expected_eligibility_artifact_digest": row[
                    "artifact_digest"
                ],
                "eligibility_summary_path": row["summary_path"],
                "expected_eligibility_summary_sha256": row[
                    "summary_sha256"
                ],
            },
        })

    direct_inputs = {
        "selector_run_id": str(selector_run_id),
        "expected_selector_artifact_digest": selector_digest,
        "expected_selector_descriptor_sha256": selector_sha,
    }
    prefixes = {
        "direct_uniswap_v3": "uniswap_v3",
        "direct_sushiswap_v3": "sushiswap_v3",
        "direct_uniswap_v4": "uniswap_v4",
    }
    for source in DIRECT_SOURCES:
        row = normalized[source]
        prefix = prefixes[source]
        direct_inputs[f"{prefix}_coverage_run_id"] = str(row["run_id"])
        direct_inputs[f"{prefix}_expected_artifact_digest"] = row[
            "artifact_digest"
        ]
        direct_inputs[f"{prefix}_expected_report_sha256"] = row[
            "report_sha256"
        ]

    return {
        "version": PHASE2_ELIGIBILITY_DISPATCH_PLAN_VERSION,
        "coverage_sources": 14,
        "launchpad_dispatches": launchpad_dispatches,
        "direct_dispatch": {
            "workflow": DIRECT_ELIGIBILITY_WORKFLOW,
            "inputs": direct_inputs,
        },
        "dispatch_count": 12,
        "phase2_universe_coverage_complete_required": True,
        "workflow_dispatch_performed": False,
    }
