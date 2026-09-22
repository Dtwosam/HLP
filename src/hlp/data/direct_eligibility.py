"""Universe-ready eligibility handoff for conclusive direct launches."""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.direct_canonical import DIRECT_CANONICAL_SERIES_VERSION
from hlp.data.direct_selector import (
    DIRECT_SELECTOR_FREEZE_VERSION,
    DIRECT_SELECTOR_VERSION,
    DIRECT_SOURCE_IDS,
)
from hlp.data.phase2_universe import (
    normalize_phase2_source_eligibility_rows,
)


DIRECT_ELIGIBILITY_HANDOFF_VERSION = (
    "phase2-direct-eligibility-handoff-v1"
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


def build_direct_eligibility_handoff(
    canonical_summary_rows: Iterable[Mapping[str, object]],
    canonical_report: Mapping[str, object],
    source_token_memberships: Mapping[str, Iterable[str]],
    coverage_reports: Mapping[str, Mapping[str, object]],
    selector_freeze: Mapping[str, object],
    *,
    source_inventory: Iterable[Mapping[str, object]],
    provenance_sha256: str,
    selector_descriptor_sha256: str,
) -> tuple[dict[str, list[dict]], dict]:
    """Split one frozen cross-venue series across direct source populations.

    Source membership describes where a conclusive direct-launch market belongs.
    Price eligibility is always derived from the single frozen cross-venue
    canonical series, so non-selected competing pools never become alternate
    threshold histories.
    """
    provenance = _sha256(
        provenance_sha256,
        label="direct eligibility provenance",
    )
    selector_sha = _sha256(
        selector_descriptor_sha256,
        label="direct selector descriptor",
    )
    sources = set(DIRECT_SOURCE_IDS)

    inventory = {
        str(row["source_id"]): dict(row)
        for row in source_inventory
    }
    if set(source_token_memberships) != sources:
        raise ValueError(
            "direct eligibility source membership set changed"
        )
    if set(coverage_reports) != sources:
        raise ValueError(
            "direct eligibility coverage-report set changed"
        )

    if (
        str(selector_freeze.get("version") or "")
        != DIRECT_SELECTOR_FREEZE_VERSION
    ):
        raise ValueError("direct eligibility selector freeze version changed")
    if (
        str(selector_freeze.get("selector_version") or "")
        != DIRECT_SELECTOR_VERSION
    ):
        raise ValueError("direct eligibility selector version changed")
    if selector_freeze.get("selection_rule_frozen") is not True:
        raise ValueError("direct eligibility selector is not frozen")
    if selector_freeze.get("source_coverage_complete") is not False:
        raise ValueError(
            "direct eligibility selector unexpectedly closes coverage"
        )
    snapshot = int(selector_freeze.get("snapshot_head_block", -1))
    if snapshot <= 0:
        raise ValueError("direct eligibility selector snapshot is invalid")

    memberships: dict[str, set[str]] = {}
    for source_id in sorted(sources):
        spec = inventory.get(source_id)
        if spec is None or spec.get("source_kind") != "direct_dex":
            raise ValueError(
                f"direct eligibility inventory source changed: {source_id}"
            )
        membership = {
            normalize_address(str(token))
            for token in source_token_memberships[source_id]
        }
        memberships[source_id] = membership

        coverage = coverage_reports[source_id]
        if str(coverage.get("source_id") or "") != source_id:
            raise ValueError(
                f"direct eligibility coverage source drift: {source_id}"
            )
        if str(coverage.get("coverage_status") or "") != "complete":
            raise ValueError(
                f"direct eligibility requires complete coverage: {source_id}"
            )
        expected_readiness = str(spec.get("readiness") or "")
        if str(coverage.get("source_readiness") or "") != expected_readiness:
            raise ValueError(
                f"direct eligibility readiness drift: {source_id}"
            )
        if int(coverage.get("snapshot_head_block", -1)) != snapshot:
            raise ValueError(
                f"direct eligibility snapshot drift: {source_id}"
            )
        if int(coverage.get("last_block", -1)) != snapshot:
            raise ValueError(
                f"direct eligibility coverage does not reach snapshot: "
                f"{source_id}"
            )
        if coverage.get("continuous") is not True:
            raise ValueError(
                f"direct eligibility coverage is not continuous: {source_id}"
            )
        missing = coverage.get("missing_ranges")
        if not isinstance(missing, list) or missing:
            raise ValueError(
                f"direct eligibility coverage has missing ranges: {source_id}"
            )
        points = int(coverage.get("price_points", -1))
        priced = int(coverage.get("priced_points", -1))
        if points < 0 or priced != points:
            raise ValueError(
                f"direct eligibility coverage has unpriced points: {source_id}"
            )
        if int(coverage.get("tokens_discovered", -1)) != len(membership):
            raise ValueError(
                f"direct eligibility membership count drift: {source_id}"
            )
        if str(coverage.get("selector_version") or "") != (
            DIRECT_SELECTOR_VERSION
        ):
            raise ValueError(
                f"direct eligibility coverage selector drift: {source_id}"
            )
        if _sha256(
            coverage.get("selector_descriptor_sha256"),
            label=f"{source_id} selector descriptor",
        ) != selector_sha:
            raise ValueError(
                f"direct eligibility selector descriptor drift: {source_id}"
            )
        if coverage.get(
            "selector_rule_applied_to_coverage_points"
        ) is not False:
            raise ValueError(
                f"direct eligibility coverage pre-applied selector: {source_id}"
            )

    if (
        str(canonical_report.get("version") or "")
        != DIRECT_CANONICAL_SERIES_VERSION
    ):
        raise ValueError("direct eligibility canonical report version changed")
    if (
        str(canonical_report.get("canonical_selector_version") or "")
        != DIRECT_SELECTOR_VERSION
    ):
        raise ValueError(
            "direct eligibility canonical selector version changed"
        )
    if canonical_report.get("selection_rule_frozen") is not True:
        raise ValueError("direct eligibility canonical selector is not frozen")
    if canonical_report.get("canonical_price_series") is not True:
        raise ValueError("direct eligibility series is not canonical")
    if canonical_report.get(
        "cross_pool_volume_double_counting_allowed"
    ) is not False:
        raise ValueError(
            "direct eligibility canonical report permits volume double counting"
        )

    canonical_rows = [dict(row) for row in canonical_summary_rows]
    by_token: dict[str, dict] = {}
    canonical_points = 0
    for row in canonical_rows:
        token = normalize_address(str(row.get("token") or ""))
        if token in by_token:
            raise ValueError(
                f"direct eligibility repeats canonical token: {token}"
            )
        if row.get("canonical_price_series") is not True:
            raise ValueError(
                f"direct eligibility token row is not canonical: {token}"
            )
        points = int(row.get("price_points", -1))
        priced = int(row.get("priced_points", -1))
        unpriced = int(row.get("unpriced_points", 0))
        if (
            points <= 0
            or priced != points
            or unpriced != 0
            or row.get("pricing_complete") is not True
        ):
            raise ValueError(
                f"direct eligibility token pricing is incomplete: {token}"
            )
        canonical_points += points
        by_token[token] = row

    membership_counts: Counter[str] = Counter()
    for membership in memberships.values():
        membership_counts.update(membership)
    expected_tokens = set(membership_counts)
    actual_tokens = set(by_token)
    if actual_tokens != expected_tokens:
        raise ValueError(
            "direct eligibility canonical token population mismatch: "
            f"missing={sorted(expected_tokens - actual_tokens)} "
            f"extra={sorted(actual_tokens - expected_tokens)}"
        )
    if len(canonical_rows) != int(canonical_report.get("tokens", -1)):
        raise ValueError(
            "direct eligibility canonical token count disagrees with report"
        )
    if canonical_points != int(canonical_report.get("points", -1)):
        raise ValueError(
            "direct eligibility canonical point count disagrees with report"
        )

    groups: dict[str, list[dict]] = {}
    source_summaries = {}
    for source_id in sorted(sources):
        raw_rows = [
            by_token[token]
            for token in sorted(memberships[source_id])
        ]
        normalized = normalize_phase2_source_eligibility_rows(
            source_id,
            raw_rows,
            provenance_sha256=provenance,
            canonical_price_series=True,
        )
        if len(normalized) != int(
            coverage_reports[source_id].get("tokens_discovered", -1)
        ):
            raise ValueError(
                f"direct eligibility normalized token count drift: "
                f"{source_id}"
            )
        groups[source_id] = normalized
        source_summaries[source_id] = {
            "tokens": len(normalized),
            "canonical_price_points": sum(
                int(row["price_points"]) for row in normalized
            ),
            "eligible_tokens": sum(
                bool(row["crossed_100k"]) for row in normalized
            ),
        }

    summary = {
        "version": DIRECT_ELIGIBILITY_HANDOFF_VERSION,
        "snapshot_head_block": snapshot,
        "selector_version": DIRECT_SELECTOR_VERSION,
        "selector_descriptor_sha256": selector_sha,
        "eligibility_provenance_sha256": provenance,
        "canonical_tokens": len(canonical_rows),
        "canonical_price_points": canonical_points,
        "canonical_selected_markets": int(
            canonical_report.get("selected_markets", 0)
        ),
        "canonical_leadership_switches": int(
            canonical_report.get("leadership_switches", 0)
        ),
        "canonical_synthetic_selector_switches": int(
            canonical_report.get("synthetic_selector_switches", 0)
        ),
        "direct_population_overlap_tokens": sum(
            count > 1 for count in membership_counts.values()
        ),
        "source_summaries": source_summaries,
        "canonical_price_series": True,
        "selection_rule_frozen": True,
        "cross_pool_volume_double_counting_allowed": False,
        "source_coverage_complete": True,
        "phase2_universe_source_ready": True,
        "phase2_universe_frozen": False,
    }
    return groups, summary
