"""Phase-3 feature-family coverage and cutoff reconciliation gate."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase3_chain_regime import (
    PHASE3_CHAIN_REGIME_HANDOFF_VERSION,
)
from hlp.data.phase3_feature_entry import (
    PHASE3_FEATURE_SNAPSHOT_KIND,
    PHASE3_FEATURE_SUBJECT_FIELDS,
    PHASE3_FEATURE_SUBJECT_VERSION,
)
from hlp.data.phase3_feature_registry import (
    validate_phase3_feature_registry,
)
from hlp.data.phase3_holder_features import (
    PHASE3_HOLDER_FEATURE_HANDOFF_VERSION,
)
from hlp.data.phase3_price_features import (
    PHASE3_PRICE_FEATURE_HANDOFF_VERSION,
)
from hlp.data.phase3_trade_features import (
    PHASE3_TRADE_FEATURE_HANDOFF_VERSION,
)
from hlp.data.snapshot import write_jsonl_snapshot


PHASE3_FEATURE_COVERAGE_VERSION = "phase3-feature-coverage-v1"
PHASE3_FEATURE_COVERAGE_HANDOFF_VERSION = (
    "phase3-feature-coverage-handoff-v1"
)

FAMILY_HANDOFF_CONTRACTS = {
    "chain_regime": (
        PHASE3_CHAIN_REGIME_HANDOFF_VERSION,
        "phase3_chain_regime_features_ready",
    ),
    "holder_state": (
        PHASE3_HOLDER_FEATURE_HANDOFF_VERSION,
        "phase3_holder_features_ready",
    ),
    "price_drawdown": (
        PHASE3_PRICE_FEATURE_HANDOFF_VERSION,
        "phase3_price_features_ready",
    ),
    "trade_flow": (
        PHASE3_TRADE_FEATURE_HANDOFF_VERSION,
        "phase3_trade_features_ready",
    ),
}


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower().removeprefix("sha256:")
    if len(text) != 64:
        raise ValueError(f"{label} SHA-256 is invalid")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} SHA-256 is invalid") from exc
    return text


def _cutoff(row: Mapping[str, object]) -> tuple[int, int, int]:
    block = int(row.get("feature_cutoff_block", -1))
    raw_tx = row.get("feature_cutoff_transaction_index")
    tx = -1 if raw_tx is None else int(raw_tx)
    log = int(row.get("feature_cutoff_log_index", -1))
    if block < 0 or tx < -1 or log < 0:
        raise ValueError("Phase-3 feature coverage cutoff is invalid")
    return block, tx, log


def materialize_phase3_feature_coverage(
    subject_rows: Iterable[Mapping[str, object]],
    family_rows: Mapping[
        str, Iterable[Mapping[str, object]]
    ],
    family_handoffs: Mapping[str, Mapping[str, object]],
    *,
    feature_registry: Iterable[Mapping[str, object]],
    required_families: Iterable[str],
    output: Path,
) -> tuple[dict, dict]:
    """Require one cutoff-aligned row per subject for every required family."""

    registry_rows = [dict(row) for row in feature_registry]
    registry = validate_phase3_feature_registry(registry_rows)
    registry_sha = registry["registry_sha256"]
    feature_ids_by_family = {}
    for row in registry_rows:
        family = str(row["family"])
        feature_ids_by_family.setdefault(family, set()).add(
            str(row["feature_id"])
        )

    required = sorted({str(value) for value in required_families})
    if not required:
        raise ValueError("Phase-3 feature coverage requires families")
    unknown = set(required) - set(feature_ids_by_family)
    if unknown:
        raise ValueError(
            "Phase-3 feature coverage has unregistered families: "
            f"{sorted(unknown)}"
        )
    unsupported = set(required) - set(FAMILY_HANDOFF_CONTRACTS)
    if unsupported:
        raise ValueError(
            "Phase-3 feature coverage lacks handoff contracts: "
            f"{sorted(unsupported)}"
        )
    if set(family_rows) != set(required):
        raise ValueError(
            "Phase-3 feature coverage row-family contract mismatch: "
            f"missing={sorted(set(required) - set(family_rows))} "
            f"extra={sorted(set(family_rows) - set(required))}"
        )
    if set(family_handoffs) != set(required):
        raise ValueError(
            "Phase-3 feature coverage handoff-family contract mismatch: "
            f"missing={sorted(set(required) - set(family_handoffs))} "
            f"extra={sorted(set(family_handoffs) - set(required))}"
        )

    subjects = {}
    for raw in subject_rows:
        row = dict(raw)
        if set(row) != PHASE3_FEATURE_SUBJECT_FIELDS:
            raise ValueError("Phase-3 feature coverage subject fields changed")
        if (
            str(row.get("version") or "")
            != PHASE3_FEATURE_SUBJECT_VERSION
        ):
            raise ValueError("Phase-3 feature coverage subject version changed")
        if row.get("snapshot_kind") != PHASE3_FEATURE_SNAPSHOT_KIND:
            raise ValueError("Phase-3 feature coverage snapshot kind changed")
        if row.get("feature_cutoff_inclusive") is not True:
            raise ValueError("Phase-3 feature coverage cutoff is not inclusive")
        token = normalize_address(str(row.get("token") or ""))
        if token in subjects:
            raise ValueError(
                f"Phase-3 feature coverage repeats subject: {token}"
            )
        subjects[token] = {
            "cutoff": _cutoff(row),
            "families": {},
        }
    if not subjects:
        raise ValueError("Phase-3 feature coverage has no subjects")

    family_missing_subjects = {}
    family_missing_values = {}
    family_row_counts = {}
    for family in required:
        handoff = dict(family_handoffs[family])
        expected_version, ready_key = FAMILY_HANDOFF_CONTRACTS[family]
        if str(handoff.get("version") or "") != expected_version:
            raise ValueError(
                f"{family} Phase-3 feature handoff version changed"
            )
        if str(handoff.get("feature_family") or "") != family:
            raise ValueError(
                f"{family} Phase-3 feature handoff family drift"
            )
        if _sha256(
            handoff.get("feature_registry_sha256"),
            label=f"{family} feature registry",
        ) != registry_sha:
            raise ValueError(
                f"{family} Phase-3 feature registry SHA drift"
            )
        if handoff.get(ready_key) is not True:
            raise ValueError(
                f"{family} Phase-3 feature family is not ready"
            )
        for flag in (
            "outcome_rows_consumed",
            "outcome_fields_exposed",
            "future_state_allowed",
        ):
            if handoff.get(flag) is not False:
                raise ValueError(
                    f"{family} Phase-3 feature handoff violates {flag}"
                )
        if int(handoff.get("feature_subjects", -1)) != len(subjects):
            raise ValueError(
                f"{family} Phase-3 feature subject count drift"
            )

        seen = set()
        missing_value_count = 0
        rows = []
        for raw in family_rows[family]:
            row = dict(raw)
            token = normalize_address(str(row.get("token") or ""))
            if token not in subjects:
                raise ValueError(
                    f"{family} feature row has unknown subject: {token}"
                )
            if token in seen:
                raise ValueError(
                    f"{family} feature row repeats subject: {token}"
                )
            seen.add(token)
            if row.get("snapshot_kind") != PHASE3_FEATURE_SNAPSHOT_KIND:
                raise ValueError(
                    f"{family} feature snapshot kind changed: {token}"
                )
            if row.get("feature_cutoff_inclusive") is not True:
                raise ValueError(
                    f"{family} feature cutoff is not inclusive: {token}"
                )
            if _cutoff(row) != subjects[token]["cutoff"]:
                raise ValueError(
                    f"{family} feature cutoff drift: {token}"
                )
            if _sha256(
                row.get("feature_registry_sha256"),
                label=f"{family} feature row registry",
            ) != registry_sha:
                raise ValueError(
                    f"{family} feature row registry drift: {token}"
                )
            values = row.get("feature_values")
            if not isinstance(values, Mapping):
                raise ValueError(
                    f"{family} feature values are missing: {token}"
                )
            expected_ids = feature_ids_by_family[family]
            if set(values) != expected_ids:
                raise ValueError(
                    f"{family} feature id coverage changed: {token}"
                )
            missing = row.get("missing_feature_ids")
            if not isinstance(missing, list):
                raise ValueError(
                    f"{family} missingness list is invalid: {token}"
                )
            missing_set = {str(value) for value in missing}
            if not missing_set <= expected_ids:
                raise ValueError(
                    f"{family} missingness contains unknown features: {token}"
                )
            actual_nulls = {
                feature_id
                for feature_id, value in values.items()
                if value is None
            }
            if missing_set != actual_nulls:
                raise ValueError(
                    f"{family} missingness does not match null values: {token}"
                )
            quality = row.get("data_quality")
            if not isinstance(quality, Mapping):
                raise ValueError(
                    f"{family} data quality is missing: {token}"
                )
            missing_value_count += len(missing_set)
            subjects[token]["families"][family] = {
                "missing_feature_ids": sorted(missing_set),
                "data_quality": dict(quality),
            }
            rows.append(row)

        family_row_counts[family] = len(rows)
        missing_subjects = set(subjects) - seen
        family_missing_subjects[family] = len(missing_subjects)
        family_missing_values[family] = missing_value_count
        if missing_subjects:
            raise ValueError(
                f"{family} Phase-3 feature coverage missing subjects: "
                f"{sorted(missing_subjects)[:20]}"
            )

    coverage_rows = []
    subjects_with_any_missing = 0
    for token in sorted(subjects):
        state = subjects[token]
        if set(state["families"]) != set(required):
            raise ValueError(
                f"Phase-3 feature coverage family drift: {token}"
            )
        missing_by_family = {
            family: state["families"][family][
                "missing_feature_ids"
            ]
            for family in required
        }
        if any(missing_by_family.values()):
            subjects_with_any_missing += 1
        coverage_rows.append({
            "version": PHASE3_FEATURE_COVERAGE_VERSION,
            "token": token,
            "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
            "feature_cutoff_block": state["cutoff"][0],
            "feature_cutoff_transaction_index": (
                None
                if state["cutoff"][1] == -1
                else state["cutoff"][1]
            ),
            "feature_cutoff_log_index": state["cutoff"][2],
            "feature_cutoff_inclusive": True,
            "required_families": required,
            "families_present": required,
            "missing_feature_ids_by_family": missing_by_family,
            "all_required_families_present": True,
            "outcome_fields_exposed": False,
            "future_state_allowed": False,
        })

    manifest = write_jsonl_snapshot(
        coverage_rows,
        output=output,
        provenance={
            "version": PHASE3_FEATURE_COVERAGE_VERSION,
            "feature_registry_sha256": registry_sha,
            "required_families": required,
            "subjects": len(subjects),
            "outcome_fields_exposed": False,
            "future_state_allowed": False,
        },
    )
    summary = {
        "version": PHASE3_FEATURE_COVERAGE_VERSION,
        "feature_registry_sha256": registry_sha,
        "required_families": required,
        "complete_feature_families": required,
        "feature_subjects": len(subjects),
        "coverage_rows": int(manifest["records"]),
        "coverage_rows_sha256": manifest["sha256"],
        "family_row_counts": dict(sorted(family_row_counts.items())),
        "family_missing_subjects": dict(
            sorted(family_missing_subjects.items())
        ),
        "family_missing_feature_values": dict(
            sorted(family_missing_values.items())
        ),
        "subjects_with_any_missing_values": subjects_with_any_missing,
        "matched_subject_coverage_equal": True,
        "missingness_recorded": True,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "feature_coverage_complete": True,
    }
    return manifest, summary


def build_phase3_feature_coverage_handoff(
    coverage_summary: Mapping[str, object],
    *,
    coverage_summary_sha256: str,
    feature_entry_handoff_sha256: str,
) -> dict:
    """Publish a leakage-safe equal-coverage proof for required families."""

    summary = dict(coverage_summary)
    if (
        str(summary.get("version") or "")
        != PHASE3_FEATURE_COVERAGE_VERSION
    ):
        raise ValueError("Phase-3 feature coverage handoff version changed")
    if summary.get("matched_subject_coverage_equal") is not True:
        raise ValueError("Phase-3 feature subject coverage is unequal")
    if summary.get("missingness_recorded") is not True:
        raise ValueError("Phase-3 feature missingness is not recorded")
    if summary.get("outcome_fields_exposed") is not False:
        raise ValueError("Phase-3 feature coverage exposes outcomes")
    if summary.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 feature coverage allows future state")
    if summary.get("feature_coverage_complete") is not True:
        raise ValueError("Phase-3 feature coverage is incomplete")

    return {
        "version": PHASE3_FEATURE_COVERAGE_HANDOFF_VERSION,
        "feature_registry_sha256": _sha256(
            summary.get("feature_registry_sha256"),
            label="Phase-3 feature coverage registry",
        ),
        "coverage_rows_sha256": _sha256(
            summary.get("coverage_rows_sha256"),
            label="Phase-3 feature coverage rows",
        ),
        "coverage_summary_sha256": _sha256(
            coverage_summary_sha256,
            label="Phase-3 feature coverage summary",
        ),
        "feature_entry_handoff_sha256": _sha256(
            feature_entry_handoff_sha256,
            label="Phase-3 feature entry handoff",
        ),
        "required_families": list(summary["required_families"]),
        "feature_subjects": int(summary["feature_subjects"]),
        "matched_subject_coverage_equal": True,
        "missingness_recorded": True,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "feature_coverage_complete": True,
    }
