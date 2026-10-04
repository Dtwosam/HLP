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

PHASE2_ELIGIBILITY_WAVE_LAUNCH_RECEIPT_VERSION = (
    "phase2-eligibility-wave-launch-receipt-v1"
)

LAUNCHPAD_DISPATCH_INPUT_NAMES = frozenset({
    "source_id",
    "coverage_run_id",
    "coverage_artifact_name",
    "expected_coverage_artifact_digest",
    "coverage_report_path",
    "expected_coverage_report_sha256",
    "eligibility_run_id",
    "eligibility_artifact_name",
    "expected_eligibility_artifact_digest",
    "eligibility_summary_path",
    "expected_eligibility_summary_sha256",
})
DIRECT_DISPATCH_INPUT_NAMES = frozenset({
    "selector_run_id",
    "expected_selector_artifact_digest",
    "expected_selector_descriptor_sha256",
    "uniswap_v3_coverage_run_id",
    "uniswap_v3_expected_artifact_digest",
    "uniswap_v3_expected_report_sha256",
    "sushiswap_v3_coverage_run_id",
    "sushiswap_v3_expected_artifact_digest",
    "sushiswap_v3_expected_report_sha256",
    "uniswap_v4_coverage_run_id",
    "uniswap_v4_expected_artifact_digest",
    "uniswap_v4_expected_report_sha256",
})


def _commit_sha(value: object, *, label: str) -> str:
    text = str(value or "").lower()
    if len(text) != 40:
        raise ValueError(f"{label} must be a 40-char commit SHA")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} is not hexadecimal") from exc
    return text


def validate_phase2_eligibility_dispatch_plan(
    plan: Mapping[str, object],
    *,
    require_execution_metadata: bool = False,
) -> dict:
    """Validate an immutable 14/14 eligibility-wave dispatch plan."""

    row = dict(plan)
    if str(row.get("version") or "") != (
        PHASE2_ELIGIBILITY_DISPATCH_PLAN_VERSION
    ):
        raise ValueError("Phase-2 eligibility dispatch-plan version changed")
    if int(row.get("coverage_sources", -1)) != 14:
        raise ValueError("Phase-2 eligibility coverage-source count drift")
    if int(row.get("dispatch_count", -1)) != 12:
        raise ValueError("Phase-2 eligibility dispatch count drift")
    if row.get("phase2_universe_coverage_complete_required") is not True:
        raise ValueError("Phase-2 eligibility plan lost 14/14 requirement")
    if row.get("workflow_dispatch_performed") is not False:
        raise ValueError("Phase-2 eligibility plan is not read-only")

    raw_launchpads = row.get("launchpad_dispatches")
    if not isinstance(raw_launchpads, list):
        raise ValueError("Phase-2 launchpad dispatch list is missing")
    if len(raw_launchpads) != len(LAUNCHPAD_SOURCES):
        raise ValueError("Phase-2 launchpad dispatch count drift")

    normalized_launchpads = []
    for expected_source, raw in zip(
        LAUNCHPAD_SOURCES,
        raw_launchpads,
        strict=True,
    ):
        if not isinstance(raw, Mapping):
            raise ValueError(
                f"{expected_source} eligibility dispatch is not an object"
            )
        dispatch = dict(raw)
        if str(dispatch.get("source_id") or "") != expected_source:
            raise ValueError(
                f"{expected_source} eligibility dispatch source drift"
            )
        if str(dispatch.get("workflow") or "") != (
            LAUNCHPAD_ELIGIBILITY_WORKFLOW
        ):
            raise ValueError(
                f"{expected_source} eligibility workflow drift"
            )
        inputs_raw = dispatch.get("inputs")
        if not isinstance(inputs_raw, Mapping):
            raise ValueError(
                f"{expected_source} eligibility dispatch inputs are missing"
            )
        inputs = dict(inputs_raw)
        if set(inputs) != LAUNCHPAD_DISPATCH_INPUT_NAMES:
            raise ValueError(
                f"{expected_source} eligibility dispatch-input drift"
            )
        if str(inputs["source_id"]) != expected_source:
            raise ValueError(
                f"{expected_source} eligibility input source drift"
            )
        coverage_run_id = _positive_run_id(
            inputs["coverage_run_id"],
            label=f"{expected_source} eligibility coverage run ID",
        )
        eligibility_run_id = _positive_run_id(
            inputs["eligibility_run_id"],
            label=f"{expected_source} eligibility source run ID",
        )
        if eligibility_run_id != coverage_run_id:
            raise ValueError(
                f"{expected_source} coverage/eligibility run binding drift"
            )
        expected_artifact = LAUNCHPAD_COVERAGE_ARTIFACTS[
            expected_source
        ]
        if str(inputs["coverage_artifact_name"]) != expected_artifact:
            raise ValueError(
                f"{expected_source} eligibility coverage artifact drift"
            )
        if str(inputs["eligibility_artifact_name"]) != expected_artifact:
            raise ValueError(
                f"{expected_source} eligibility source artifact drift"
            )
        coverage_digest = _artifact_digest(
            inputs["expected_coverage_artifact_digest"],
            label=f"{expected_source} eligibility coverage digest",
        )
        eligibility_digest = _artifact_digest(
            inputs["expected_eligibility_artifact_digest"],
            label=f"{expected_source} eligibility source digest",
        )
        if eligibility_digest != coverage_digest:
            raise ValueError(
                f"{expected_source} coverage/eligibility artifact drift"
            )
        if str(inputs["coverage_report_path"]) != (
            LAUNCHPAD_COVERAGE_REPORT_PATHS[expected_source]
        ):
            raise ValueError(
                f"{expected_source} eligibility coverage-report path drift"
            )
        if str(inputs["eligibility_summary_path"]) != (
            LAUNCHPAD_SUMMARY_PATHS[expected_source]
        ):
            raise ValueError(
                f"{expected_source} eligibility summary path drift"
            )
        report_sha = _sha256(
            inputs["expected_coverage_report_sha256"],
            label=f"{expected_source} eligibility coverage report",
        )
        summary_sha = _sha256(
            inputs["expected_eligibility_summary_sha256"],
            label=f"{expected_source} eligibility summary",
        )
        normalized_inputs = {
            **inputs,
            "coverage_run_id": str(coverage_run_id),
            "eligibility_run_id": str(eligibility_run_id),
            "expected_coverage_artifact_digest": coverage_digest,
            "expected_eligibility_artifact_digest": eligibility_digest,
            "expected_coverage_report_sha256": report_sha,
            "expected_eligibility_summary_sha256": summary_sha,
        }
        normalized_launchpads.append({
            "source_id": expected_source,
            "workflow": LAUNCHPAD_ELIGIBILITY_WORKFLOW,
            "inputs": normalized_inputs,
        })

    raw_direct = row.get("direct_dispatch")
    if not isinstance(raw_direct, Mapping):
        raise ValueError("Phase-2 direct eligibility dispatch is missing")
    direct = dict(raw_direct)
    if str(direct.get("workflow") or "") != DIRECT_ELIGIBILITY_WORKFLOW:
        raise ValueError("Phase-2 direct eligibility workflow drift")
    direct_inputs_raw = direct.get("inputs")
    if not isinstance(direct_inputs_raw, Mapping):
        raise ValueError("Phase-2 direct eligibility inputs are missing")
    direct_inputs = dict(direct_inputs_raw)
    if set(direct_inputs) != DIRECT_DISPATCH_INPUT_NAMES:
        raise ValueError("Phase-2 direct eligibility dispatch-input drift")
    direct_inputs["selector_run_id"] = str(
        _positive_run_id(
            direct_inputs["selector_run_id"],
            label="direct eligibility selector run ID",
        )
    )
    direct_inputs["expected_selector_artifact_digest"] = (
        _artifact_digest(
            direct_inputs["expected_selector_artifact_digest"],
            label="direct eligibility selector artifact",
        )
    )
    direct_inputs["expected_selector_descriptor_sha256"] = _sha256(
        direct_inputs["expected_selector_descriptor_sha256"],
        label="direct eligibility selector descriptor",
    )
    prefixes = {
        "direct_uniswap_v3": "uniswap_v3",
        "direct_sushiswap_v3": "sushiswap_v3",
        "direct_uniswap_v4": "uniswap_v4",
    }
    for source in DIRECT_SOURCES:
        prefix = prefixes[source]
        direct_inputs[f"{prefix}_coverage_run_id"] = str(
            _positive_run_id(
                direct_inputs[f"{prefix}_coverage_run_id"],
                label=f"{source} eligibility coverage run ID",
            )
        )
        direct_inputs[f"{prefix}_expected_artifact_digest"] = (
            _artifact_digest(
                direct_inputs[f"{prefix}_expected_artifact_digest"],
                label=f"{source} eligibility coverage artifact",
            )
        )
        direct_inputs[f"{prefix}_expected_report_sha256"] = _sha256(
            direct_inputs[f"{prefix}_expected_report_sha256"],
            label=f"{source} eligibility coverage report",
        )

    normalized = {
        **row,
        "coverage_sources": 14,
        "launchpad_dispatches": normalized_launchpads,
        "direct_dispatch": {
            "workflow": DIRECT_ELIGIBILITY_WORKFLOW,
            "inputs": direct_inputs,
        },
        "dispatch_count": 12,
        "phase2_universe_coverage_complete_required": True,
        "workflow_dispatch_performed": False,
    }
    if require_execution_metadata:
        normalized["final_ledger_approval_run_id"] = _positive_run_id(
            row.get("final_ledger_approval_run_id"),
            label="final ledger approval run ID",
        )
        normalized["final_ledger_approval_artifact_digest"] = (
            _artifact_digest(
                row.get("final_ledger_approval_artifact_digest"),
                label="final ledger approval artifact digest",
            )
        )
        normalized["canonical_ledger_commit_sha"] = _commit_sha(
            row.get("canonical_ledger_commit_sha"),
            label="final canonical ledger commit",
        )
        normalized["pons_coverage_run_id"] = _positive_run_id(
            row.get("pons_coverage_run_id"),
            label="Pons coverage run ID",
        )
    return normalized


def validate_phase2_eligibility_wave_launch_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate the immutable receipt for a 12-run eligibility wave."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE2_ELIGIBILITY_WAVE_LAUNCH_RECEIPT_VERSION
    ):
        raise ValueError("Phase-2 eligibility-wave launch version changed")
    control_run_id = _positive_run_id(
        row.get("eligibility_wave_control_run_id"),
        label="eligibility-wave control run ID",
    )
    plan_run_id = _positive_run_id(
        row.get("plan_run_id"),
        label="eligibility-wave plan run ID",
    )
    plan_digest = _artifact_digest(
        row.get("plan_artifact_digest"),
        label="eligibility-wave plan artifact digest",
    )
    pons_run_id = _positive_run_id(
        row.get("pons_coverage_run_id"),
        label="eligibility-wave Pons coverage run ID",
    )
    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError("eligibility-wave execution branch is empty")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="eligibility-wave execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="eligibility-wave canonical ledger commit",
    )
    if canonical != head:
        raise ValueError(
            "eligibility-wave canonical commit is not execution HEAD"
        )

    launchpads_raw = row.get("launchpad_run_ids")
    if not isinstance(launchpads_raw, Mapping):
        raise ValueError("eligibility-wave launchpad run map is missing")
    if set(launchpads_raw) != set(LAUNCHPAD_SOURCES):
        raise ValueError("eligibility-wave launchpad run set drift")
    launchpads = {
        source: _positive_run_id(
            launchpads_raw[source],
            label=f"{source} eligibility target run ID",
        )
        for source in LAUNCHPAD_SOURCES
    }
    direct_run_id = _positive_run_id(
        row.get("direct_run_id"),
        label="direct eligibility target run ID",
    )
    all_run_ids = list(launchpads.values()) + [direct_run_id]
    if len(set(all_run_ids)) != 12:
        raise ValueError("eligibility-wave target run IDs are not unique")
    if int(row.get("target_runs_created", -1)) != 12:
        raise ValueError("eligibility-wave target-run count drift")
    if row.get("target_runs_waited_for_completion") is not False:
        raise ValueError("eligibility-wave launcher unexpectedly waited")
    if row.get("phase2_universe_coverage_complete") is not True:
        raise ValueError("eligibility-wave receipt lost 14/14 coverage proof")
    if row.get("phase2_universe_frozen") is not False:
        raise ValueError("eligibility-wave receipt prematurely freezes universe")
    if row.get("canonical_coverage_ledger_mutated") is not False:
        raise ValueError("eligibility-wave launcher mutated canonical ledger")
    if row.get("workflow_dispatch_performed") is not True:
        raise ValueError("eligibility-wave receipt lacks dispatch proof")

    return {
        **row,
        "eligibility_wave_control_run_id": control_run_id,
        "plan_run_id": plan_run_id,
        "plan_artifact_digest": plan_digest,
        "pons_coverage_run_id": pons_run_id,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "launchpad_run_ids": launchpads,
        "direct_run_id": direct_run_id,
        "target_runs_created": 12,
        "target_runs_waited_for_completion": False,
        "phase2_universe_coverage_complete": True,
        "phase2_universe_frozen": False,
        "canonical_coverage_ledger_mutated": False,
        "workflow_dispatch_performed": True,
    }

