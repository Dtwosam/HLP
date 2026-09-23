"""Bind conclusive direct launches to the frozen selector contract."""

from __future__ import annotations

from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.direct_selector import (
    DIRECT_SELECTOR_FREEZE_VERSION,
    DIRECT_SELECTOR_VERSION,
)


DIRECT_LAUNCH_HANDOFF_VERSION = (
    "phase2-direct-launch-population-handoff-v2"
)
DIRECT_SOURCE_POPULATION_VERSION = (
    "phase2-direct-source-population-v1"
)
DIRECT_SOURCE_IDS = (
    "direct_uniswap_v3",
    "direct_sushiswap_v3",
    "direct_uniswap_v4",
)


def _market_identity(row: Mapping[str, object]) -> str:
    value = row.get("pool_id")
    if value is None:
        value = row.get("pool")
    market = str(value or "").lower()
    if not market:
        raise ValueError("direct source population row has no market identity")
    return market


def build_direct_source_populations(
    direct_launch_rows: Iterable[Mapping[str, object]],
    launch_handoff: Mapping[str, object],
    selector_freeze: Mapping[str, object],
) -> tuple[dict[str, list[dict]], dict]:
    """Group conclusive direct-launch markets by venue after selector freeze.

    This binds the two prerequisite decisions but deliberately does not claim
    historical source coverage and does not preselect one market per token.
    """
    if (
        str(launch_handoff.get("version") or "")
        != DIRECT_LAUNCH_HANDOFF_VERSION
    ):
        raise ValueError("direct launch population handoff version changed")
    if launch_handoff.get(
        "direct_launch_population_conclusive"
    ) is not True:
        raise ValueError("direct launch population is not conclusive")
    if launch_handoff.get("selector_freeze_ready") is not False:
        raise ValueError(
            "direct launch population unexpectedly freezes selector"
        )
    if launch_handoff.get("source_coverage_complete") is not False:
        raise ValueError(
            "direct launch population unexpectedly closes source coverage"
        )

    if (
        str(selector_freeze.get("version") or "")
        != DIRECT_SELECTOR_FREEZE_VERSION
    ):
        raise ValueError("direct selector freeze version changed")
    if (
        str(selector_freeze.get("selector_version") or "")
        != DIRECT_SELECTOR_VERSION
    ):
        raise ValueError("direct selector policy version changed")
    if selector_freeze.get("selection_rule_frozen") is not True:
        raise ValueError("direct selector is not frozen")
    if selector_freeze.get("source_coverage_complete") is not False:
        raise ValueError(
            "direct selector freeze unexpectedly closes source coverage"
        )

    launch_snapshot = int(
        launch_handoff.get("snapshot_head_block", -1)
    )
    selector_snapshot = int(
        selector_freeze.get("snapshot_head_block", -1)
    )
    if launch_snapshot <= 0 or selector_snapshot != launch_snapshot:
        raise ValueError(
            "direct source population snapshot mismatch"
        )

    direct_source_ids = tuple(
        str(value)
        for value in launch_handoff.get("direct_source_ids", [])
    )
    if set(direct_source_ids) != set(DIRECT_SOURCE_IDS):
        raise ValueError(
            "direct launch population source set changed"
        )

    groups = {source_id: [] for source_id in DIRECT_SOURCE_IDS}
    seen_markets: set[tuple[str, str]] = set()
    input_rows = [dict(row) for row in direct_launch_rows]
    tokens: set[str] = set()

    for raw in input_rows:
        source_id = str(raw.get("source_id") or "")
        if source_id not in groups:
            raise ValueError(
                f"direct source population has unexpected source: "
                f"{source_id!r}"
            )
        token = normalize_address(str(raw.get("token") or ""))
        if (
            raw.get("direct_launch_classification")
            != "conclusive_direct_launch"
        ):
            raise ValueError(
                f"direct source population launch classification changed: "
                f"{token}"
            )
        if raw.get("direct_launch_attribution_complete") is not True:
            raise ValueError(
                f"direct source population attribution incomplete: {token}"
            )
        if raw.get("source_coverage_complete") is not False:
            raise ValueError(
                f"direct source population row closes coverage: {token}"
            )

        market_id = _market_identity(raw)
        key = (source_id, market_id)
        if key in seen_markets:
            raise ValueError(
                "direct source population repeats market: "
                f"{source_id} {market_id}"
            )
        seen_markets.add(key)
        tokens.add(token)

        row = dict(raw)
        row["token"] = token
        row["canonical_selector_version"] = DIRECT_SELECTOR_VERSION
        row["canonical_selector_frozen"] = True
        row["canonical_market_selected"] = False
        row["source_coverage_complete"] = False
        groups[source_id].append(row)

    expected_markets = int(
        launch_handoff.get("direct_launch_candidate_markets", -1)
    )
    expected_tokens = int(
        launch_handoff.get("direct_launch_candidate_tokens", -1)
    )
    if len(input_rows) != expected_markets:
        raise ValueError(
            "direct source population market count disagrees with handoff"
        )
    if len(tokens) != expected_tokens:
        raise ValueError(
            "direct source population token count disagrees with handoff"
        )

    for source_id, rows in groups.items():
        rows.sort(
            key=lambda row: (
                int(row["initialize_block"]),
                row["token"],
                _market_identity(row),
            )
        )

    summary = {
        "version": DIRECT_SOURCE_POPULATION_VERSION,
        "snapshot_head_block": launch_snapshot,
        "selector_version": DIRECT_SELECTOR_VERSION,
        "selector_rule_frozen": True,
        "direct_launch_population_conclusive": True,
        "input_markets": len(input_rows),
        "input_tokens": len(tokens),
        "source_market_counts": {
            source_id: len(groups[source_id])
            for source_id in DIRECT_SOURCE_IDS
        },
        "source_token_counts": {
            source_id: len({
                row["token"] for row in groups[source_id]
            })
            for source_id in DIRECT_SOURCE_IDS
        },
        "canonical_market_selection_applied": False,
        "source_coverage_complete": False,
    }
    return groups, summary
