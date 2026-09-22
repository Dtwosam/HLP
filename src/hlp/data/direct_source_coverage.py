"""Market-level completion audit for direct DEX Phase-2 sources."""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.reconstruct import event_order


DIRECT_SOURCE_COVERAGE_VERSION = "phase2-direct-source-coverage-v1"
DIRECT_SOURCE_COVERAGE_CONFIG = {
    "direct_uniswap_v3": {
        "venue": "uniswap_v3",
        "version": "v3",
        "required_start_block": 8_930,
    },
    "direct_sushiswap_v3": {
        "venue": "sushiswap_v3",
        "version": "v3",
        "required_start_block": 6_292_626,
    },
    "direct_uniswap_v4": {
        "venue": "uniswap_v4",
        "version": "v4",
        "required_start_block": 9_070,
    },
}


def _market_id(row: Mapping[str, object]) -> str:
    raw = row.get("market_id")
    if raw is None:
        raw = row.get("pool_id")
    if raw is None:
        raw = row.get("pool")
    market = str(raw or "").lower()
    if not market:
        raise ValueError("direct source coverage row has no market identity")
    return market


def _initialize_order(row: Mapping[str, object]) -> tuple[int, int, int]:
    block = int(row.get("initialize_block", -1))
    raw_tx = row.get("initialize_transaction_index")
    tx = -1 if raw_tx is None else int(raw_tx)
    log = int(row.get("initialize_log_index", -1))
    if block < 0 or tx < -1 or log < 0:
        raise ValueError("direct source registry has invalid Initialize order")
    return block, tx, log


def audit_direct_source_market_points(
    registry_rows: Iterable[Mapping[str, object]],
    point_rows: Iterable[Mapping[str, object]],
    *,
    source_id: str,
    snapshot_head_block: int,
) -> dict:
    """Require complete, fully priced history for every registered direct market.

    Direct sources may contain several markets for the same token, so this audit
    is deliberately market-level. Canonical pool selection remains a separate
    downstream use of the already-frozen selector contract.
    """
    source_id = str(source_id)
    config = DIRECT_SOURCE_COVERAGE_CONFIG.get(source_id)
    if config is None:
        raise ValueError(f"unknown direct source coverage id: {source_id!r}")
    head = int(snapshot_head_block)
    if head <= 0:
        raise ValueError("direct source coverage snapshot is invalid")

    registry: dict[str, dict] = {}
    tokens: set[str] = set()
    for raw in registry_rows:
        row = dict(raw)
        if str(row.get("source_id") or "") != source_id:
            raise ValueError(
                "direct source coverage registry source identity drift"
            )
        if str(row.get("venue") or "") != config["venue"]:
            raise ValueError(
                "direct source coverage registry venue identity drift"
            )
        if row.get("direct_launch_classification") != (
            "conclusive_direct_launch"
        ):
            raise ValueError(
                "direct source coverage registry is not conclusive direct launch"
            )
        if row.get("direct_launch_attribution_complete") is not True:
            raise ValueError(
                "direct source coverage registry attribution is incomplete"
            )
        if row.get("canonical_selector_frozen") is not True:
            raise ValueError(
                "direct source coverage registry selector is not frozen"
            )
        if row.get("canonical_market_selected") is not False:
            raise ValueError(
                "direct source coverage registry preselects a market"
            )
        if row.get("source_coverage_complete") is not False:
            raise ValueError(
                "direct source coverage registry prematurely closes coverage"
            )

        market = _market_id(row)
        if market in registry:
            raise ValueError(
                f"direct source coverage repeats registry market: {market}"
            )
        token = normalize_address(str(row.get("token") or ""))
        initialize_order = _initialize_order(row)
        if initialize_order[0] > head:
            raise ValueError(
                f"direct source market initializes after snapshot: {market}"
            )
        registry[market] = {
            "token": token,
            "initialize_order": initialize_order,
        }
        tokens.add(token)

    counts: Counter[str] = Counter()
    initialize_counts: Counter[str] = Counter()
    point_tokens: set[str] = set()
    priced_points = 0
    quality_ready_points = 0
    points = 0
    previous_order = None

    expected_initialize_type = (
        "v3_initialize"
        if config["version"] == "v3"
        else "v4_initialize"
    )
    expected_swap_type = (
        "v3_swap"
        if config["version"] == "v3"
        else "v4_swap"
    )

    for raw in point_rows:
        row = dict(raw)
        points += 1
        if str(row.get("source_id") or "") != source_id:
            raise ValueError(
                "direct source coverage point source identity drift"
            )
        market = _market_id(row)
        registered = registry.get(market)
        if registered is None:
            raise ValueError(
                f"direct source coverage point has unknown market: {market}"
            )
        token = normalize_address(str(row.get("token") or ""))
        if token != registered["token"]:
            raise ValueError(
                f"direct source coverage point token drift: {market}"
            )

        order = event_order(row)
        if order < registered["initialize_order"]:
            raise ValueError(
                f"direct source coverage point predates Initialize: {market}"
            )
        ordered_key = (*order, market)
        if previous_order is not None and ordered_key < previous_order:
            raise ValueError(
                "direct source coverage points are not chronological"
            )
        previous_order = ordered_key

        kind = str(row.get("event_type") or "")
        if kind not in {expected_initialize_type, expected_swap_type}:
            raise ValueError(
                f"direct source coverage point event type changed: {kind!r}"
            )
        if kind == expected_initialize_type:
            if order != registered["initialize_order"]:
                raise ValueError(
                    f"direct source Initialize point order drift: {market}"
                )
            initialize_counts[market] += 1

        counts[market] += 1
        point_tokens.add(token)
        if row.get("market_cap_proxy_usd") is not None:
            priced_points += 1
        if (
            row.get("market_cap_proxy_usd") is not None
            and row.get("active_quote_liquidity_usd") is not None
        ):
            quality_ready_points += 1

    missing_markets = sorted(set(registry) - set(counts))
    missing_initialize = sorted(
        market
        for market in registry
        if initialize_counts[market] != 1
    )
    if missing_markets:
        raise ValueError(
            "direct source coverage has markets with no points: "
            + ", ".join(missing_markets[:10])
        )
    if missing_initialize:
        raise ValueError(
            "direct source coverage requires exactly one Initialize point "
            "per market: "
            + ", ".join(missing_initialize[:10])
        )
    if priced_points != points:
        raise ValueError(
            "direct source coverage contains unpriced market points"
        )
    if point_tokens != tokens:
        raise ValueError(
            "direct source coverage point token population drift"
        )

    return {
        "version": DIRECT_SOURCE_COVERAGE_VERSION,
        "source_id": source_id,
        "venue": config["venue"],
        "market_version": config["version"],
        "required_start_block": int(config["required_start_block"]),
        "snapshot_head_block": head,
        "registry_markets": len(registry),
        "registry_tokens": len(tokens),
        "markets_with_points": len(counts),
        "tokens_with_points": len(point_tokens),
        "initialize_points": sum(initialize_counts.values()),
        "swap_points": points - sum(initialize_counts.values()),
        "price_points": points,
        "priced_points": priced_points,
        "quality_ready_points": quality_ready_points,
        "all_registry_markets_priced": True,
        "selector_rule_applied_to_coverage_points": False,
        "source_coverage_complete": True,
    }


def build_direct_source_coverage_report(
    audit: Mapping[str, object],
    *,
    provenance_sha256: str,
) -> dict:
    """Convert a successful market audit into the canonical coverage row."""
    source_id = str(audit.get("source_id") or "")
    config = DIRECT_SOURCE_COVERAGE_CONFIG.get(source_id)
    if config is None:
        raise ValueError("direct source coverage audit has unknown source")
    if str(audit.get("version") or "") != DIRECT_SOURCE_COVERAGE_VERSION:
        raise ValueError("direct source coverage audit version changed")
    if audit.get("source_coverage_complete") is not True:
        raise ValueError("direct source coverage audit is incomplete")
    if audit.get("all_registry_markets_priced") is not True:
        raise ValueError("direct source coverage markets are not fully priced")
    if audit.get("selector_rule_applied_to_coverage_points") is not False:
        raise ValueError(
            "direct source coverage must retain all markets before selection"
        )

    provenance = str(provenance_sha256 or "").lower()
    if len(provenance) != 64:
        raise ValueError("direct source coverage provenance SHA-256 is invalid")
    try:
        int(provenance, 16)
    except ValueError as exc:
        raise ValueError(
            "direct source coverage provenance SHA-256 is invalid"
        ) from exc

    start = int(audit["required_start_block"])
    head = int(audit["snapshot_head_block"])
    return {
        "source_id": source_id,
        "source_readiness": "adapter_ready",
        "coverage_status": "complete",
        "required_start_block": start,
        "first_block": start,
        "last_block": head,
        "continuous": True,
        "missing_ranges": [],
        "tokens_discovered": int(audit["registry_tokens"]),
        "price_points": int(audit["price_points"]),
        "priced_points": int(audit["priced_points"]),
        "observed_volume_usd": None,
        "provenance_sha256": provenance,
        "blocking_reason": None,
        "snapshot_head_block": head,
        "markets_discovered": int(audit["registry_markets"]),
        "initialize_points": int(audit["initialize_points"]),
        "swap_points": int(audit["swap_points"]),
        "quality_ready_points": int(audit["quality_ready_points"]),
        "selector_rule_applied_to_coverage_points": False,
    }
