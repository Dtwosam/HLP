"""Final Phase-3 feature-store acceptance and immutable materialization."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase3_feature_coverage import (
    PHASE3_FEATURE_COVERAGE_HANDOFF_VERSION,
)
from hlp.data.phase3_feature_entry import PHASE3_FEATURE_SNAPSHOT_KIND
from hlp.data.phase3_feature_registry import (
    validate_phase3_feature_registry,
)
from hlp.data.phase3_feature_staging import (
    PHASE3_FEATURE_STAGING_HANDOFF_VERSION,
    PHASE3_FEATURE_STAGING_VERSION,
    PHASE3_FINAL_FEATURE_STORE_CHECKPOINT,
)
from hlp.data.snapshot import write_jsonl_snapshot


PHASE3_FEATURE_STORE_VERSION = "phase3-feature-store-v1"
PHASE3_FEATURE_STORE_HANDOFF_VERSION = (
    "phase3-feature-store-handoff-v1"
)


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
        raise ValueError("Phase-3 feature-store cutoff is invalid")
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
        if not missing or policy != "null_with_flag":
            raise ValueError(
                f"Phase-3 feature-store invalid null: {feature_id}"
            )
        return
    if missing:
        raise ValueError(
            f"Phase-3 feature-store non-null marked missing: {feature_id}"
        )

    dtype = str(definition["dtype"])
    if dtype == "decimal_string":
        if not isinstance(value, str):
            raise ValueError(
                f"Phase-3 feature-store decimal type drift: {feature_id}"
            )
        try:
            parsed = Decimal(value)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(
                f"Phase-3 feature-store decimal invalid: {feature_id}"
            ) from exc
        if not parsed.is_finite():
            raise ValueError(
                f"Phase-3 feature-store decimal non-finite: {feature_id}"
            )
    elif dtype == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(
                f"Phase-3 feature-store integer type drift: {feature_id}"
            )
    elif dtype == "boolean":
        if not isinstance(value, bool):
            raise ValueError(
                f"Phase-3 feature-store boolean type drift: {feature_id}"
            )
    elif dtype == "string":
        if not isinstance(value, str):
            raise ValueError(
                f"Phase-3 feature-store string type drift: {feature_id}"
            )
    else:
        raise ValueError(
            f"Phase-3 feature-store unsupported dtype: {dtype}"
        )


def materialize_phase3_feature_store(
    staging_rows: Iterable[Mapping[str, object]],
    *,
    staging_handoff: Mapping[str, object],
    coverage_handoff: Mapping[str, object],
    feature_coverage_handoff_sha256: str,
    feature_registry: Iterable[Mapping[str, object]],
    output: Path,
) -> tuple[dict, dict]:
    """Promote only an all-registry, equal-coverage, label-free staging bundle."""

    staging = dict(staging_handoff)
    coverage = dict(coverage_handoff)
    registry_rows = [dict(row) for row in feature_registry]
    registry = validate_phase3_feature_registry(registry_rows)
    registry_sha = registry["registry_sha256"]
    definitions = {
        str(row["feature_id"]): row
        for row in registry_rows
    }
    all_feature_ids = set(definitions)
    all_families = list(registry["families"])

    if (
        str(staging.get("version") or "")
        != PHASE3_FEATURE_STAGING_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 finalizer staging version changed")
    if staging.get("staging_bundle_ready") is not True:
        raise ValueError("Phase-3 finalizer staging bundle is not ready")
    if staging.get("final_checkpoint_claimed") is not False:
        raise ValueError(
            "Phase-3 finalizer requires an unclaimed staging bundle"
        )
    if staging.get("final_checkpoint_name") != (
        PHASE3_FINAL_FEATURE_STORE_CHECKPOINT
    ):
        raise ValueError("Phase-3 finalizer checkpoint name drift")

    if (
        str(coverage.get("version") or "")
        != PHASE3_FEATURE_COVERAGE_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 finalizer coverage version changed")
    if coverage.get("feature_coverage_complete") is not True:
        raise ValueError("Phase-3 finalizer coverage is incomplete")
    if coverage.get("matched_subject_coverage_equal") is not True:
        raise ValueError("Phase-3 finalizer subject coverage is unequal")

    for label, handoff in (
        ("staging", staging),
        ("coverage", coverage),
    ):
        if _sha256(
            handoff.get("feature_registry_sha256"),
            label=f"Phase-3 finalizer {label} registry",
        ) != registry_sha:
            raise ValueError(
                f"Phase-3 finalizer {label} registry SHA drift"
            )
        if handoff.get("outcome_fields_exposed") is not False:
            raise ValueError(
                f"Phase-3 finalizer {label} exposes outcome fields"
            )
        if handoff.get("future_state_allowed") is not False:
            raise ValueError(
                f"Phase-3 finalizer {label} allows future state"
            )
        if handoff.get("missingness_recorded") is not True:
            raise ValueError(
                f"Phase-3 finalizer {label} lacks missingness"
            )

    if staging.get("data_quality_recorded") is not True:
        raise ValueError("Phase-3 finalizer staging lacks data quality")
    if staging.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-3 finalizer staging consumed outcomes")

    expected_coverage_handoff_sha = _sha256(
        feature_coverage_handoff_sha256,
        label="Phase-3 finalizer coverage handoff",
    )
    if _sha256(
        staging.get("feature_coverage_handoff_sha256"),
        label="Phase-3 staging coverage handoff",
    ) != expected_coverage_handoff_sha:
        raise ValueError(
            "Phase-3 finalizer staging/coverage handoff linkage drift"
        )
    if _sha256(
        staging.get("coverage_rows_sha256"),
        label="Phase-3 staging coverage rows",
    ) != _sha256(
        coverage.get("coverage_rows_sha256"),
        label="Phase-3 coverage rows",
    ):
        raise ValueError(
            "Phase-3 finalizer staging/coverage row SHA drift"
        )

    included = sorted(
        str(value)
        for value in staging.get("included_families") or []
    )
    required = sorted(
        str(value)
        for value in coverage.get("required_families") or []
    )
    if included != all_families or required != all_families:
        raise ValueError(
            "Phase-3 finalizer does not include every registered family"
        )
    if included != required:
        raise ValueError(
            "Phase-3 finalizer staging/coverage family drift"
        )
    if int(staging.get("features_per_subject", -1)) != int(
        registry["features"]
    ):
        raise ValueError(
            "Phase-3 finalizer staging feature count is incomplete"
        )
    if int(staging.get("feature_subjects", -1)) != int(
        coverage.get("feature_subjects", -2)
    ):
        raise ValueError(
            "Phase-3 finalizer staging/coverage subject count drift"
        )

    rows = []
    seen = set()
    total_missing = 0
    for raw in staging_rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE3_FEATURE_STAGING_VERSION
        ):
            raise ValueError("Phase-3 finalizer staging row version changed")
        token = normalize_address(str(row.get("token") or ""))
        if token in seen:
            raise ValueError(
                f"Phase-3 finalizer repeats subject token: {token}"
            )
        seen.add(token)
        _cutoff(row)
        if row.get("snapshot_kind") != PHASE3_FEATURE_SNAPSHOT_KIND:
            raise ValueError(
                f"Phase-3 finalizer snapshot kind drift: {token}"
            )
        if row.get("feature_cutoff_inclusive") is not True:
            raise ValueError(
                f"Phase-3 finalizer cutoff semantics drift: {token}"
            )
        if _sha256(
            row.get("feature_registry_sha256"),
            label=f"{token} Phase-3 finalizer registry",
        ) != registry_sha:
            raise ValueError(
                f"Phase-3 finalizer row registry drift: {token}"
            )
        if sorted(row.get("included_families") or []) != all_families:
            raise ValueError(
                f"Phase-3 finalizer row family coverage drift: {token}"
            )
        values = row.get("feature_values")
        if not isinstance(values, Mapping) or set(values) != all_feature_ids:
            raise ValueError(
                f"Phase-3 finalizer row feature coverage drift: {token}"
            )
        missing_raw = row.get("missing_feature_ids")
        if not isinstance(missing_raw, list):
            raise ValueError(
                f"Phase-3 finalizer row missingness invalid: {token}"
            )
        missing = {str(value) for value in missing_raw}
        if not missing <= all_feature_ids:
            raise ValueError(
                f"Phase-3 finalizer row missingness has unknown ids: {token}"
            )
        nulls = {
            feature_id
            for feature_id, value in values.items()
            if value is None
        }
        if missing != nulls:
            raise ValueError(
                f"Phase-3 finalizer row missing/null drift: {token}"
            )
        for feature_id in sorted(all_feature_ids):
            _validate_value(
                feature_id,
                values[feature_id],
                definitions[feature_id],
                missing=feature_id in missing,
            )
        quality = row.get("data_quality_by_family")
        if not isinstance(quality, Mapping) or sorted(quality) != all_families:
            raise ValueError(
                f"Phase-3 finalizer row data-quality coverage drift: {token}"
            )
        if row.get("outcome_fields_exposed") is not False:
            raise ValueError(
                f"Phase-3 finalizer row exposes outcomes: {token}"
            )
        if row.get("future_state_allowed") is not False:
            raise ValueError(
                f"Phase-3 finalizer row allows future state: {token}"
            )
        total_missing += len(missing)
        rows.append({
            "version": PHASE3_FEATURE_STORE_VERSION,
            "token": token,
            "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
            "feature_cutoff_block": int(row["feature_cutoff_block"]),
            "feature_cutoff_transaction_index": row.get(
                "feature_cutoff_transaction_index"
            ),
            "feature_cutoff_log_index": int(
                row["feature_cutoff_log_index"]
            ),
            "feature_cutoff_inclusive": True,
            "feature_registry_sha256": registry_sha,
            "included_families": all_families,
            "feature_values": dict(sorted(values.items())),
            "missing_feature_ids": sorted(missing),
            "data_quality_by_family": {
                family: dict(quality[family])
                for family in all_families
            },
            "outcome_fields_exposed": False,
            "future_state_allowed": False,
        })

    expected_subjects = int(staging["feature_subjects"])
    if len(rows) != expected_subjects:
        raise ValueError(
            "Phase-3 finalizer staging row count drift"
        )
    if not rows:
        raise ValueError("Phase-3 finalizer has no feature subjects")
    rows.sort(key=lambda row: row["token"])

    manifest = write_jsonl_snapshot(
        rows,
        output=output,
        provenance={
            "version": PHASE3_FEATURE_STORE_VERSION,
            "checkpoint_name": PHASE3_FINAL_FEATURE_STORE_CHECKPOINT,
            "feature_registry_sha256": registry_sha,
            "staging_rows_sha256": staging["feature_rows_sha256"],
            "coverage_rows_sha256": coverage["coverage_rows_sha256"],
            "included_families": all_families,
            "features_per_subject": int(registry["features"]),
            "matched_subject_coverage_equal": True,
            "missingness_recorded": True,
            "data_quality_recorded": True,
            "outcome_rows_consumed": False,
            "outcome_fields_exposed": False,
            "future_state_allowed": False,
            "final_checkpoint_claimed": True,
        },
    )
    summary = {
        "version": PHASE3_FEATURE_STORE_VERSION,
        "checkpoint_name": PHASE3_FINAL_FEATURE_STORE_CHECKPOINT,
        "feature_registry_sha256": registry_sha,
        "included_families": all_families,
        "feature_subjects": len(rows),
        "features_per_subject": int(registry["features"]),
        "feature_rows": int(manifest["records"]),
        "feature_rows_sha256": manifest["sha256"],
        "staging_rows_sha256": str(staging["feature_rows_sha256"]),
        "coverage_rows_sha256": str(coverage["coverage_rows_sha256"]),
        "missing_feature_values": total_missing,
        "all_registered_families_included": True,
        "all_registered_features_included": True,
        "matched_subject_coverage_equal": True,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "feature_store_ready": True,
        "final_checkpoint_claimed": True,
    }
    return manifest, summary


def build_phase3_feature_store_handoff(
    feature_store_summary: Mapping[str, object],
    *,
    feature_store_summary_sha256: str,
    staging_handoff_sha256: str,
    feature_coverage_handoff_sha256: str,
) -> dict:
    """Publish the final Phase-3 checkpoint only after full acceptance."""

    summary = dict(feature_store_summary)
    if (
        str(summary.get("version") or "")
        != PHASE3_FEATURE_STORE_VERSION
    ):
        raise ValueError("Phase-3 feature-store handoff version changed")
    if summary.get("checkpoint_name") != (
        PHASE3_FINAL_FEATURE_STORE_CHECKPOINT
    ):
        raise ValueError("Phase-3 feature-store checkpoint name drift")
    for flag in (
        "all_registered_families_included",
        "all_registered_features_included",
        "matched_subject_coverage_equal",
        "missingness_recorded",
        "data_quality_recorded",
        "feature_store_ready",
        "final_checkpoint_claimed",
    ):
        if summary.get(flag) is not True:
            raise ValueError(
                f"Phase-3 feature-store handoff lacks {flag}"
            )
    for flag in (
        "outcome_rows_consumed",
        "outcome_fields_exposed",
        "future_state_allowed",
    ):
        if summary.get(flag) is not False:
            raise ValueError(
                f"Phase-3 feature-store handoff violates {flag}"
            )
    return {
        "version": PHASE3_FEATURE_STORE_HANDOFF_VERSION,
        "checkpoint_name": PHASE3_FINAL_FEATURE_STORE_CHECKPOINT,
        "feature_registry_sha256": _sha256(
            summary.get("feature_registry_sha256"),
            label="Phase-3 feature-store registry",
        ),
        "feature_rows_sha256": _sha256(
            summary.get("feature_rows_sha256"),
            label="Phase-3 feature-store rows",
        ),
        "feature_store_summary_sha256": _sha256(
            feature_store_summary_sha256,
            label="Phase-3 feature-store summary",
        ),
        "staging_handoff_sha256": _sha256(
            staging_handoff_sha256,
            label="Phase-3 feature-store staging handoff",
        ),
        "feature_coverage_handoff_sha256": _sha256(
            feature_coverage_handoff_sha256,
            label="Phase-3 feature-store coverage handoff",
        ),
        "staging_rows_sha256": _sha256(
            summary.get("staging_rows_sha256"),
            label="Phase-3 feature-store staging rows",
        ),
        "coverage_rows_sha256": _sha256(
            summary.get("coverage_rows_sha256"),
            label="Phase-3 feature-store coverage rows",
        ),
        "included_families": list(summary["included_families"]),
        "feature_subjects": int(summary["feature_subjects"]),
        "features_per_subject": int(summary["features_per_subject"]),
        "missing_feature_values": int(
            summary["missing_feature_values"]
        ),
        "all_registered_families_included": True,
        "all_registered_features_included": True,
        "matched_subject_coverage_equal": True,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "feature_store_ready": True,
        "final_checkpoint_claimed": True,
    }
