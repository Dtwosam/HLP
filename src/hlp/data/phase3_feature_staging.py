"""Label-free Phase-3 feature staging bundle."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase3_feature_coverage import (
    PHASE3_FEATURE_COVERAGE_HANDOFF_VERSION,
    PHASE3_FEATURE_COVERAGE_VERSION,
)
from hlp.data.phase3_feature_entry import PHASE3_FEATURE_SNAPSHOT_KIND
from hlp.data.phase3_feature_registry import (
    validate_phase3_feature_registry,
)
from hlp.data.snapshot import write_jsonl_snapshot


PHASE3_FEATURE_STAGING_VERSION = "phase3-feature-staging-v1"
PHASE3_FEATURE_STAGING_HANDOFF_VERSION = (
    "phase3-feature-staging-handoff-v1"
)
PHASE3_FINAL_FEATURE_STORE_CHECKPOINT = "hlp-v1-phase3-feature-store"


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
        raise ValueError("Phase-3 feature staging cutoff is invalid")
    return block, tx, log


def _validate_value(
    feature_id: str,
    value: object,
    definition: Mapping[str, object],
    *,
    missing: bool,
) -> None:
    policy = str(definition["missingness_policy"])
    if value is None:
        if not missing:
            raise ValueError(
                f"{feature_id} is null without a missingness flag"
            )
        if policy != "null_with_flag":
            raise ValueError(
                f"{feature_id} cannot be null under {policy}"
            )
        return
    if missing:
        raise ValueError(
            f"{feature_id} is non-null but marked missing"
        )

    dtype = str(definition["dtype"])
    if dtype == "decimal_string":
        if not isinstance(value, str):
            raise ValueError(
                f"{feature_id} must be a decimal string"
            )
        try:
            decimal = Decimal(value)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(
                f"{feature_id} decimal string is invalid"
            ) from exc
        if not decimal.is_finite():
            raise ValueError(
                f"{feature_id} decimal string must be finite"
            )
    elif dtype == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{feature_id} must be an integer")
    elif dtype == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"{feature_id} must be a boolean")
    elif dtype == "string":
        if not isinstance(value, str):
            raise ValueError(f"{feature_id} must be a string")
    else:
        raise ValueError(
            f"{feature_id} has unsupported dtype: {dtype}"
        )


def materialize_phase3_feature_staging(
    coverage_rows: Iterable[Mapping[str, object]],
    family_rows: Mapping[
        str, Iterable[Mapping[str, object]]
    ],
    *,
    coverage_handoff: Mapping[str, object],
    feature_registry: Iterable[Mapping[str, object]],
    output: Path,
) -> tuple[dict, dict]:
    """Flatten equal-coverage families into a label-free staging bundle."""

    handoff = dict(coverage_handoff)
    if (
        str(handoff.get("version") or "")
        != PHASE3_FEATURE_COVERAGE_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 feature staging coverage version changed")
    if handoff.get("matched_subject_coverage_equal") is not True:
        raise ValueError("Phase-3 feature staging coverage is unequal")
    if handoff.get("missingness_recorded") is not True:
        raise ValueError("Phase-3 feature staging missingness is absent")
    if handoff.get("outcome_fields_exposed") is not False:
        raise ValueError("Phase-3 feature staging coverage exposes outcomes")
    if handoff.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 feature staging coverage allows future state")
    if handoff.get("feature_coverage_complete") is not True:
        raise ValueError("Phase-3 feature staging coverage is incomplete")

    registry_rows = [dict(row) for row in feature_registry]
    registry = validate_phase3_feature_registry(registry_rows)
    registry_sha = registry["registry_sha256"]
    if _sha256(
        handoff.get("feature_registry_sha256"),
        label="Phase-3 feature staging registry",
    ) != registry_sha:
        raise ValueError("Phase-3 feature staging registry SHA drift")
    definitions = {
        str(row["feature_id"]): row
        for row in registry_rows
    }
    ids_by_family = {}
    for row in registry_rows:
        ids_by_family.setdefault(
            str(row["family"]),
            set(),
        ).add(str(row["feature_id"]))

    required = sorted(
        str(value)
        for value in handoff.get("required_families") or []
    )
    if not required:
        raise ValueError("Phase-3 feature staging requires families")
    if set(family_rows) != set(required):
        raise ValueError(
            "Phase-3 feature staging family contract mismatch: "
            f"missing={sorted(set(required) - set(family_rows))} "
            f"extra={sorted(set(family_rows) - set(required))}"
        )
    unknown = set(required) - set(ids_by_family)
    if unknown:
        raise ValueError(
            "Phase-3 feature staging has unregistered families: "
            f"{sorted(unknown)}"
        )

    coverage = {}
    coverage_materialized = []
    for raw in coverage_rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE3_FEATURE_COVERAGE_VERSION
        ):
            raise ValueError("Phase-3 feature staging coverage row changed")
        token = normalize_address(str(row.get("token") or ""))
        if token in coverage:
            raise ValueError(
                f"Phase-3 feature staging repeats coverage token: {token}"
            )
        if row.get("snapshot_kind") != PHASE3_FEATURE_SNAPSHOT_KIND:
            raise ValueError(
                f"Phase-3 feature staging snapshot kind changed: {token}"
            )
        if row.get("feature_cutoff_inclusive") is not True:
            raise ValueError(
                f"Phase-3 feature staging cutoff is not inclusive: {token}"
            )
        if row.get("all_required_families_present") is not True:
            raise ValueError(
                f"Phase-3 feature staging coverage is incomplete: {token}"
            )
        if row.get("outcome_fields_exposed") is not False:
            raise ValueError(
                f"Phase-3 feature staging row exposes outcomes: {token}"
            )
        if row.get("future_state_allowed") is not False:
            raise ValueError(
                f"Phase-3 feature staging row allows future state: {token}"
            )
        if sorted(row.get("required_families") or []) != required:
            raise ValueError(
                f"Phase-3 feature staging required families drift: {token}"
            )
        if sorted(row.get("families_present") or []) != required:
            raise ValueError(
                f"Phase-3 feature staging family coverage drift: {token}"
            )
        raw_missing = row.get("missing_feature_ids_by_family")
        if not isinstance(raw_missing, Mapping):
            raise ValueError(
                f"Phase-3 feature staging missingness map absent: {token}"
            )
        missing_by_family = {
            str(family): sorted(str(value) for value in values)
            for family, values in raw_missing.items()
        }
        if set(missing_by_family) != set(required):
            raise ValueError(
                f"Phase-3 feature staging missingness families drift: {token}"
            )
        normalized = {
            **row,
            "token": token,
            "_cutoff": _cutoff(row),
            "_missing_by_family": missing_by_family,
        }
        coverage[token] = normalized
        coverage_materialized.append(row)

    if len(coverage) != int(handoff.get("feature_subjects", -1)):
        raise ValueError("Phase-3 feature staging subject count drift")

    family_by_token = {
        family: {}
        for family in required
    }
    for family in required:
        expected_ids = ids_by_family[family]
        for raw in family_rows[family]:
            row = dict(raw)
            token = normalize_address(str(row.get("token") or ""))
            if token not in coverage:
                raise ValueError(
                    f"{family} staging row has unknown subject: {token}"
                )
            if token in family_by_token[family]:
                raise ValueError(
                    f"{family} staging row repeats subject: {token}"
                )
            if row.get("snapshot_kind") != PHASE3_FEATURE_SNAPSHOT_KIND:
                raise ValueError(
                    f"{family} staging snapshot kind changed: {token}"
                )
            if row.get("feature_cutoff_inclusive") is not True:
                raise ValueError(
                    f"{family} staging cutoff is not inclusive: {token}"
                )
            if _cutoff(row) != coverage[token]["_cutoff"]:
                raise ValueError(
                    f"{family} staging cutoff drift: {token}"
                )
            if _sha256(
                row.get("feature_registry_sha256"),
                label=f"{family} staging registry",
            ) != registry_sha:
                raise ValueError(
                    f"{family} staging registry drift: {token}"
                )
            values = row.get("feature_values")
            if not isinstance(values, Mapping) or set(values) != expected_ids:
                raise ValueError(
                    f"{family} staging feature id coverage drift: {token}"
                )
            raw_missing = row.get("missing_feature_ids")
            if not isinstance(raw_missing, list):
                raise ValueError(
                    f"{family} staging missingness list invalid: {token}"
                )
            missing = {str(value) for value in raw_missing}
            if missing != set(
                coverage[token]["_missing_by_family"][family]
            ):
                raise ValueError(
                    f"{family} staging missingness/coverage drift: {token}"
                )
            for feature_id in sorted(expected_ids):
                _validate_value(
                    feature_id,
                    values[feature_id],
                    definitions[feature_id],
                    missing=feature_id in missing,
                )
            quality = row.get("data_quality")
            if not isinstance(quality, Mapping):
                raise ValueError(
                    f"{family} staging data-quality flags absent: {token}"
                )
            family_by_token[family][token] = {
                "values": dict(values),
                "missing": sorted(missing),
                "data_quality": dict(quality),
            }

        missing_subjects = set(coverage) - set(family_by_token[family])
        if missing_subjects:
            raise ValueError(
                f"{family} staging missing subjects: "
                f"{sorted(missing_subjects)[:20]}"
            )

    output_rows = []
    total_missing = 0
    for token in sorted(coverage):
        combined = {}
        missing = []
        data_quality = {}
        for family in required:
            state = family_by_token[family][token]
            overlap = set(combined) & set(state["values"])
            if overlap:
                raise ValueError(
                    f"Phase-3 staging feature ids overlap across families: "
                    f"{sorted(overlap)}"
                )
            combined.update(state["values"])
            missing.extend(state["missing"])
            data_quality[family] = state["data_quality"]
        expected_combined = set().union(
            *(ids_by_family[family] for family in required)
        )
        if set(combined) != expected_combined:
            raise ValueError(
                f"Phase-3 staging flattened feature coverage drift: {token}"
            )
        total_missing += len(missing)
        cutoff = coverage[token]["_cutoff"]
        output_rows.append({
            "version": PHASE3_FEATURE_STAGING_VERSION,
            "token": token,
            "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
            "feature_cutoff_block": cutoff[0],
            "feature_cutoff_transaction_index": (
                None if cutoff[1] == -1 else cutoff[1]
            ),
            "feature_cutoff_log_index": cutoff[2],
            "feature_cutoff_inclusive": True,
            "feature_registry_sha256": registry_sha,
            "included_families": required,
            "feature_values": dict(sorted(combined.items())),
            "missing_feature_ids": sorted(missing),
            "data_quality_by_family": data_quality,
            "outcome_fields_exposed": False,
            "future_state_allowed": False,
        })

    manifest = write_jsonl_snapshot(
        output_rows,
        output=output,
        provenance={
            "version": PHASE3_FEATURE_STAGING_VERSION,
            "feature_registry_sha256": registry_sha,
            "coverage_rows_sha256": handoff["coverage_rows_sha256"],
            "included_families": required,
            "outcome_rows_consumed": False,
            "outcome_fields_exposed": False,
            "future_state_allowed": False,
            "final_checkpoint_claimed": False,
        },
    )
    summary = {
        "version": PHASE3_FEATURE_STAGING_VERSION,
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_registry_sha256": registry_sha,
        "included_families": required,
        "feature_subjects": len(output_rows),
        "features_per_subject": len(
            set().union(
                *(ids_by_family[family] for family in required)
            )
        ),
        "feature_rows": int(manifest["records"]),
        "feature_rows_sha256": manifest["sha256"],
        "coverage_rows_sha256": str(handoff["coverage_rows_sha256"]),
        "missing_feature_values": total_missing,
        "matched_subject_coverage_equal": True,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "staging_bundle_ready": True,
        "final_checkpoint_name": PHASE3_FINAL_FEATURE_STORE_CHECKPOINT,
        "final_checkpoint_claimed": False,
    }
    return manifest, summary


def build_phase3_feature_staging_handoff(
    staging_summary: Mapping[str, object],
    *,
    staging_summary_sha256: str,
    feature_coverage_handoff_sha256: str,
) -> dict:
    """Bind a label-free partial feature bundle without claiming Phase 3 done."""

    summary = dict(staging_summary)
    if (
        str(summary.get("version") or "")
        != PHASE3_FEATURE_STAGING_VERSION
    ):
        raise ValueError("Phase-3 feature staging handoff version changed")
    if summary.get("matched_subject_coverage_equal") is not True:
        raise ValueError("Phase-3 feature staging coverage is unequal")
    if summary.get("missingness_recorded") is not True:
        raise ValueError("Phase-3 feature staging missingness is absent")
    if summary.get("data_quality_recorded") is not True:
        raise ValueError("Phase-3 feature staging data quality is absent")
    if summary.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-3 feature staging consumed outcome rows")
    if summary.get("outcome_fields_exposed") is not False:
        raise ValueError("Phase-3 feature staging exposes outcomes")
    if summary.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 feature staging allows future state")
    if summary.get("staging_bundle_ready") is not True:
        raise ValueError("Phase-3 feature staging bundle is not ready")
    if (
        summary.get("final_checkpoint_name")
        != PHASE3_FINAL_FEATURE_STORE_CHECKPOINT
    ):
        raise ValueError("Phase-3 final checkpoint name drift")
    if summary.get("final_checkpoint_claimed") is not False:
        raise ValueError("Phase-3 staging incorrectly claims final checkpoint")

    return {
        "version": PHASE3_FEATURE_STAGING_HANDOFF_VERSION,
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_registry_sha256": _sha256(
            summary.get("feature_registry_sha256"),
            label="Phase-3 feature staging registry",
        ),
        "feature_rows_sha256": _sha256(
            summary.get("feature_rows_sha256"),
            label="Phase-3 feature staging rows",
        ),
        "coverage_rows_sha256": _sha256(
            summary.get("coverage_rows_sha256"),
            label="Phase-3 feature staging coverage",
        ),
        "staging_summary_sha256": _sha256(
            staging_summary_sha256,
            label="Phase-3 feature staging summary",
        ),
        "feature_coverage_handoff_sha256": _sha256(
            feature_coverage_handoff_sha256,
            label="Phase-3 feature coverage handoff",
        ),
        "included_families": list(summary["included_families"]),
        "feature_subjects": int(summary["feature_subjects"]),
        "features_per_subject": int(summary["features_per_subject"]),
        "matched_subject_coverage_equal": True,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "staging_bundle_ready": True,
        "final_checkpoint_name": PHASE3_FINAL_FEATURE_STORE_CHECKPOINT,
        "final_checkpoint_claimed": False,
    }
