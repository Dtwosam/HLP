"""Deterministic Flap curve-to-DEX lifecycle handoff."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.quote_usd import QuoteUsdTimeline


def _order(
    block: object,
    transaction_index: object,
    log_index: object,
) -> tuple[int, int, int]:
    return (
        int(block),
        -1 if transaction_index is None else int(transaction_index),
        int(log_index),
    )


def build_flap_graduation_market_handoffs(
    flap_registry: Iterable[Mapping[str, object]],
    market_registries: Iterable[Mapping[str, object]],
) -> list[dict]:
    """Join LaunchedToDEX pool addresses to exact address-based DEX markets.

    V4 PoolIds are deliberately not inferred from Flap's address-valued
    graduation event. Only an exact market registry row carrying the same
    concrete pool address can close a handoff.
    """
    by_pool: dict[str, dict] = {}
    for raw in market_registries:
        row = dict(raw)
        pool_raw = row.get("pool")
        if pool_raw is None:
            # PoolId-only markets are not address-identical evidence.
            continue
        pool = normalize_address(str(pool_raw))
        if pool in by_pool:
            raise ValueError(
                f"duplicate address-based market registry pool: {pool}"
            )
        if str(row.get("source_kind") or "") != "direct_dex":
            raise ValueError(
                f"Flap handoff market is not direct_dex: {pool}"
            )
        by_pool[pool] = row

    output = []
    seen_tokens: set[str] = set()
    for raw in flap_registry:
        row = dict(raw)
        graduation_block = row.get("graduation_block")
        if graduation_block is None:
            continue

        token = normalize_address(str(row["token"]))
        if token in seen_tokens:
            raise ValueError(
                f"duplicate graduated Flap registry token: {token}"
            )
        seen_tokens.add(token)

        pool_raw = row.get("graduation_pool")
        if pool_raw is None:
            raise ValueError(
                f"graduated Flap token has no pool: {token}"
            )
        pool = normalize_address(str(pool_raw))
        quote_raw = row.get("graduation_quote_token")
        if quote_raw is None:
            raise ValueError(
                f"graduated Flap token has no frozen quote: {token}"
            )
        quote = normalize_address(str(quote_raw))
        graduation_order = _order(
            graduation_block,
            row.get("graduation_transaction_index"),
            row.get("graduation_log_index"),
        )

        base = {
            "source_id": "flap",
            "token": token,
            "graduation_pool": pool,
            "graduation_quote_token": quote,
            "graduation_dex_id": row.get("graduation_dex_id"),
            "graduation_lp_fee_profile": row.get(
                "graduation_lp_fee_profile"
            ),
            "graduation_block": int(graduation_block),
            "graduation_transaction_hash": str(
                row.get("graduation_transaction_hash") or ""
            ).lower(),
            "graduation_transaction_index": row.get(
                "graduation_transaction_index"
            ),
            "graduation_log_index": int(
                row.get("graduation_log_index")
            ),
        }

        market = by_pool.get(pool)
        if market is None:
            output.append({
                **base,
                "market_match_status": "unmatched_address_market",
                "market_handoff_complete": False,
                "market_available_at_graduation": None,
                "market_source_id": None,
                "market_venue": None,
                "market_quote_token": None,
                "market_initialize_block": None,
                "market_initialize_transaction_index": None,
                "market_initialize_log_index": None,
                "market_initialize_order_relation": None,
            })
            continue

        market_token = normalize_address(str(market["token"]))
        if market_token != token:
            raise ValueError(
                "Flap graduation pool token mismatch: "
                f"{pool} {market_token} != {token}"
            )
        market_quote = normalize_address(str(market["quote_token"]))
        if market_quote != quote:
            raise ValueError(
                "Flap graduation pool quote mismatch: "
                f"{pool} {market_quote} != {quote}"
            )

        initialize_order = _order(
            market["initialize_block"],
            market.get("initialize_transaction_index"),
            market.get("initialize_log_index"),
        )
        if initialize_order < graduation_order:
            relation = "before_graduation"
        elif initialize_order == graduation_order:
            relation = "same_order"
        else:
            relation = "after_graduation"

        output.append({
            **base,
            "market_match_status": "matched_address_market",
            "market_handoff_complete": True,
            "market_available_at_graduation": (
                initialize_order <= graduation_order
            ),
            "market_source_id": str(market["source_id"]),
            "market_venue": str(market["venue"]),
            "market_quote_token": market_quote,
            "market_quote_decimals": int(market["quote_decimals"]),
            "market_initialize_block": int(
                market["initialize_block"]
            ),
            "market_initialize_transaction_index": market.get(
                "initialize_transaction_index"
            ),
            "market_initialize_log_index": int(
                market["initialize_log_index"]
            ),
            "market_initialize_order_relation": relation,
            "market_initial_sqrt_price_x96": int(
                market["initial_sqrt_price_x96"]
            ),
            "market_initial_tick": int(market["initial_tick"]),
        })

    output.sort(
        key=lambda row: (
            row["graduation_block"],
            row["token"],
            row["graduation_pool"],
        )
    )
    return output


def summarize_flap_graduation_market_handoffs(
    rows: Iterable[Mapping[str, object]],
) -> dict:
    data = [dict(row) for row in rows]
    matched = [
        row for row in data
        if row.get("market_handoff_complete") is True
    ]
    unmatched = [
        row for row in data
        if row.get("market_handoff_complete") is not True
    ]
    return {
        "graduated_tokens": len(data),
        "matched_address_markets": len(matched),
        "unmatched_address_markets": len(unmatched),
        "markets_available_at_graduation": sum(
            row.get("market_available_at_graduation") is True
            for row in matched
        ),
        "market_source_ids": sorted({
            str(row["market_source_id"])
            for row in matched
        }),
        "market_venues": sorted({
            str(row["market_venue"])
            for row in matched
        }),
        "all_graduations_resolved": not unmatched,
        "v4_pool_id_inference_used": False,
    }



def build_flap_v3_graduation_registry(
    flap_registry: Iterable[Mapping[str, object]],
    handoffs: Iterable[Mapping[str, object]],
) -> list[dict]:
    """Freeze exact address-based V3 markets for every Flap graduation."""
    flap_by_token = {
        normalize_address(str(row["token"])): dict(row)
        for row in flap_registry
        if row.get("graduation_block") is not None
    }
    handoff_by_token: dict[str, dict] = {}
    for raw in handoffs:
        row = dict(raw)
        token = normalize_address(str(row["token"]))
        if token in handoff_by_token:
            raise ValueError(f"duplicate Flap graduation handoff: {token}")
        handoff_by_token[token] = row

    if set(handoff_by_token) != set(flap_by_token):
        missing = sorted(set(flap_by_token) - set(handoff_by_token))
        extra = sorted(set(handoff_by_token) - set(flap_by_token))
        raise ValueError(
            "Flap graduation handoff population mismatch: "
            f"missing={missing[:10]} extra={extra[:10]}"
        )

    output = []
    seen_pools: set[str] = set()
    supported_sources = {
        "direct_uniswap_v3",
        "direct_sushiswap_v3",
    }
    for token in sorted(flap_by_token):
        launch = flap_by_token[token]
        handoff = handoff_by_token[token]
        if handoff.get("market_handoff_complete") is not True:
            raise ValueError(
                f"Flap graduation has no exact address market: {token}"
            )
        if handoff.get("market_available_at_graduation") is not True:
            raise ValueError(
                f"Flap V3 market was not available at graduation: {token}"
            )
        market_source = str(handoff.get("market_source_id") or "")
        if market_source not in supported_sources:
            raise ValueError(
                f"Flap graduation is not an address-based V3 market: {token}"
            )

        pool = normalize_address(str(handoff["graduation_pool"]))
        if pool in seen_pools:
            raise ValueError(f"duplicate Flap graduation pool: {pool}")
        seen_pools.add(pool)
        quote = normalize_address(
            str(handoff["graduation_quote_token"])
        )
        graduation_order = _order(
            handoff["graduation_block"],
            handoff.get("graduation_transaction_index"),
            handoff["graduation_log_index"],
        )
        initialize_order = _order(
            handoff["market_initialize_block"],
            handoff.get("market_initialize_transaction_index"),
            handoff["market_initialize_log_index"],
        )
        if initialize_order > graduation_order:
            raise ValueError(
                f"Flap V3 Initialize follows graduation: {token}"
            )

        supply_raw = int(launch["supply_raw"])
        token_decimals = int(launch["token_decimals"])
        if supply_raw <= 0 or token_decimals < 0:
            raise ValueError(
                f"Flap graduation has invalid supply metadata: {token}"
            )

        output.append({
            "source_id": "flap",
            "venue": "flap",
            "launch_kind": "curve_to_v3",
            "token": token,
            "pool": pool,
            "quote_token": quote,
            "quote_decimals": int(handoff["market_quote_decimals"]),
            "token_decimals": token_decimals,
            "supply_raw": supply_raw,
            "market_source_id": market_source,
            "market_venue": str(handoff["market_venue"]),
            "launch_block": int(launch["launch_block"]),
            "launch_transaction_hash": str(
                launch["launch_transaction_hash"]
            ).lower(),
            "launch_transaction_index": launch.get(
                "launch_transaction_index"
            ),
            "launch_log_index": int(launch["launch_log_index"]),
            "lifecycle_block": graduation_order[0],
            "lifecycle_transaction_hash": str(
                handoff["graduation_transaction_hash"]
            ).lower(),
            "lifecycle_transaction_index": (
                None
                if graduation_order[1] < 0
                else graduation_order[1]
            ),
            "lifecycle_log_index": graduation_order[2],
            "initialize_block": initialize_order[0],
            "initialize_transaction_index": (
                None if initialize_order[1] < 0 else initialize_order[1]
            ),
            "initialize_log_index": initialize_order[2],
            "initial_sqrt_price_x96": int(
                handoff["market_initial_sqrt_price_x96"]
            ),
            "initial_tick": int(handoff["market_initial_tick"]),
        })

    output.sort(
        key=lambda row: (
            row["lifecycle_block"],
            -1
            if row["lifecycle_transaction_index"] is None
            else row["lifecycle_transaction_index"],
            row["lifecycle_log_index"],
            row["token"],
        )
    )
    return output


def build_flap_graduation_snapshot_points(
    graduation_registry: Iterable[Mapping[str, object]],
    pool_quote_points: Iterable[Mapping[str, object]],
    weth_usd_anchor_points: Iterable[dict],
    *,
    initial_weth_usd: Decimal,
    initial_quote_usd: dict[str, Decimal] | None = None,
    quote_usd_updates: Iterable[dict] = (),
) -> list[dict]:
    """Price each Flap graduation at its exact causal V3 pool state."""
    registry = [dict(row) for row in graduation_registry]
    quote_points: dict[tuple[str, tuple[int, int, int]], dict] = {}
    for raw in pool_quote_points:
        row = dict(raw)
        pool = normalize_address(str(row["pool"]))
        order = _order(
            row["block_number"],
            row.get("transaction_index"),
            row["log_index"],
        )
        key = (pool, order)
        if key in quote_points:
            raise ValueError(
                f"duplicate Flap graduation price point: {pool} {order}"
            )
        quote_points[key] = row

    timeline = QuoteUsdTimeline(
        initial_weth_usd=initial_weth_usd,
        weth_anchor_points=weth_usd_anchor_points,
        initial_quote_usd=initial_quote_usd,
        oracle_updates=quote_usd_updates,
    )

    output = []
    for row in sorted(
        registry,
        key=lambda item: (
            int(item["lifecycle_block"]),
            -1
            if item.get("lifecycle_transaction_index") is None
            else int(item["lifecycle_transaction_index"]),
            int(item["lifecycle_log_index"]),
            str(item["token"]),
        ),
    ):
        order = _order(
            row["lifecycle_block"],
            row.get("lifecycle_transaction_index"),
            row["lifecycle_log_index"],
        )
        timeline.advance_to(order)
        pool = normalize_address(str(row["pool"]))
        price_row = quote_points.get((pool, order))
        if price_row is None:
            raise ValueError(
                f"missing causal Flap graduation pool price: {pool}"
            )
        if normalize_address(str(price_row["token"])) != normalize_address(
            str(row["token"])
        ):
            raise ValueError(
                f"Flap graduation price token mismatch: {pool}"
            )
        if normalize_address(
            str(price_row["quote_token"])
        ) != normalize_address(str(row["quote_token"])):
            raise ValueError(
                f"Flap graduation price quote mismatch: {pool}"
            )

        quote_per_token = Decimal(str(price_row["quote_per_token"]))
        if quote_per_token <= 0:
            raise ValueError(
                f"Flap graduation quote-per-token is non-positive: {pool}"
            )
        supply = Decimal(int(row["supply_raw"])) / (
            Decimal(10) ** int(row["token_decimals"])
        )
        market_cap_quote = quote_per_token * supply
        quote = normalize_address(str(row["quote_token"]))
        quote_usd = timeline.price(quote)
        pricing_status = timeline.pricing_status(quote)
        market_cap_usd = (
            None if quote_usd is None else market_cap_quote * quote_usd
        )
        output.append({
            "source_id": "flap",
            "venue": "flap",
            "phase": "v3",
            "event_type": "v3_graduation_snapshot",
            "token": normalize_address(str(row["token"])),
            "pool": pool,
            "market_id": pool,
            "market_source_id": row["market_source_id"],
            "market_venue": row["market_venue"],
            "quote_token": quote,
            "quote_decimals": int(row["quote_decimals"]),
            "supply_raw": int(row["supply_raw"]),
            "block_number": order[0],
            "transaction_hash": str(
                row["lifecycle_transaction_hash"]
            ).lower(),
            "transaction_index": (
                None if order[1] < 0 else order[1]
            ),
            "log_index": order[2],
            "quote_per_token": str(quote_per_token),
            "market_cap_quote": str(market_cap_quote),
            "pricing_status": pricing_status,
            "quote_usd": (
                None if quote_usd is None else str(quote_usd)
            ),
            "market_cap_proxy_usd": (
                None
                if market_cap_usd is None
                else str(market_cap_usd)
            ),
            "pool_price_source": str(
                price_row.get("pricing_source")
                or "sparse_v3_state_and_swaps"
            ),
        })
    return output


def merge_flap_lifecycle_market_cap_summaries(
    flap_registry: Iterable[Mapping[str, object]],
    curve_rows: Iterable[Mapping[str, object]],
    v3_rows: Iterable[Mapping[str, object]],
) -> list[dict]:
    """Merge curve and post-graduation summaries for every launched token."""
    merged: dict[str, dict] = {}
    for raw in flap_registry:
        row = dict(raw)
        token = normalize_address(str(row["token"]))
        if token in merged:
            raise ValueError(f"duplicate Flap registry token: {token}")
        merged[token] = {
            "token": token,
            "venue": "flap",
            "graduated": row.get("graduation_block") is not None,
            "curve_price_points": 0,
            "v3_price_points": 0,
            "price_points": 0,
            "priced_points": 0,
            "max_market_cap_proxy_usd": None,
            "max_market_cap_block": None,
            "crossed_100k": False,
        }

    for phase, rows in (("curve", curve_rows), ("v3", v3_rows)):
        for raw in rows:
            row = dict(raw)
            token = normalize_address(str(row["token"]))
            current = merged.get(token)
            if current is None:
                raise ValueError(
                    f"Flap {phase} summary has unknown token: {token}"
                )
            points = int(row["price_points"])
            priced = int(row["priced_points"])
            if points < 0 or priced < 0 or priced > points:
                raise ValueError(
                    f"Flap {phase} summary has invalid counts: {token}"
                )
            current[f"{phase}_price_points"] += points
            current["price_points"] += points
            current["priced_points"] += priced
            current["crossed_100k"] = (
                bool(current["crossed_100k"])
                or bool(row["crossed_100k"])
            )

            raw_max = row.get("max_market_cap_proxy_usd")
            if raw_max is None:
                continue
            value = Decimal(str(raw_max))
            block = int(row["max_market_cap_block"])
            prior = current["max_market_cap_proxy_usd"]
            prior_block = current["max_market_cap_block"]
            if (
                prior is None
                or value > Decimal(str(prior))
                or (
                    value == Decimal(str(prior))
                    and (
                        prior_block is None
                        or block < int(prior_block)
                    )
                )
            ):
                current["max_market_cap_proxy_usd"] = str(value)
                current["max_market_cap_block"] = block

    output = list(merged.values())
    output.sort(key=lambda row: row["token"])
    return output
