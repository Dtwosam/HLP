"""Second Phase-3 feature wave from canonical transfer evidence."""

from __future__ import annotations

from typing import Mapping

from hlp.data.phase3_first_wave_dispatch import (
    validate_phase3_first_wave_completion_receipt,
)


PHASE3_SECOND_WAVE_PLAN_VERSION = "phase3-second-wave-plan-v1"
PHASE3_SECOND_WAVE_LAUNCH_VERSION = "phase3-second-wave-launch-receipt-v1"
PHASE3_SECOND_WAVE_COMPLETION_VERSION = (
    "phase3-second-wave-completion-receipt-v1"
)

EARLY_WORKFLOW = "phase3-early-recipient-features.yml"
HOLDER_WORKFLOW = "phase3-holder-features.yml"
LIFECYCLE_WORKFLOW = "phase3-lifecycle-features.yml"
REDISTRIBUTION_WORKFLOW = "phase3-redistribution-features.yml"

SECOND_WAVE_WORKFLOWS = (
    EARLY_WORKFLOW,
    HOLDER_WORKFLOW,
    LIFECYCLE_WORKFLOW,
    REDISTRIBUTION_WORKFLOW,
)


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


def _commit_sha(value: object, *, label: str) -> str:
    text = str(value or "").lower()
    if len(text) != 40:
        raise ValueError(f"{label} must be a 40-char commit SHA")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} is not hexadecimal") from exc
    return text


def _feature_output(raw: Mapping[str, object], *, label: str) -> dict:
    row = dict(raw)
    return {
        "run_id": _positive_run_id(
            row.get("run_id"),
            label=f"{label} run ID",
        ),
        "artifact_digest": _artifact_digest(
            row.get("artifact_digest"),
            label=f"{label} artifact",
        ),
        "handoff_artifact_digest": _artifact_digest(
            row.get("handoff_artifact_digest"),
            label=f"{label} handoff artifact",
        ),
        "handoff_sha256": _sha256(
            row.get("handoff_sha256"),
            label=f"{label} handoff",
        ),
        "feature_subjects": int(row.get("feature_subjects", -1)),
    }


def build_phase3_second_wave_plan(
    first_wave_completion: Mapping[str, object],
) -> dict:
    first = validate_phase3_first_wave_completion_receipt(
        first_wave_completion
    )
    transfer = dict(first["outputs"]["canonical_transfer"])
    common = {
        "feature_entry_run_id": str(first["feature_entry_run_id"]),
        "expected_feature_entry_artifact_digest": first[
            "feature_entry_artifact_digest"
        ],
        "expected_feature_entry_handoff_sha256": first[
            "feature_entry_handoff_sha256"
        ],
        "canonical_transfer_run_id": str(transfer["run_id"]),
        "expected_canonical_transfer_artifact_digest": transfer[
            "artifact_digest"
        ],
        "expected_canonical_transfer_handoff_sha256": transfer[
            "handoff_sha256"
        ],
    }
    dispatches = [
        {
            "node_id": "early_recipient",
            "workflow": EARLY_WORKFLOW,
            "inputs": dict(common),
        },
        {
            "node_id": "holder",
            "workflow": HOLDER_WORKFLOW,
            "inputs": dict(common),
        },
        {
            "node_id": "lifecycle",
            "workflow": LIFECYCLE_WORKFLOW,
            "inputs": dict(common),
        },
        {
            "node_id": "redistribution",
            "workflow": REDISTRIBUTION_WORKFLOW,
            "inputs": dict(common),
        },
    ]
    prior = {
        key: dict(first["outputs"][key])
        for key in ("price_features", "chain_regime", "venue_mechanics")
    }
    return {
        "version": PHASE3_SECOND_WAVE_PLAN_VERSION,
        "execution_branch": first["execution_branch"],
        "execution_head_sha": first["execution_head_sha"],
        "canonical_ledger_commit_sha": first[
            "canonical_ledger_commit_sha"
        ],
        "first_wave_completion_control_run_id": first[
            "first_wave_completion_control_run_id"
        ],
        "feature_entry_run_id": first["feature_entry_run_id"],
        "feature_entry_artifact_digest": first[
            "feature_entry_artifact_digest"
        ],
        "feature_entry_handoff_sha256": first[
            "feature_entry_handoff_sha256"
        ],
        "feature_subjects": first["feature_subjects"],
        "canonical_transfer": transfer,
        "prior_feature_outputs": prior,
        "dispatches": dispatches,
        "dispatch_count": 4,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "workflow_dispatch_performed": False,
    }


def validate_phase3_second_wave_plan(plan: Mapping[str, object]) -> dict:
    row = dict(plan)
    if str(row.get("version") or "") != PHASE3_SECOND_WAVE_PLAN_VERSION:
        raise ValueError("Phase-3 second-wave plan version changed")
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="Phase-3 second-wave execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="Phase-3 second-wave canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("Phase-3 second-wave branch/HEAD drift")
    first_control = _positive_run_id(
        row.get("first_wave_completion_control_run_id"),
        label="Phase-3 second-wave first-wave completion run ID",
    )
    entry_run = _positive_run_id(
        row.get("feature_entry_run_id"),
        label="Phase-3 second-wave entry run ID",
    )
    entry_digest = _artifact_digest(
        row.get("feature_entry_artifact_digest"),
        label="Phase-3 second-wave entry artifact",
    )
    entry_handoff = _sha256(
        row.get("feature_entry_handoff_sha256"),
        label="Phase-3 second-wave entry handoff",
    )
    subjects = int(row.get("feature_subjects", -1))
    if subjects <= 0:
        raise ValueError("Phase-3 second-wave subject count invalid")

    transfer_raw = row.get("canonical_transfer")
    if not isinstance(transfer_raw, Mapping):
        raise ValueError("Phase-3 second-wave transfer parent missing")
    transfer = dict(transfer_raw)
    transfer_run = _positive_run_id(
        transfer.get("run_id"),
        label="Phase-3 second-wave transfer run ID",
    )
    transfer_digest = _artifact_digest(
        transfer.get("artifact_digest"),
        label="Phase-3 second-wave transfer artifact",
    )
    transfer_handoff_digest = _artifact_digest(
        transfer.get("handoff_artifact_digest"),
        label="Phase-3 second-wave transfer handoff artifact",
    )
    transfer_handoff = _sha256(
        transfer.get("handoff_sha256"),
        label="Phase-3 second-wave transfer handoff",
    )
    universe_tokens = int(transfer.get("universe_tokens", -1))
    transfer_rows = int(transfer.get("transfer_rows", -1))
    if universe_tokens <= 0 or transfer_rows < 0:
        raise ValueError("Phase-3 second-wave transfer dimensions invalid")
    normalized_transfer = {
        "run_id": transfer_run,
        "artifact_digest": transfer_digest,
        "handoff_artifact_digest": transfer_handoff_digest,
        "handoff_sha256": transfer_handoff,
        "universe_tokens": universe_tokens,
        "transfer_rows": transfer_rows,
    }

    prior_raw = row.get("prior_feature_outputs")
    if not isinstance(prior_raw, Mapping) or set(prior_raw) != {
        "price_features",
        "chain_regime",
        "venue_mechanics",
    }:
        raise ValueError("Phase-3 second-wave prior feature set drift")
    prior = {}
    for key in sorted(prior_raw):
        item = _feature_output(prior_raw[key], label=key)
        if item["feature_subjects"] != subjects:
            raise ValueError(f"{key} prior subject coverage drift")
        prior[key] = item

    common = {
        "feature_entry_run_id": str(entry_run),
        "expected_feature_entry_artifact_digest": entry_digest,
        "expected_feature_entry_handoff_sha256": entry_handoff,
        "canonical_transfer_run_id": str(transfer_run),
        "expected_canonical_transfer_artifact_digest": transfer_digest,
        "expected_canonical_transfer_handoff_sha256": transfer_handoff,
    }
    expected = {
        "early_recipient": EARLY_WORKFLOW,
        "holder": HOLDER_WORKFLOW,
        "lifecycle": LIFECYCLE_WORKFLOW,
        "redistribution": REDISTRIBUTION_WORKFLOW,
    }
    raw_dispatches = row.get("dispatches")
    if not isinstance(raw_dispatches, list) or len(raw_dispatches) != 4:
        raise ValueError("Phase-3 second-wave dispatch count drift")
    normalized_dispatches = []
    seen = set()
    for raw_item in raw_dispatches:
        if not isinstance(raw_item, Mapping):
            raise ValueError("Phase-3 second-wave dispatch invalid")
        item = dict(raw_item)
        node_id = str(item.get("node_id") or "")
        if node_id not in expected or node_id in seen:
            raise ValueError(f"Phase-3 second-wave node drift: {node_id}")
        seen.add(node_id)
        if str(item.get("workflow") or "") != expected[node_id]:
            raise ValueError(f"{node_id} workflow drift")
        if dict(item.get("inputs") or {}) != common:
            raise ValueError(f"{node_id} input binding drift")
        normalized_dispatches.append({
            "node_id": node_id,
            "workflow": expected[node_id],
            "inputs": dict(common),
        })
    if seen != set(expected):
        raise ValueError("Phase-3 second-wave node set drift")
    if int(row.get("dispatch_count", -1)) != 4:
        raise ValueError("Phase-3 second-wave dispatch-count drift")
    for field in (
        "outcome_rows_consumed",
        "outcome_fields_exposed",
        "future_state_allowed",
        "workflow_dispatch_performed",
    ):
        if row.get(field) is not False:
            raise ValueError(f"Phase-3 second-wave {field} drift")
    return {
        **row,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "first_wave_completion_control_run_id": first_control,
        "feature_entry_run_id": entry_run,
        "feature_entry_artifact_digest": entry_digest,
        "feature_entry_handoff_sha256": entry_handoff,
        "feature_subjects": subjects,
        "canonical_transfer": normalized_transfer,
        "prior_feature_outputs": prior,
        "dispatches": sorted(
            normalized_dispatches,
            key=lambda item: item["node_id"],
        ),
        "dispatch_count": 4,
    }


def validate_phase3_second_wave_launch_receipt(
    receipt: Mapping[str, object],
) -> dict:
    row = dict(receipt)
    if str(row.get("version") or "") != PHASE3_SECOND_WAVE_LAUNCH_VERSION:
        raise ValueError("Phase-3 second-wave launch version changed")
    control = _positive_run_id(
        row.get("second_wave_control_run_id"),
        label="Phase-3 second-wave control run ID",
    )
    plan_run = _positive_run_id(
        row.get("second_wave_plan_run_id"),
        label="Phase-3 second-wave plan run ID",
    )
    plan_digest = _artifact_digest(
        row.get("second_wave_plan_artifact_digest"),
        label="Phase-3 second-wave plan artifact",
    )
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="Phase-3 second-wave launch head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="Phase-3 second-wave launch canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("Phase-3 second-wave launch branch/HEAD drift")
    entry_run = _positive_run_id(
        row.get("feature_entry_run_id"),
        label="Phase-3 second-wave launch entry run ID",
    )
    entry_digest = _artifact_digest(
        row.get("feature_entry_artifact_digest"),
        label="Phase-3 second-wave launch entry artifact",
    )
    entry_handoff = _sha256(
        row.get("feature_entry_handoff_sha256"),
        label="Phase-3 second-wave launch entry handoff",
    )
    subjects = int(row.get("feature_subjects", -1))
    if subjects <= 0:
        raise ValueError("Phase-3 second-wave launch subject count invalid")
    transfer_raw = row.get("canonical_transfer")
    if not isinstance(transfer_raw, Mapping):
        raise ValueError("Phase-3 second-wave launch transfer missing")
    transfer = dict(transfer_raw)
    _positive_run_id(
        transfer.get("run_id"),
        label="Phase-3 second-wave launch transfer run ID",
    )
    _artifact_digest(
        transfer.get("artifact_digest"),
        label="Phase-3 second-wave launch transfer artifact",
    )
    _sha256(
        transfer.get("handoff_sha256"),
        label="Phase-3 second-wave launch transfer handoff",
    )
    prior_raw = row.get("prior_feature_outputs")
    if not isinstance(prior_raw, Mapping) or set(prior_raw) != {
        "price_features",
        "chain_regime",
        "venue_mechanics",
    }:
        raise ValueError("Phase-3 second-wave launch prior feature drift")
    runs_raw = row.get("target_run_ids")
    expected_nodes = {
        "early_recipient",
        "holder",
        "lifecycle",
        "redistribution",
    }
    if not isinstance(runs_raw, Mapping) or set(runs_raw) != expected_nodes:
        raise ValueError("Phase-3 second-wave target run set drift")
    runs = {
        key: _positive_run_id(value, label=f"{key} target run ID")
        for key, value in runs_raw.items()
    }
    if len(set(runs.values())) != 4:
        raise ValueError("Phase-3 second-wave target run IDs not unique")
    if int(row.get("target_runs_created", -1)) != 4:
        raise ValueError("Phase-3 second-wave target-run count drift")
    if row.get("target_runs_waited_for_completion") is not False:
        raise ValueError("Phase-3 second-wave launcher unexpectedly waited")
    if row.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-3 second-wave launch consumed outcomes")
    if row.get("workflow_dispatch_performed") is not True:
        raise ValueError("Phase-3 second-wave launch lacks dispatch proof")
    return {
        **row,
        "second_wave_control_run_id": control,
        "second_wave_plan_run_id": plan_run,
        "second_wave_plan_artifact_digest": plan_digest,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "feature_entry_run_id": entry_run,
        "feature_entry_artifact_digest": entry_digest,
        "feature_entry_handoff_sha256": entry_handoff,
        "feature_subjects": subjects,
        "canonical_transfer": dict(transfer_raw),
        "prior_feature_outputs": {
            key: dict(prior_raw[key]) for key in sorted(prior_raw)
        },
        "target_run_ids": dict(sorted(runs.items())),
        "target_runs_created": 4,
        "target_runs_waited_for_completion": False,
        "outcome_rows_consumed": False,
        "workflow_dispatch_performed": True,
    }


def validate_phase3_second_wave_completion_receipt(
    receipt: Mapping[str, object],
) -> dict:
    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE3_SECOND_WAVE_COMPLETION_VERSION
    ):
        raise ValueError("Phase-3 second-wave completion version changed")
    control = _positive_run_id(
        row.get("second_wave_completion_control_run_id"),
        label="Phase-3 second-wave completion control run ID",
    )
    launch_run = _positive_run_id(
        row.get("second_wave_launch_run_id"),
        label="Phase-3 second-wave launch run ID",
    )
    launch_digest = _artifact_digest(
        row.get("second_wave_launch_artifact_digest"),
        label="Phase-3 second-wave launch artifact",
    )
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="Phase-3 second-wave completion head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="Phase-3 second-wave completion canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("Phase-3 second-wave completion branch/HEAD drift")
    entry_run = _positive_run_id(
        row.get("feature_entry_run_id"),
        label="Phase-3 second-wave completion entry run ID",
    )
    entry_digest = _artifact_digest(
        row.get("feature_entry_artifact_digest"),
        label="Phase-3 second-wave completion entry artifact",
    )
    entry_handoff = _sha256(
        row.get("feature_entry_handoff_sha256"),
        label="Phase-3 second-wave completion entry handoff",
    )
    expected_subjects = int(row.get("expected_feature_subjects", -1))
    if expected_subjects <= 0:
        raise ValueError("Phase-3 second-wave expected subject count invalid")
    transfer_raw = row.get("canonical_transfer")
    if not isinstance(transfer_raw, Mapping):
        raise ValueError("Phase-3 second-wave completion transfer missing")
    prior_raw = row.get("prior_feature_outputs")
    if not isinstance(prior_raw, Mapping) or set(prior_raw) != {
        "price_features",
        "chain_regime",
        "venue_mechanics",
    }:
        raise ValueError("Phase-3 second-wave completion prior feature drift")
    prior = {
        key: _feature_output(prior_raw[key], label=key)
        for key in sorted(prior_raw)
    }
    if any(
        item["feature_subjects"] != expected_subjects
        for item in prior.values()
    ):
        raise ValueError("Phase-3 second-wave prior subject coverage drift")
    outputs_raw = row.get("outputs")
    expected_nodes = {
        "early_recipient",
        "holder",
        "lifecycle",
        "redistribution",
    }
    if not isinstance(outputs_raw, Mapping) or set(outputs_raw) != expected_nodes:
        raise ValueError("Phase-3 second-wave output set drift")
    outputs = {
        key: _feature_output(outputs_raw[key], label=key)
        for key in sorted(outputs_raw)
    }
    if any(
        item["feature_subjects"] != expected_subjects
        for item in outputs.values()
    ):
        raise ValueError("Phase-3 second-wave feature-subject coverage drift")
    if int(row.get("target_runs_completed", -1)) != 4:
        raise ValueError("Phase-3 second-wave completion count drift")
    if row.get("all_target_runs_successful") is not True:
        raise ValueError("Phase-3 second-wave lacks success proof")
    for field in (
        "outcome_rows_consumed",
        "outcome_fields_exposed",
        "future_state_allowed",
    ):
        if row.get(field) is not False:
            raise ValueError(f"Phase-3 second-wave completion {field} drift")
    if row.get("workflow_dispatch_performed") is not False:
        raise ValueError("Phase-3 second-wave completion dispatches workflow")
    return {
        **row,
        "second_wave_completion_control_run_id": control,
        "second_wave_launch_run_id": launch_run,
        "second_wave_launch_artifact_digest": launch_digest,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "feature_entry_run_id": entry_run,
        "feature_entry_artifact_digest": entry_digest,
        "feature_entry_handoff_sha256": entry_handoff,
        "expected_feature_subjects": expected_subjects,
        "canonical_transfer": dict(transfer_raw),
        "prior_feature_outputs": prior,
        "outputs": outputs,
        "feature_subjects": expected_subjects,
        "target_runs_completed": 4,
        "all_target_runs_successful": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "workflow_dispatch_performed": False,
    }
