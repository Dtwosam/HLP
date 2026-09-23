"""Guarded Phase-4 entry: join frozen features to frozen outcomes."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase2_dataset import (
    PHASE2_CHECKPOINT_NAME,
    PHASE2_DATASET_HANDOFF_VERSION,
    PHASE2_DATASET_VERSION,
)
from hlp.data.phase2_outcomes import PHASE2_OUTCOME_LABEL_VERSION
from hlp.data.phase3_feature_coverage import (
    PHASE3_FEATURE_COVERAGE_HANDOFF_VERSION,
)
from hlp.data.phase3_feature_entry import (
    PHASE3_FEATURE_ENTRY_HANDOFF_VERSION,
    PHASE3_FEATURE_SNAPSHOT_KIND,
)
from hlp.data.phase3_feature_staging import (
    PHASE3_FINAL_FEATURE_STORE_CHECKPOINT,
)
from hlp.data.phase3_feature_store import (
    PHASE3_FEATURE_STORE_HANDOFF_VERSION,
    PHASE3_FEATURE_STORE_VERSION,
)
from hlp.data.snapshot import write_jsonl_snapshot


PHASE4_DISCOVERY_ENTRY_VERSION = "phase4-discovery-entry-v1"
PHASE4_DISCOVERY_ENTRY_HANDOFF_VERSION = (
    "phase4-discovery-entry-handoff-v1"
)
PHASE4_DISCOVERY_CHECKPOINT_NAME = "hlp-v1-phase4-discovery"


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower().removeprefix("sha256:")
    if len(text) != 64:
        raise ValueError(f"{label} SHA-256 is invalid")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} SHA-256 is invalid") from exc
    return text


def _decimal(value: object, *, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label} is not a decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{label} is not finite")
    return result


def _share(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        raise ValueError("Phase-4 discovery entry denominator is not positive")
    with localcontext() as context:
        context.prec = 80
        value = Decimal(numerator) / Decimal(denominator)
        if value == 0:
            return "0"
        return format(value.normalize(context=context), "f")


def _event(
    row: Mapping[str, object],
    *,
    prefix: str,
) -> tuple[int, int, int]:
    block = int(row.get(f"{prefix}_block", -1))
    raw_tx = row.get(f"{prefix}_transaction_index")
    tx = -1 if raw_tx is None else int(raw_tx)
    log = int(row.get(f"{prefix}_log_index", -1))
    if block < 0 or tx < -1 or log < 0:
        raise ValueError(
            f"Phase-4 discovery entry {prefix} event is invalid"
        )
    return block, tx, log


def _feature_cutoff(row: Mapping[str, object]) -> tuple[int, int, int]:
    block = int(row.get("feature_cutoff_block", -1))
    raw_tx = row.get("feature_cutoff_transaction_index")
    tx = -1 if raw_tx is None else int(raw_tx)
    log = int(row.get("feature_cutoff_log_index", -1))
    if block < 0 or tx < -1 or log < 0:
        raise ValueError("Phase-4 discovery feature cutoff is invalid")
    return block, tx, log


def _validate_handoffs(
    *,
    phase2_dataset_handoff: Mapping[str, object],
    feature_store_handoff: Mapping[str, object],
    coverage_handoff: Mapping[str, object],
    feature_entry_handoff: Mapping[str, object],
    phase2_dataset_handoff_sha256: str,
    feature_coverage_handoff_sha256: str,
    feature_entry_handoff_sha256: str,
) -> tuple[dict, dict, dict, dict]:
    phase2 = dict(phase2_dataset_handoff)
    store = dict(feature_store_handoff)
    coverage = dict(coverage_handoff)
    entry = dict(feature_entry_handoff)

    if str(phase2.get("version") or "") != PHASE2_DATASET_HANDOFF_VERSION:
        raise ValueError("Phase-4 entry Phase-2 handoff version changed")
    if phase2.get("checkpoint_name") != PHASE2_CHECKPOINT_NAME:
        raise ValueError("Phase-4 entry Phase-2 checkpoint changed")
    for flag in (
        "phase2_universe_frozen",
        "phase2_dump_detector_frozen",
        "outcome_labels_computed",
        "phase2_dataset_ready",
    ):
        if phase2.get(flag) is not True:
            raise ValueError(f"Phase-4 entry Phase-2 handoff lacks {flag}")
    if phase2.get("phase3_features_attached") is not False:
        raise ValueError(
            "Phase-4 entry requires labels frozen before feature attachment"
        )

    if (
        str(store.get("version") or "")
        != PHASE3_FEATURE_STORE_HANDOFF_VERSION
    ):
        raise ValueError("Phase-4 entry feature-store handoff version changed")
    if store.get("checkpoint_name") != PHASE3_FINAL_FEATURE_STORE_CHECKPOINT:
        raise ValueError("Phase-4 entry feature-store checkpoint changed")
    for flag in (
        "all_registered_families_included",
        "all_registered_features_included",
        "matched_subject_coverage_equal",
        "feature_store_ready",
        "final_checkpoint_claimed",
    ):
        if store.get(flag) is not True:
            raise ValueError(f"Phase-4 entry feature store lacks {flag}")
    if store.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-4 entry feature store consumed outcomes")
    if store.get("outcome_fields_exposed") is not False:
        raise ValueError("Phase-4 entry feature store exposes outcomes")
    if store.get("future_state_allowed") is not False:
        raise ValueError("Phase-4 entry feature store allows future state")

    if (
        str(coverage.get("version") or "")
        != PHASE3_FEATURE_COVERAGE_HANDOFF_VERSION
    ):
        raise ValueError("Phase-4 entry coverage handoff version changed")
    if coverage.get("feature_coverage_complete") is not True:
        raise ValueError("Phase-4 entry feature coverage is incomplete")
    if coverage.get("matched_subject_coverage_equal") is not True:
        raise ValueError("Phase-4 entry feature coverage is unequal")
    if coverage.get("outcome_fields_exposed") is not False:
        raise ValueError("Phase-4 entry coverage exposes outcomes")
    if coverage.get("future_state_allowed") is not False:
        raise ValueError("Phase-4 entry coverage allows future state")

    if (
        str(entry.get("version") or "")
        != PHASE3_FEATURE_ENTRY_HANDOFF_VERSION
    ):
        raise ValueError("Phase-4 entry feature-entry handoff version changed")
    if entry.get("phase3_feature_entry_ready") is not True:
        raise ValueError("Phase-4 entry feature-entry is not ready")
    if entry.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-4 feature-entry consumed outcomes")
    if entry.get("outcome_fields_exposed") is not False:
        raise ValueError("Phase-4 feature-entry exposes outcomes")
    if entry.get("future_state_allowed") is not False:
        raise ValueError("Phase-4 feature-entry allows future state")

    expected_coverage_sha = _sha256(
        feature_coverage_handoff_sha256,
        label="Phase-4 feature coverage handoff",
    )
    if _sha256(
        store.get("feature_coverage_handoff_sha256"),
        label="Phase-4 feature-store coverage link",
    ) != expected_coverage_sha:
        raise ValueError("Phase-4 feature-store/coverage linkage drift")

    expected_entry_sha = _sha256(
        feature_entry_handoff_sha256,
        label="Phase-4 feature-entry handoff",
    )
    if _sha256(
        coverage.get("feature_entry_handoff_sha256"),
        label="Phase-4 coverage feature-entry link",
    ) != expected_entry_sha:
        raise ValueError("Phase-4 coverage/feature-entry linkage drift")

    expected_phase2_sha = _sha256(
        phase2_dataset_handoff_sha256,
        label="Phase-4 Phase-2 dataset handoff",
    )
    if _sha256(
        entry.get("phase2_dataset_handoff_sha256"),
        label="Phase-4 feature-entry Phase-2 link",
    ) != expected_phase2_sha:
        raise ValueError("Phase-4 feature-entry/Phase-2 linkage drift")

    if int(phase2.get("snapshot_head_block", -1)) != int(
        entry.get("snapshot_head_block", -2)
    ):
        raise ValueError("Phase-4 Phase-2/feature-entry snapshot drift")
    if _sha256(
        phase2.get("eligible_universe_sha256"),
        label="Phase-4 Phase-2 universe",
    ) != _sha256(
        entry.get("eligible_universe_sha256"),
        label="Phase-4 feature-entry universe",
    ):
        raise ValueError("Phase-4 Phase-2/feature-entry universe drift")
    if int(phase2.get("tokens", -1)) != int(entry.get("universe_tokens", -2)):
        raise ValueError("Phase-4 Phase-2/feature-entry token count drift")

    subjects = int(store.get("feature_subjects", -1))
    if subjects <= 0:
        raise ValueError("Phase-4 feature store has no subjects")
    if subjects != int(coverage.get("feature_subjects", -2)):
        raise ValueError("Phase-4 store/coverage subject count drift")
    if subjects != int(entry.get("feature_subjects", -3)):
        raise ValueError("Phase-4 store/entry subject count drift")
    if subjects != int(phase2.get("confirmed_dump_tokens", -4)):
        raise ValueError("Phase-4 features do not match confirmed dumps")
    return phase2, store, coverage, entry


def materialize_phase4_discovery_entry(
    phase2_rows: Iterable[Mapping[str, object]],
    feature_rows: Iterable[Mapping[str, object]],
    *,
    phase2_dataset_handoff: Mapping[str, object],
    feature_store_handoff: Mapping[str, object],
    coverage_handoff: Mapping[str, object],
    feature_entry_handoff: Mapping[str, object],
    phase2_dataset_handoff_sha256: str,
    feature_store_handoff_sha256: str,
    feature_coverage_handoff_sha256: str,
    feature_entry_handoff_sha256: str,
    output: Path,
) -> tuple[dict, dict]:
    """Join labels only after the final causal feature store is frozen."""

    phase2, store, _, entry = _validate_handoffs(
        phase2_dataset_handoff=phase2_dataset_handoff,
        feature_store_handoff=feature_store_handoff,
        coverage_handoff=coverage_handoff,
        feature_entry_handoff=feature_entry_handoff,
        phase2_dataset_handoff_sha256=phase2_dataset_handoff_sha256,
        feature_coverage_handoff_sha256=feature_coverage_handoff_sha256,
        feature_entry_handoff_sha256=feature_entry_handoff_sha256,
    )
    registry_sha = _sha256(
        store.get("feature_registry_sha256"),
        label="Phase-4 feature registry",
    )

    dataset = {}
    outcome_eligible = {}
    for raw in phase2_rows:
        row = dict(raw)
        if str(row.get("version") or "") != PHASE2_DATASET_VERSION:
            raise ValueError("Phase-4 Phase-2 dataset row version changed")
        token = normalize_address(str(row.get("token") or ""))
        if token in dataset:
            raise ValueError(f"Phase-4 Phase-2 dataset repeats token: {token}")
        if row.get("phase2_universe_frozen") is not True:
            raise ValueError(f"Phase-4 Phase-2 universe is not frozen: {token}")
        if row.get("phase2_dump_detector_frozen") is not True:
            raise ValueError(f"Phase-4 Phase-2 detector is not frozen: {token}")
        if row.get("outcome_labels_computed") is not True:
            raise ValueError(f"Phase-4 Phase-2 labels absent: {token}")
        if row.get("phase3_features_attached") is not False:
            raise ValueError(
                f"Phase-4 Phase-2 row already contains features: {token}"
            )
        outcome = row.get("outcome")
        if not isinstance(outcome, Mapping):
            raise ValueError(f"Phase-4 Phase-2 outcome missing: {token}")
        outcome = dict(outcome)
        if str(outcome.get("version") or "") != PHASE2_OUTCOME_LABEL_VERSION:
            raise ValueError(f"Phase-4 outcome version changed: {token}")
        if normalize_address(str(outcome.get("token") or "")) != token:
            raise ValueError(f"Phase-4 outcome token drift: {token}")
        dataset[token] = row
        if outcome.get("outcome_eligible") is not True:
            continue
        if outcome.get("dump_status") != "confirmed":
            raise ValueError(
                f"Phase-4 eligible outcome is not confirmed: {token}"
            )
        if outcome.get("live_signal_semantics") != "confirmation_event":
            raise ValueError(
                f"Phase-4 eligible outcome live semantics drift: {token}"
            )
        comeback = outcome.get("comeback_5x")
        if not isinstance(comeback, bool):
            raise ValueError(f"Phase-4 5x label is invalid: {token}")
        multiple = _decimal(
            outcome.get("max_post_dump_multiple"),
            label=f"{token} max post-dump multiple",
        )
        if multiple < 0:
            raise ValueError(
                f"Phase-4 max post-dump multiple is negative: {token}"
            )
        if comeback != (multiple >= Decimal("5")):
            raise ValueError(
                f"Phase-4 5x label/magnitude disagree: {token}"
            )
        outcome_eligible[token] = outcome

    if len(dataset) != int(phase2.get("tokens", -1)):
        raise ValueError("Phase-4 Phase-2 dataset row count drift")
    if len(outcome_eligible) != int(phase2.get("confirmed_dump_tokens", -1)):
        raise ValueError("Phase-4 eligible outcome count drift")

    features = {}
    for raw in feature_rows:
        row = dict(raw)
        if str(row.get("version") or "") != PHASE3_FEATURE_STORE_VERSION:
            raise ValueError("Phase-4 feature-store row version changed")
        token = normalize_address(str(row.get("token") or ""))
        if token in features:
            raise ValueError(f"Phase-4 feature store repeats token: {token}")
        if row.get("snapshot_kind") != PHASE3_FEATURE_SNAPSHOT_KIND:
            raise ValueError(f"Phase-4 feature snapshot drift: {token}")
        if row.get("feature_cutoff_inclusive") is not True:
            raise ValueError(f"Phase-4 feature cutoff is not inclusive: {token}")
        if _sha256(
            row.get("feature_registry_sha256"),
            label=f"{token} Phase-4 feature registry",
        ) != registry_sha:
            raise ValueError(f"Phase-4 feature registry drift: {token}")
        values = row.get("feature_values")
        if not isinstance(values, Mapping) or not values:
            raise ValueError(f"Phase-4 feature values missing: {token}")
        missing = row.get("missing_feature_ids")
        if not isinstance(missing, list):
            raise ValueError(f"Phase-4 feature missingness invalid: {token}")
        if set(str(value) for value in missing) != {
            feature_id
            for feature_id, value in values.items()
            if value is None
        }:
            raise ValueError(f"Phase-4 feature missingness drift: {token}")
        if row.get("outcome_fields_exposed") is not False:
            raise ValueError(f"Phase-4 frozen feature row exposes outcomes: {token}")
        if row.get("future_state_allowed") is not False:
            raise ValueError(f"Phase-4 frozen feature row allows future state: {token}")
        features[token] = row

    if set(features) != set(outcome_eligible):
        raise ValueError(
            "Phase-4 feature/outcome subject membership drift: "
            f"missing_features={sorted(set(outcome_eligible)-set(features))[:20]} "
            f"extra_features={sorted(set(features)-set(outcome_eligible))[:20]}"
        )
    if len(features) != int(store.get("feature_subjects", -1)):
        raise ValueError("Phase-4 feature-store row count drift")

    rows = []
    positives = 0
    for token in sorted(features):
        feature = features[token]
        outcome = outcome_eligible[token]
        if _feature_cutoff(feature) != _event(outcome, prefix="confirmation"):
            raise ValueError(
                f"Phase-4 feature/outcome confirmation cutoff drift: {token}"
            )
        comeback = bool(outcome["comeback_5x"])
        positives += int(comeback)
        rows.append({
            "version": PHASE4_DISCOVERY_ENTRY_VERSION,
            "token": token,
            "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
            "feature_cutoff_block": int(feature["feature_cutoff_block"]),
            "feature_cutoff_transaction_index": feature.get(
                "feature_cutoff_transaction_index"
            ),
            "feature_cutoff_log_index": int(
                feature["feature_cutoff_log_index"]
            ),
            "feature_cutoff_inclusive": True,
            "feature_registry_sha256": registry_sha,
            "included_families": list(feature["included_families"]),
            "feature_values": dict(feature["feature_values"]),
            "missing_feature_ids": list(feature["missing_feature_ids"]),
            "data_quality_by_family": dict(
                feature["data_quality_by_family"]
            ),
            "universe": dict(dataset[token]["universe"]),
            "outcome": dict(outcome),
            "target_comeback_5x": comeback,
            "target_max_post_dump_multiple": str(
                outcome["max_post_dump_multiple"]
            ),
            "labels_joined_after_feature_freeze": True,
            "feature_values_mutated": False,
            "phase4_discovery_only": True,
        })

    if positives != int(phase2.get("comeback_5x_tokens", -1)):
        raise ValueError("Phase-4 5x positive count drift")

    manifest = write_jsonl_snapshot(
        rows,
        output=output,
        provenance={
            "version": PHASE4_DISCOVERY_ENTRY_VERSION,
            "phase2_checkpoint_name": PHASE2_CHECKPOINT_NAME,
            "phase3_checkpoint_name": PHASE3_FINAL_FEATURE_STORE_CHECKPOINT,
            "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
            "phase2_dataset_handoff_sha256": _sha256(
                phase2_dataset_handoff_sha256,
                label="Phase-4 Phase-2 handoff",
            ),
            "feature_store_handoff_sha256": _sha256(
                feature_store_handoff_sha256,
                label="Phase-4 feature-store handoff",
            ),
            "feature_coverage_handoff_sha256": _sha256(
                feature_coverage_handoff_sha256,
                label="Phase-4 coverage handoff",
            ),
            "feature_entry_handoff_sha256": _sha256(
                feature_entry_handoff_sha256,
                label="Phase-4 feature-entry handoff",
            ),
            "feature_registry_sha256": registry_sha,
            "labels_joined_after_feature_freeze": True,
            "feature_values_mutated": False,
            "phase4_discovery_checkpoint_claimed": False,
        },
    )
    summary = {
        "version": PHASE4_DISCOVERY_ENTRY_VERSION,
        "phase2_checkpoint_name": PHASE2_CHECKPOINT_NAME,
        "phase3_checkpoint_name": PHASE3_FINAL_FEATURE_STORE_CHECKPOINT,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "snapshot_head_block": int(entry["snapshot_head_block"]),
        "eligible_universe_sha256": str(entry["eligible_universe_sha256"]),
        "feature_registry_sha256": registry_sha,
        "discovery_rows_sha256": manifest["sha256"],
        "discovery_subjects": len(rows),
        "comeback_5x_tokens": positives,
        "comeback_5x_base_rate": _share(positives, len(rows)),
        "continuous_max_post_dump_multiple_retained": True,
        "exact_confirmation_cutoff_alignment": True,
        "matched_feature_coverage_equal": True,
        "universe_context_retained": True,
        "labels_joined_after_feature_freeze": True,
        "feature_values_mutated": False,
        "phase4_discovery_only": True,
        "phase4_discovery_entry_ready": True,
        "phase4_discovery_checkpoint_claimed": False,
    }
    return manifest, summary


def build_phase4_discovery_entry_handoff(
    discovery_summary: Mapping[str, object],
    *,
    discovery_summary_sha256: str,
    phase2_dataset_handoff_sha256: str,
    feature_store_handoff_sha256: str,
    feature_coverage_handoff_sha256: str,
    feature_entry_handoff_sha256: str,
) -> dict:
    """Publish a join-ready research cohort without claiming discovery."""

    summary = dict(discovery_summary)
    if (
        str(summary.get("version") or "")
        != PHASE4_DISCOVERY_ENTRY_VERSION
    ):
        raise ValueError("Phase-4 discovery-entry handoff version changed")
    if summary.get("phase4_checkpoint_name") != (
        PHASE4_DISCOVERY_CHECKPOINT_NAME
    ):
        raise ValueError("Phase-4 discovery checkpoint name changed")
    for flag in (
        "continuous_max_post_dump_multiple_retained",
        "exact_confirmation_cutoff_alignment",
        "matched_feature_coverage_equal",
        "universe_context_retained",
        "labels_joined_after_feature_freeze",
        "phase4_discovery_only",
        "phase4_discovery_entry_ready",
    ):
        if summary.get(flag) is not True:
            raise ValueError(f"Phase-4 discovery entry lacks {flag}")
    if summary.get("feature_values_mutated") is not False:
        raise ValueError("Phase-4 discovery entry mutated frozen features")
    if summary.get("phase4_discovery_checkpoint_claimed") is not False:
        raise ValueError("Phase-4 discovery entry claimed final discovery")

    return {
        "version": PHASE4_DISCOVERY_ENTRY_HANDOFF_VERSION,
        "phase2_checkpoint_name": PHASE2_CHECKPOINT_NAME,
        "phase3_checkpoint_name": PHASE3_FINAL_FEATURE_STORE_CHECKPOINT,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "snapshot_head_block": int(summary["snapshot_head_block"]),
        "eligible_universe_sha256": _sha256(
            summary.get("eligible_universe_sha256"),
            label="Phase-4 discovery universe",
        ),
        "feature_registry_sha256": _sha256(
            summary.get("feature_registry_sha256"),
            label="Phase-4 discovery feature registry",
        ),
        "feature_registry_file_sha256": _sha256(
            summary.get("feature_registry_file_sha256"),
            label="Phase-4 discovery feature registry file",
        ),
        "discovery_rows_sha256": _sha256(
            summary.get("discovery_rows_sha256"),
            label="Phase-4 discovery rows",
        ),
        "discovery_summary_sha256": _sha256(
            discovery_summary_sha256,
            label="Phase-4 discovery summary",
        ),
        "phase2_dataset_handoff_sha256": _sha256(
            phase2_dataset_handoff_sha256,
            label="Phase-4 Phase-2 dataset handoff",
        ),
        "feature_store_handoff_sha256": _sha256(
            feature_store_handoff_sha256,
            label="Phase-4 feature-store handoff",
        ),
        "feature_coverage_handoff_sha256": _sha256(
            feature_coverage_handoff_sha256,
            label="Phase-4 coverage handoff",
        ),
        "feature_entry_handoff_sha256": _sha256(
            feature_entry_handoff_sha256,
            label="Phase-4 feature-entry handoff",
        ),
        "discovery_subjects": int(summary["discovery_subjects"]),
        "comeback_5x_tokens": int(summary["comeback_5x_tokens"]),
        "comeback_5x_base_rate": str(summary["comeback_5x_base_rate"]),
        "continuous_max_post_dump_multiple_retained": True,
        "exact_confirmation_cutoff_alignment": True,
        "matched_feature_coverage_equal": True,
        "universe_context_retained": True,
        "labels_joined_after_feature_freeze": True,
        "feature_values_mutated": False,
        "phase4_discovery_only": True,
        "phase4_discovery_entry_ready": True,
        "phase4_discovery_checkpoint_claimed": False,
    }
