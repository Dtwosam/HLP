"""First Phase-3 feature fan-out after leakage-safe feature entry."""

from __future__ import annotations

from typing import Mapping

from hlp.data.phase3_feature_entry_dispatch import (
    validate_phase3_feature_entry_completion_receipt,
)


PHASE3_FIRST_WAVE_PLAN_VERSION = "phase3-first-wave-plan-v1"
PHASE3_FIRST_WAVE_LAUNCH_VERSION = "phase3-first-wave-launch-receipt-v1"
PHASE3_FIRST_WAVE_COMPLETION_VERSION = (
    "phase3-first-wave-completion-receipt-v1"
)

TRANSFER_WORKFLOW = "phase3-canonical-transfer-tape.yml"
PRICE_WORKFLOW = "phase3-price-features.yml"
CHAIN_WORKFLOW = "phase3-chain-regime-features.yml"
VENUE_WORKFLOW = "phase3-venue-mechanics-features.yml"
FIRST_WAVE_WORKFLOWS = (
    TRANSFER_WORKFLOW,
    PRICE_WORKFLOW,
    CHAIN_WORKFLOW,
    VENUE_WORKFLOW,
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


def build_phase3_first_wave_plan(
    entry_completion: Mapping[str, object],
) -> dict:
    entry = validate_phase3_feature_entry_completion_receipt(
        entry_completion
    )
    common_entry = {
        "feature_entry_run_id": str(entry["feature_entry_run_id"]),
        "expected_feature_entry_artifact_digest": entry[
            "feature_entry_artifact_digest"
        ],
        "expected_feature_entry_handoff_sha256": entry[
            "entry_handoff_sha256"
        ],
    }
    universe = {
        "universe_run_id": str(entry["universe_run_id"]),
        "expected_universe_artifact_digest": entry[
            "universe_artifact_digest"
        ],
        "expected_universe_handoff_sha256": entry[
            "universe_handoff_sha256"
        ],
    }
    price_path = {
        "price_path_run_id": str(entry["price_path_run_id"]),
        "expected_price_path_artifact_digest": entry[
            "price_path_artifact_digest"
        ],
        "expected_price_path_handoff_sha256": entry[
            "price_path_handoff_sha256"
        ],
    }
    dispatches = [
        {
            "node_id": "canonical_transfer",
            "workflow": TRANSFER_WORKFLOW,
            "inputs": {
                **common_entry,
                **universe,
                "max_tokens_per_batch": "50",
            },
        },
        {
            "node_id": "price_features",
            "workflow": PRICE_WORKFLOW,
            "inputs": {**common_entry, **price_path},
        },
        {
            "node_id": "chain_regime",
            "workflow": CHAIN_WORKFLOW,
            "inputs": {**common_entry, **price_path},
        },
        {
            "node_id": "venue_mechanics",
            "workflow": VENUE_WORKFLOW,
            "inputs": {**common_entry, **price_path},
        },
    ]
    return {
        "version": PHASE3_FIRST_WAVE_PLAN_VERSION,
        "execution_branch": entry["execution_branch"],
        "execution_head_sha": entry["execution_head_sha"],
        "canonical_ledger_commit_sha": entry[
            "canonical_ledger_commit_sha"
        ],
        "feature_entry_completion_control_run_id": entry[
            "feature_entry_completion_control_run_id"
        ],
        "feature_entry_run_id": entry["feature_entry_run_id"],
        "feature_entry_artifact_digest": entry[
            "feature_entry_artifact_digest"
        ],
        "feature_entry_handoff_sha256": entry["entry_handoff_sha256"],
        "feature_subjects": entry["feature_subjects"],
        "universe_run_id": entry["universe_run_id"],
        "universe_artifact_digest": entry["universe_artifact_digest"],
        "universe_handoff_sha256": entry["universe_handoff_sha256"],
        "price_path_run_id": entry["price_path_run_id"],
        "price_path_artifact_digest": entry[
            "price_path_artifact_digest"
        ],
        "price_path_handoff_sha256": entry[
            "price_path_handoff_sha256"
        ],
        "dispatches": dispatches,
        "dispatch_count": 4,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "workflow_dispatch_performed": False,
    }


def validate_phase3_first_wave_plan(plan: Mapping[str, object]) -> dict:
    row = dict(plan)
    if str(row.get("version") or "") != PHASE3_FIRST_WAVE_PLAN_VERSION:
        raise ValueError("Phase-3 first-wave plan version changed")
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="Phase-3 first-wave execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="Phase-3 first-wave canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("Phase-3 first-wave branch/HEAD drift")
    completion_run = _positive_run_id(
        row.get("feature_entry_completion_control_run_id"),
        label="Phase-3 first-wave entry completion run ID",
    )
    entry_run = _positive_run_id(
        row.get("feature_entry_run_id"),
        label="Phase-3 first-wave entry run ID",
    )
    entry_digest = _artifact_digest(
        row.get("feature_entry_artifact_digest"),
        label="Phase-3 first-wave entry artifact",
    )
    entry_handoff = _sha256(
        row.get("feature_entry_handoff_sha256"),
        label="Phase-3 first-wave entry handoff",
    )
    universe_run = _positive_run_id(
        row.get("universe_run_id"),
        label="Phase-3 first-wave universe run ID",
    )
    universe_digest = _artifact_digest(
        row.get("universe_artifact_digest"),
        label="Phase-3 first-wave universe artifact",
    )
    universe_handoff = _sha256(
        row.get("universe_handoff_sha256"),
        label="Phase-3 first-wave universe handoff",
    )
    price_run = _positive_run_id(
        row.get("price_path_run_id"),
        label="Phase-3 first-wave price-path run ID",
    )
    price_digest = _artifact_digest(
        row.get("price_path_artifact_digest"),
        label="Phase-3 first-wave price-path artifact",
    )
    price_handoff = _sha256(
        row.get("price_path_handoff_sha256"),
        label="Phase-3 first-wave price-path handoff",
    )
    subjects = int(row.get("feature_subjects", -1))
    if subjects <= 0:
        raise ValueError("Phase-3 first-wave subject count invalid")
    raw = row.get("dispatches")
    if not isinstance(raw, list) or len(raw) != 4:
        raise ValueError("Phase-3 first-wave dispatch count drift")
    expected = {
        "canonical_transfer": {
            "workflow": TRANSFER_WORKFLOW,
            "inputs": {
                "feature_entry_run_id": str(entry_run),
                "expected_feature_entry_artifact_digest": entry_digest,
                "expected_feature_entry_handoff_sha256": entry_handoff,
                "universe_run_id": str(universe_run),
                "expected_universe_artifact_digest": universe_digest,
                "expected_universe_handoff_sha256": universe_handoff,
                "max_tokens_per_batch": "50",
            },
        },
        "price_features": {
            "workflow": PRICE_WORKFLOW,
            "inputs": {
                "feature_entry_run_id": str(entry_run),
                "expected_feature_entry_artifact_digest": entry_digest,
                "expected_feature_entry_handoff_sha256": entry_handoff,
                "price_path_run_id": str(price_run),
                "expected_price_path_artifact_digest": price_digest,
                "expected_price_path_handoff_sha256": price_handoff,
            },
        },
        "chain_regime": {
            "workflow": CHAIN_WORKFLOW,
            "inputs": {
                "feature_entry_run_id": str(entry_run),
                "expected_feature_entry_artifact_digest": entry_digest,
                "expected_feature_entry_handoff_sha256": entry_handoff,
                "price_path_run_id": str(price_run),
                "expected_price_path_artifact_digest": price_digest,
                "expected_price_path_handoff_sha256": price_handoff,
            },
        },
        "venue_mechanics": {
            "workflow": VENUE_WORKFLOW,
            "inputs": {
                "feature_entry_run_id": str(entry_run),
                "expected_feature_entry_artifact_digest": entry_digest,
                "expected_feature_entry_handoff_sha256": entry_handoff,
                "price_path_run_id": str(price_run),
                "expected_price_path_artifact_digest": price_digest,
                "expected_price_path_handoff_sha256": price_handoff,
            },
        },
    }
    seen = set()
    normalized = []
    for item_raw in raw:
        if not isinstance(item_raw, Mapping):
            raise ValueError("Phase-3 first-wave dispatch is invalid")
        item = dict(item_raw)
        node_id = str(item.get("node_id") or "")
        if node_id not in expected or node_id in seen:
            raise ValueError(f"Phase-3 first-wave node drift: {node_id}")
        seen.add(node_id)
        exp = expected[node_id]
        if str(item.get("workflow") or "") != exp["workflow"]:
            raise ValueError(f"{node_id} workflow drift")
        if dict(item.get("inputs") or {}) != exp["inputs"]:
            raise ValueError(f"{node_id} input binding drift")
        normalized.append({
            "node_id": node_id,
            "workflow": exp["workflow"],
            "inputs": exp["inputs"],
        })
    if seen != set(expected):
        raise ValueError("Phase-3 first-wave node set drift")
    if int(row.get("dispatch_count", -1)) != 4:
        raise ValueError("Phase-3 first-wave dispatch-count drift")
    for field in (
        "outcome_rows_consumed",
        "outcome_fields_exposed",
        "future_state_allowed",
        "workflow_dispatch_performed",
    ):
        if row.get(field) is not False:
            raise ValueError(f"Phase-3 first-wave {field} drift")
    return {
        **row,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "feature_entry_completion_control_run_id": completion_run,
        "feature_entry_run_id": entry_run,
        "feature_entry_artifact_digest": entry_digest,
        "feature_entry_handoff_sha256": entry_handoff,
        "feature_subjects": subjects,
        "universe_run_id": universe_run,
        "universe_artifact_digest": universe_digest,
        "universe_handoff_sha256": universe_handoff,
        "price_path_run_id": price_run,
        "price_path_artifact_digest": price_digest,
        "price_path_handoff_sha256": price_handoff,
        "dispatches": sorted(normalized, key=lambda value: value["node_id"]),
        "dispatch_count": 4,
    }


def validate_phase3_first_wave_launch_receipt(
    receipt: Mapping[str, object],
) -> dict:
    row = dict(receipt)
    if str(row.get("version") or "") != PHASE3_FIRST_WAVE_LAUNCH_VERSION:
        raise ValueError("Phase-3 first-wave launch version changed")
    control = _positive_run_id(
        row.get("first_wave_control_run_id"),
        label="Phase-3 first-wave control run ID",
    )
    plan_run = _positive_run_id(
        row.get("first_wave_plan_run_id"),
        label="Phase-3 first-wave plan run ID",
    )
    plan_digest = _artifact_digest(
        row.get("first_wave_plan_artifact_digest"),
        label="Phase-3 first-wave plan artifact",
    )
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="Phase-3 first-wave launch head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="Phase-3 first-wave launch canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("Phase-3 first-wave launch branch/HEAD drift")
    runs_raw = row.get("target_run_ids")
    if not isinstance(runs_raw, Mapping) or set(runs_raw) != {
        "canonical_transfer",
        "price_features",
        "chain_regime",
        "venue_mechanics",
    }:
        raise ValueError("Phase-3 first-wave target run set drift")
    runs = {
        key: _positive_run_id(value, label=f"{key} target run ID")
        for key, value in runs_raw.items()
    }
    if len(set(runs.values())) != 4:
        raise ValueError("Phase-3 first-wave target run IDs are not unique")
    if int(row.get("target_runs_created", -1)) != 4:
        raise ValueError("Phase-3 first-wave target-run count drift")
    if row.get("target_runs_waited_for_completion") is not False:
        raise ValueError("Phase-3 first-wave launcher unexpectedly waited")
    if row.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-3 first-wave launch consumed outcomes")
    if row.get("workflow_dispatch_performed") is not True:
        raise ValueError("Phase-3 first-wave launch lacks dispatch proof")
    return {
        **row,
        "first_wave_control_run_id": control,
        "first_wave_plan_run_id": plan_run,
        "first_wave_plan_artifact_digest": plan_digest,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "target_run_ids": dict(sorted(runs.items())),
        "target_runs_created": 4,
        "target_runs_waited_for_completion": False,
        "outcome_rows_consumed": False,
        "workflow_dispatch_performed": True,
    }


def validate_phase3_first_wave_completion_receipt(
    receipt: Mapping[str, object],
) -> dict:
    row = dict(receipt)
    if str(row.get("version") or "") != PHASE3_FIRST_WAVE_COMPLETION_VERSION:
        raise ValueError("Phase-3 first-wave completion version changed")
    control = _positive_run_id(
        row.get("first_wave_completion_control_run_id"),
        label="Phase-3 first-wave completion control run ID",
    )
    launch_run = _positive_run_id(
        row.get("first_wave_launch_run_id"),
        label="Phase-3 first-wave launch run ID",
    )
    launch_digest = _artifact_digest(
        row.get("first_wave_launch_artifact_digest"),
        label="Phase-3 first-wave launch artifact",
    )
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="Phase-3 first-wave completion head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="Phase-3 first-wave completion canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("Phase-3 first-wave completion branch/HEAD drift")
    outputs_raw = row.get("outputs")
    if not isinstance(outputs_raw, Mapping) or set(outputs_raw) != {
        "canonical_transfer",
        "price_features",
        "chain_regime",
        "venue_mechanics",
    }:
        raise ValueError("Phase-3 first-wave output set drift")
    outputs = {}
    for key, value in outputs_raw.items():
        if not isinstance(value, Mapping):
            raise ValueError(f"{key} first-wave output invalid")
        item = dict(value)
        normalized = {
            "run_id": _positive_run_id(
                item.get("run_id"),
                label=f"{key} completed run ID",
            ),
            "artifact_digest": _artifact_digest(
                item.get("artifact_digest"),
                label=f"{key} artifact",
            ),
            "handoff_artifact_digest": _artifact_digest(
                item.get("handoff_artifact_digest"),
                label=f"{key} handoff artifact",
            ),
            "handoff_sha256": _sha256(
                item.get("handoff_sha256"),
                label=f"{key} handoff",
            ),
        }
        if key == "canonical_transfer":
            normalized["universe_tokens"] = int(
                item.get("universe_tokens", -1)
            )
            normalized["transfer_rows"] = int(
                item.get("transfer_rows", -1)
            )
            if normalized["universe_tokens"] <= 0:
                raise ValueError(
                    "canonical transfer universe-token count invalid"
                )
            if normalized["transfer_rows"] < 0:
                raise ValueError(
                    "canonical transfer row count invalid"
                )
        else:
            normalized["feature_subjects"] = int(
                item.get("feature_subjects", -1)
            )
            if normalized["feature_subjects"] <= 0:
                raise ValueError(f"{key} subject count invalid")
        outputs[key] = normalized
    subjects = {
        outputs[key]["feature_subjects"]
        for key in ("price_features", "chain_regime", "venue_mechanics")
    }
    if len(subjects) != 1:
        raise ValueError("Phase-3 first-wave feature-subject coverage drift")
    if int(row.get("target_runs_completed", -1)) != 4:
        raise ValueError("Phase-3 first-wave completion count drift")
    if row.get("all_target_runs_successful") is not True:
        raise ValueError("Phase-3 first-wave lacks success proof")
    for field in (
        "outcome_rows_consumed",
        "outcome_fields_exposed",
        "future_state_allowed",
    ):
        if row.get(field) is not False:
            raise ValueError(f"Phase-3 first-wave completion {field} drift")
    if row.get("workflow_dispatch_performed") is not False:
        raise ValueError("Phase-3 first-wave completion dispatches workflow")
    return {
        **row,
        "first_wave_completion_control_run_id": control,
        "first_wave_launch_run_id": launch_run,
        "first_wave_launch_artifact_digest": launch_digest,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "outputs": dict(sorted(outputs.items())),
        "feature_subjects": subjects.pop(),
        "universe_tokens": outputs["canonical_transfer"]["universe_tokens"],
        "target_runs_completed": 4,
        "all_target_runs_successful": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "workflow_dispatch_performed": False,
    }
