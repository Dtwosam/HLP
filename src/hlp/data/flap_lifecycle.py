"""Deterministic Flap curve-to-DEX lifecycle handoff."""

from __future__ import annotations

from typing import Iterable, Mapping

from hlp.config import normalize_address


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
