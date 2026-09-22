"""Validation policy for applying Phase-2 coverage-ledger proposals."""

from __future__ import annotations

from typing import Iterable, Mapping

from hlp.data.phase2_coverage import validate_phase2_coverage_ledger


PHASE2_COVERAGE_PROMOTION_VERSION = "phase2-source-coverage-promotion-v1"


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower().removeprefix("sha256:")
    if len(text) != 64:
        raise ValueError(f"{label} must be 64 hex chars")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} is not hexadecimal") from exc
    return text


def validate_phase2_coverage_ledger_commit(
    current_ledger: Mapping[str, object],
    proposed_ledger: Mapping[str, object],
    promotion_handoff: Mapping[str, object],
    promotion_validation: Mapping[str, object],
    source_inventory: Iterable[Mapping[str, object]],
    *,
    expected_source_id: str,
    current_ledger_sha256: str,
    proposed_ledger_sha256: str,
) -> dict:
    """Validate one exact stale-safe canonical coverage-ledger advance."""

    handoff = dict(promotion_handoff)
    if str(handoff.get("version") or "") != (
        PHASE2_COVERAGE_PROMOTION_VERSION
    ):
        raise ValueError("promotion handoff version changed")
    source_id = str(expected_source_id)
    if handoff.get("source_id") != source_id:
        raise ValueError("promotion source identity drift")
    if handoff.get("proposal_only") is not True:
        raise ValueError("promotion is not proposal-only")
    if handoff.get("canonical_ledger_mutated") is not False:
        raise ValueError(
            "promotion unexpectedly claims ledger mutation"
        )

    current_sha = _sha256(
        current_ledger_sha256,
        label="current canonical ledger SHA",
    )
    proposed_sha = _sha256(
        proposed_ledger_sha256,
        label="proposed ledger SHA",
    )
    if current_sha != _sha256(
        handoff.get("base_ledger_sha256"),
        label="promotion base_ledger_sha256",
    ):
        raise ValueError(
            "current canonical ledger SHA drift; promotion is stale"
        )
    if proposed_sha != _sha256(
        handoff.get("proposed_ledger_sha256"),
        label="promotion proposed_ledger_sha256",
    ):
        raise ValueError(
            "proposed ledger/handoff SHA linkage drift"
        )

    inventory = [dict(row) for row in source_inventory]
    before = validate_phase2_coverage_ledger(
        dict(current_ledger),
        inventory,
    )
    after = validate_phase2_coverage_ledger(
        dict(proposed_ledger),
        inventory,
    )
    before_ids = set(before["complete_source_ids"])
    after_ids = set(after["complete_source_ids"])
    if not before_ids.issubset(after_ids):
        raise ValueError("proposed ledger regresses complete sources")

    newly_complete = sorted(after_ids - before_ids)
    if newly_complete != [source_id]:
        raise ValueError(
            "proposed ledger must complete exactly the expected "
            f"source; got {newly_complete}"
        )

    handoff_before = sorted(
        str(value)
        for value in handoff.get("complete_source_ids_before") or []
    )
    handoff_after = sorted(
        str(value)
        for value in handoff.get("complete_source_ids_after") or []
    )
    if handoff_before != sorted(before_ids):
        raise ValueError("promotion handoff before-set drift")
    if handoff_after != sorted(after_ids):
        raise ValueError("promotion handoff after-set drift")

    validation_ids = sorted(
        str(value)
        for value in promotion_validation.get(
            "complete_source_ids"
        ) or []
    )
    if validation_ids != sorted(after_ids):
        raise ValueError(
            "promotion validation/ledger complete-set drift"
        )
    if promotion_validation.get(
        "phase2_universe_coverage_complete"
    ) != after["phase2_universe_coverage_complete"]:
        raise ValueError(
            "promotion validation completeness drift"
        )
    if handoff.get(
        "phase2_universe_coverage_complete"
    ) != after["phase2_universe_coverage_complete"]:
        raise ValueError(
            "promotion handoff completeness drift"
        )

    return {
        "source_id": source_id,
        "base_ledger_sha256": current_sha,
        "proposed_ledger_sha256": proposed_sha,
        "complete_source_ids_before": sorted(before_ids),
        "complete_source_ids_after": sorted(after_ids),
        "phase2_universe_coverage_complete": bool(
            after["phase2_universe_coverage_complete"]
        ),
        "newly_complete_source_ids": newly_complete,
        "canonical_ledger_mutation_allowed": True,
    }
