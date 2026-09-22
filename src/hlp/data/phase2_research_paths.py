"""Canonical Phase-2 research price-path bundle assembly.

The universe freeze proves which tokens are eligible. This module binds the
full canonical market-cap paths used by lifecycle research back to that frozen
universe without selecting a dump rule or computing comeback outcomes.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from heapq import merge
from pathlib import Path
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase2_universe import PHASE2_UNIVERSE_VERSION
from hlp.data.snapshot import write_jsonl_snapshot


PHASE2_RESEARCH_PRICE_PATH_VERSION = "phase2-research-price-path-v1"
DIRECT_RESEARCH_COMPONENT_ID = "direct_canonical"


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower().removeprefix("sha256:")
    if len(text) != 64:
        raise ValueError(f"{label} SHA-256 is invalid")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} SHA-256 is invalid") from exc
    return text


def _event_key(row: Mapping[str, object]) -> tuple[int, int, int]:
    block = int(row.get("block_number", -1))
    raw_transaction = row.get("transaction_index")
    transaction = -1 if raw_transaction is None else int(raw_transaction)
    log_index = int(row.get("log_index", -1))
    if block < 0 or transaction < -1 or log_index < 0:
        raise ValueError("research price path has invalid event position")
    return block, transaction, log_index


def _market_cap(value: object, *, label: str) -> Decimal:
    if value is None:
        raise ValueError(f"{label} is unpriced")
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{label} is not numeric") from exc
    if not result.is_finite() or result <= 0:
        raise ValueError(f"{label} must be positive and finite")
    return result


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")


def build_phase2_research_path_components(
    source_inventory: Iterable[Mapping[str, object]],
) -> dict[str, tuple[str, ...]]:
    """Collapse the three direct DEX populations into one selector-frozen tape."""

    components: dict[str, tuple[str, ...]] = {}
    direct = []
    seen: set[str] = set()
    for raw in source_inventory:
        row = dict(raw)
        source_id = str(row.get("source_id") or "")
        if not source_id or source_id in seen:
            raise ValueError("research price-path inventory source ids are invalid")
        seen.add(source_id)
        kind = str(row.get("source_kind") or "")
        if kind == "launchpad":
            components[source_id] = (source_id,)
        elif kind == "direct_dex":
            direct.append(source_id)
        else:
            raise ValueError(
                f"unsupported research price-path source kind: {kind!r}"
            )
    if not direct:
        raise ValueError("research price-path inventory lacks direct DEX sources")
    components[DIRECT_RESEARCH_COMPONENT_ID] = tuple(sorted(direct))
    return dict(sorted(components.items()))


def build_phase2_research_price_path(
    component_rows: Mapping[str, Iterable[Mapping[str, object]]],
    *,
    universe_rows: Iterable[Mapping[str, object]],
    universe_summary: Mapping[str, object],
    universe_sha256: str,
    source_inventory: Iterable[Mapping[str, object]],
    component_provenance_sha256: Mapping[str, object],
) -> tuple[list[dict], dict]:
    """Return one provenance-bound market-cap path for every frozen token."""

    summary = dict(universe_summary)
    if str(summary.get("version") or "") != PHASE2_UNIVERSE_VERSION:
        raise ValueError("research price path requires canonical universe version")
    if summary.get("phase2_universe_frozen") is not True:
        raise ValueError("research price path requires a frozen Phase-2 universe")
    if summary.get("coverage_complete") is not True:
        raise ValueError("research price path requires complete source coverage")
    snapshot = int(summary.get("snapshot_head_block", -1))
    if snapshot <= 0:
        raise ValueError("research price-path snapshot is invalid")
    universe_sha = _sha256(universe_sha256, label="Phase-2 universe")

    inventory = [dict(row) for row in source_inventory]
    components = build_phase2_research_path_components(inventory)
    inventory_ids = {str(row["source_id"]) for row in inventory}
    complete_ids = {str(value) for value in summary.get("complete_source_ids", [])}
    if complete_ids != inventory_ids:
        raise ValueError(
            "research price path requires the exact complete source inventory"
        )
    if int(summary.get("inventory_sources", -1)) != len(inventory_ids):
        raise ValueError("research price-path universe source count drift")

    supplied_components = {str(value) for value in component_rows}
    expected_components = set(components)
    if supplied_components != expected_components:
        raise ValueError(
            "research price-path component set mismatch: "
            f"missing={sorted(expected_components - supplied_components)} "
            f"extra={sorted(supplied_components - expected_components)}"
        )
    if {str(value) for value in component_provenance_sha256} != expected_components:
        raise ValueError("research price-path provenance component set mismatch")
    provenance = {
        component: _sha256(
            component_provenance_sha256[component],
            label=f"{component} research price path",
        )
        for component in sorted(expected_components)
    }

    source_to_component = {}
    for component, sources in components.items():
        for source_id in sources:
            if source_id in source_to_component:
                raise ValueError(
                    f"research price-path source mapped twice: {source_id}"
                )
            source_to_component[source_id] = component
    if set(source_to_component) != inventory_ids:
        raise ValueError("research price-path component mapping is incomplete")

    universe_by_token: dict[str, dict] = {}
    expected_token_components: dict[str, set[str]] = {}
    for raw in universe_rows:
        row = dict(raw)
        token = normalize_address(str(row.get("token") or ""))
        if token in universe_by_token:
            raise ValueError(f"research price-path universe repeats token: {token}")
        if row.get("universe_status") != "eligible":
            raise ValueError(
                f"research price-path universe contains non-eligible token: {token}"
            )
        source_ids = {str(value) for value in row.get("source_ids", [])}
        if not source_ids or not source_ids.issubset(inventory_ids):
            raise ValueError(
                f"research price-path universe source membership is invalid: {token}"
            )
        universe_by_token[token] = row
        expected_token_components[token] = {
            source_to_component[source_id] for source_id in source_ids
        }

    if len(universe_by_token) != int(summary.get("eligible_tokens", -1)):
        raise ValueError("research price-path universe token count drift")
    if not universe_by_token:
        raise ValueError("research price-path universe is empty")

    component_input_points: dict[str, int] = {}
    component_eligible_points: dict[str, int] = {}
    component_tokens: dict[str, set[str]] = {
        component: set() for component in expected_components
    }
    merged: dict[tuple[str, int, int, int], dict] = {}

    for component in sorted(expected_components):
        sources = set(components[component])
        input_count = 0
        eligible_count = 0
        seen_component_events: set[tuple[str, int, int, int]] = set()
        for raw in component_rows[component]:
            row = dict(raw)
            input_count += 1
            token = normalize_address(str(row.get("token") or ""))
            if token not in universe_by_token:
                continue
            if component not in expected_token_components[token]:
                raise ValueError(
                    f"research price-path unexpected component for {token}: "
                    f"{component}"
                )

            source_id = str(row.get("source_id") or "")
            if component == DIRECT_RESEARCH_COMPONENT_ID:
                if source_id not in sources:
                    raise ValueError(
                        f"direct canonical research row source drift: {source_id}"
                    )
                if row.get("canonical_price_series") is not True:
                    raise ValueError(
                        f"direct research price row is not selector-canonical: {token}"
                    )
            elif source_id and source_id != component:
                raise ValueError(
                    f"research price-path launchpad source drift: {component}"
                )
            if row.get("canonical_price_series") is False:
                raise ValueError(
                    f"research price-path row is explicitly non-canonical: {token}"
                )

            event = _event_key(row)
            if event[0] > snapshot:
                raise ValueError(
                    f"research price-path row is after frozen snapshot: {token}"
                )
            identity = (token, *event)
            if identity in seen_component_events:
                raise ValueError(
                    f"research price-path component repeats event: "
                    f"{component} {identity}"
                )
            seen_component_events.add(identity)
            market_cap = _market_cap(
                row.get("market_cap_proxy_usd"),
                label=f"{component} {token} market-cap proxy",
            )
            eligible_count += 1
            component_tokens[component].add(token)

            existing = merged.get(identity)
            if existing is None:
                merged[identity] = {
                    "version": PHASE2_RESEARCH_PRICE_PATH_VERSION,
                    "token": token,
                    "block_number": event[0],
                    "transaction_index": (
                        None if event[1] == -1 else event[1]
                    ),
                    "log_index": event[2],
                    "market_cap_proxy_usd": _decimal_text(market_cap),
                    "component_ids": [component],
                    "source_ids": [source_id] if source_id else [component],
                    "canonical_research_price_path": True,
                }
                continue

            if Decimal(existing["market_cap_proxy_usd"]) != market_cap:
                raise ValueError(
                    f"research price-path duplicate event disagrees: {identity}"
                )
            existing["component_ids"] = sorted(
                set(existing["component_ids"]) | {component}
            )
            if source_id:
                existing["source_ids"] = sorted(
                    set(existing["source_ids"]) | {source_id}
                )

        component_input_points[component] = input_count
        component_eligible_points[component] = eligible_count

    missing_memberships = []
    token_price_points = {}
    for token in sorted(universe_by_token):
        actual = {
            component
            for component, tokens in component_tokens.items()
            if token in tokens
        }
        expected = expected_token_components[token]
        if actual != expected:
            missing_memberships.append({
                "token": token,
                "expected": sorted(expected),
                "actual": sorted(actual),
            })
        token_price_points[token] = sum(
            identity[0] == token for identity in merged
        )
    if missing_memberships:
        raise ValueError(
            "research price-path frozen source membership coverage mismatch: "
            f"{missing_memberships}"
        )
    if any(points <= 0 for points in token_price_points.values()):
        raise ValueError("research price path leaves an eligible token unpriced")

    output = list(merged.values())
    output.sort(
        key=lambda row: (
            int(row["block_number"]),
            -1
            if row.get("transaction_index") is None
            else int(row["transaction_index"]),
            int(row["log_index"]),
            row["token"],
        )
    )
    payload = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
        for row in output
    ).encode("utf-8")
    path_sha = hashlib.sha256(payload).hexdigest()

    report = {
        "version": PHASE2_RESEARCH_PRICE_PATH_VERSION,
        "snapshot_head_block": snapshot,
        "universe_sha256": universe_sha,
        "coverage_source_ids": sorted(inventory_ids),
        "components": len(components),
        "component_coverage_sources": {
            component: list(sources)
            for component, sources in components.items()
        },
        "component_provenance_sha256": provenance,
        "component_input_points": dict(sorted(component_input_points.items())),
        "component_eligible_points": dict(
            sorted(component_eligible_points.items())
        ),
        "eligible_tokens": len(universe_by_token),
        "price_points": len(output),
        "token_price_points": dict(sorted(token_price_points.items())),
        "normalized_price_path_sha256": path_sha,
        "universe_source_membership_verified": True,
        "canonical_market_cap_proxy": True,
        "direct_dex_sources_collapsed_after_selector": True,
        "phase2_universe_frozen": True,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
    }
    return output, report



def materialize_phase2_research_price_path(
    component_rows: Mapping[str, Iterable[Mapping[str, object]]],
    *,
    universe_rows: Iterable[Mapping[str, object]],
    universe_summary: Mapping[str, object],
    universe_sha256: str,
    source_inventory: Iterable[Mapping[str, object]],
    component_provenance_sha256: Mapping[str, object],
    output: Path,
) -> tuple[dict, dict]:
    """Stream the full canonical research path without holding all points in memory."""

    summary = dict(universe_summary)
    if str(summary.get("version") or "") != PHASE2_UNIVERSE_VERSION:
        raise ValueError(
            "research price path requires canonical universe version"
        )
    if summary.get("phase2_universe_frozen") is not True:
        raise ValueError(
            "research price path requires a frozen Phase-2 universe"
        )
    if summary.get("coverage_complete") is not True:
        raise ValueError(
            "research price path requires complete source coverage"
        )
    snapshot = int(summary.get("snapshot_head_block", -1))
    if snapshot <= 0:
        raise ValueError("research price-path snapshot is invalid")
    universe_sha = _sha256(universe_sha256, label="Phase-2 universe")

    inventory = [dict(row) for row in source_inventory]
    components = build_phase2_research_path_components(inventory)
    inventory_ids = {str(row["source_id"]) for row in inventory}
    complete_ids = {
        str(value)
        for value in summary.get("complete_source_ids", [])
    }
    if complete_ids != inventory_ids:
        raise ValueError(
            "research price path requires the exact complete source inventory"
        )
    if int(summary.get("inventory_sources", -1)) != len(inventory_ids):
        raise ValueError(
            "research price-path universe source count drift"
        )

    expected_components = set(components)
    if {str(value) for value in component_rows} != expected_components:
        raise ValueError(
            "research price-path component set mismatch"
        )
    if {
        str(value)
        for value in component_provenance_sha256
    } != expected_components:
        raise ValueError(
            "research price-path provenance component set mismatch"
        )
    provenance = {
        component: _sha256(
            component_provenance_sha256[component],
            label=f"{component} research price path",
        )
        for component in sorted(expected_components)
    }

    source_to_component = {}
    for component, sources in components.items():
        for source_id in sources:
            if source_id in source_to_component:
                raise ValueError(
                    f"research price-path source mapped twice: {source_id}"
                )
            source_to_component[source_id] = component
    if set(source_to_component) != inventory_ids:
        raise ValueError(
            "research price-path component mapping is incomplete"
        )

    universe_by_token = {}
    expected_token_components = {}
    for raw in universe_rows:
        row = dict(raw)
        token = normalize_address(str(row.get("token") or ""))
        if token in universe_by_token:
            raise ValueError(
                f"research price-path universe repeats token: {token}"
            )
        if row.get("universe_status") != "eligible":
            raise ValueError(
                f"research price-path universe contains non-eligible token: "
                f"{token}"
            )
        source_ids = {
            str(value)
            for value in row.get("source_ids", [])
        }
        if not source_ids or not source_ids.issubset(inventory_ids):
            raise ValueError(
                f"research price-path universe source membership is invalid: "
                f"{token}"
            )
        universe_by_token[token] = row
        expected_token_components[token] = {
            source_to_component[source_id]
            for source_id in source_ids
        }
    if len(universe_by_token) != int(
        summary.get("eligible_tokens", -1)
    ):
        raise ValueError(
            "research price-path universe token count drift"
        )
    if not universe_by_token:
        raise ValueError("research price-path universe is empty")

    component_input_points = {
        component: 0 for component in expected_components
    }
    component_eligible_points = {
        component: 0 for component in expected_components
    }
    component_tokens = {
        component: set() for component in expected_components
    }
    token_price_points = {
        token: 0 for token in universe_by_token
    }

    def checked_component(component: str):
        sources = set(components[component])
        previous_sort_key = None
        for raw in component_rows[component]:
            row = dict(raw)
            component_input_points[component] += 1
            token = normalize_address(str(row.get("token") or ""))
            if token not in universe_by_token:
                continue
            if component not in expected_token_components[token]:
                raise ValueError(
                    f"research price-path unexpected component for {token}: "
                    f"{component}"
                )
            source_id = str(row.get("source_id") or "")
            if component == DIRECT_RESEARCH_COMPONENT_ID:
                if source_id not in sources:
                    raise ValueError(
                        "direct canonical research row source drift: "
                        f"{source_id}"
                    )
                if row.get("canonical_price_series") is not True:
                    raise ValueError(
                        "direct research price row is not selector-canonical: "
                        f"{token}"
                    )
            elif source_id and source_id != component:
                raise ValueError(
                    "research price-path launchpad source drift: "
                    f"{component}"
                )
            if row.get("canonical_price_series") is False:
                raise ValueError(
                    "research price-path row is explicitly non-canonical: "
                    f"{token}"
                )
            event = _event_key(row)
            if event[0] > snapshot:
                raise ValueError(
                    "research price-path row is after frozen snapshot: "
                    f"{token}"
                )
            sort_key = (*event, token)
            if (
                previous_sort_key is not None
                and sort_key < previous_sort_key
            ):
                raise ValueError(
                    f"research price-path component is not chronological: "
                    f"{component}"
                )
            if sort_key == previous_sort_key:
                raise ValueError(
                    f"research price-path component repeats event: "
                    f"{component} {sort_key}"
                )
            previous_sort_key = sort_key
            market_cap = _market_cap(
                row.get("market_cap_proxy_usd"),
                label=f"{component} {token} market-cap proxy",
            )
            component_eligible_points[component] += 1
            component_tokens[component].add(token)
            yield {
                "sort_key": sort_key,
                "token": token,
                "event": event,
                "component": component,
                "source_id": source_id,
                "market_cap": market_cap,
            }

    streams = [
        checked_component(component)
        for component in sorted(expected_components)
    ]

    def normalized_rows():
        current_key = None
        current = []

        def emit_group(group):
            if not group:
                return None
            first = group[0]
            market_cap = first["market_cap"]
            if any(
                row["market_cap"] != market_cap
                for row in group[1:]
            ):
                raise ValueError(
                    "research price-path duplicate event disagrees: "
                    f"{first['sort_key']}"
                )
            token = first["token"]
            token_price_points[token] += 1
            source_ids = {
                row["source_id"]
                for row in group
                if row["source_id"]
            }
            component_ids = {
                row["component"] for row in group
            }
            if not source_ids:
                source_ids = set(component_ids)
            event = first["event"]
            return {
                "version": PHASE2_RESEARCH_PRICE_PATH_VERSION,
                "token": token,
                "block_number": event[0],
                "transaction_index": (
                    None if event[1] == -1 else event[1]
                ),
                "log_index": event[2],
                "market_cap_proxy_usd": _decimal_text(market_cap),
                "component_ids": sorted(component_ids),
                "source_ids": sorted(source_ids),
                "canonical_research_price_path": True,
            }

        for item in merge(
            *streams,
            key=lambda row: row["sort_key"],
        ):
            key = item["sort_key"]
            if current_key is None:
                current_key = key
                current = [item]
                continue
            if key == current_key:
                current.append(item)
                continue
            row = emit_group(current)
            if row is not None:
                yield row
            current_key = key
            current = [item]

        row = emit_group(current)
        if row is not None:
            yield row

        missing_memberships = []
        for token in sorted(universe_by_token):
            actual = {
                component
                for component, tokens in component_tokens.items()
                if token in tokens
            }
            expected = expected_token_components[token]
            if actual != expected:
                missing_memberships.append({
                    "token": token,
                    "expected": sorted(expected),
                    "actual": sorted(actual),
                })
        if missing_memberships:
            raise ValueError(
                "research price-path frozen source membership coverage "
                f"mismatch: {missing_memberships[:20]}"
            )
        missing_price = sorted(
            token
            for token, count in token_price_points.items()
            if count <= 0
        )
        if missing_price:
            raise ValueError(
                "research price path leaves eligible token unpriced: "
                f"{missing_price[:20]}"
            )

    manifest = write_jsonl_snapshot(
        normalized_rows(),
        output=output,
        provenance={
            "version": PHASE2_RESEARCH_PRICE_PATH_VERSION,
            "snapshot_head_block": snapshot,
            "universe_sha256": universe_sha,
            "component_provenance_sha256": provenance,
            "canonical_market_cap_proxy": True,
            "direct_dex_sources_collapsed_after_selector": True,
            "dump_threshold_frozen": False,
            "phase2_dump_detector_frozen": False,
            "outcome_labels_computed": False,
        },
    )
    report = {
        "version": PHASE2_RESEARCH_PRICE_PATH_VERSION,
        "snapshot_head_block": snapshot,
        "universe_sha256": universe_sha,
        "coverage_source_ids": sorted(inventory_ids),
        "components": len(components),
        "component_coverage_sources": {
            component: list(sources)
            for component, sources in components.items()
        },
        "component_provenance_sha256": provenance,
        "component_input_points": dict(
            sorted(component_input_points.items())
        ),
        "component_eligible_points": dict(
            sorted(component_eligible_points.items())
        ),
        "eligible_tokens": len(universe_by_token),
        "price_points": int(manifest["records"]),
        "token_price_points": dict(sorted(token_price_points.items())),
        "normalized_price_path_sha256": manifest["sha256"],
        "universe_source_membership_verified": True,
        "canonical_market_cap_proxy": True,
        "direct_dex_sources_collapsed_after_selector": True,
        "phase2_universe_frozen": True,
        "streaming_materialization": True,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
    }
    return manifest, report
