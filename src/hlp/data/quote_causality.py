"""Point-in-time causality checks for Pons Stock Token USD feeds."""

from __future__ import annotations

from typing import Iterable

from hlp.data.quote_registry import CHAINLINK_PRICED_STATUSES
from hlp.data.rpc import RpcClient
from hlp.protocols.chainlink import (
    read_chainlink_aggregator,
    read_chainlink_latest_round,
)


def audit_pons_quote_causality(
    rpc: RpcClient,
    quote_rows: Iterable[dict],
) -> list[dict]:
    """Prove each Chainlink quote had valid observable state before first use."""
    output = []
    for source in quote_rows:
        if source["pricing_status"] not in CHAINLINK_PRICED_STATUSES:
            continue
        row = dict(source)
        first_use = int(row["first_launch_block"])
        if first_use <= 0:
            raise ValueError("first Pons quote use must be after block zero")
        prior = first_use - 1
        feed = row["feed"].lower()
        symbol = row["symbol"].upper()
        accepted = {
            f"RH{symbol} / USD",
            f"Robinhood {symbol} / USD",
        }
        if row.get("directory_name"):
            accepted.add(str(row["directory_name"]))

        result = {
            "quote_token": row["quote_token"].lower(),
            "symbol": symbol,
            "feed": feed,
            "first_launch_block": first_use,
            "causal_state_block": prior,
            "proxy_has_code": False,
            "aggregator": None,
            "aggregator_has_code": False,
            "description": None,
            "round_id": None,
            "updated_at": None,
            "usd_price": None,
            "causal_ready": False,
            "error": None,
        }
        try:
            proxy_code = rpc.get_code(feed, prior)
            result["proxy_has_code"] = proxy_code not in {"0x", "0x0", ""}
            if not result["proxy_has_code"]:
                raise RuntimeError("Chainlink proxy has no code before first Pons use")

            aggregator = read_chainlink_aggregator(rpc, feed, block=prior)
            result["aggregator"] = aggregator
            aggregator_code = rpc.get_code(aggregator, prior)
            result["aggregator_has_code"] = aggregator_code not in {
                "0x",
                "0x0",
                "",
            }
            if not result["aggregator_has_code"]:
                raise RuntimeError(
                    "Chainlink aggregator has no code before first Pons use"
                )

            latest = read_chainlink_latest_round(rpc, feed, block=prior)
            result["description"] = latest.description
            if latest.description not in accepted:
                raise ValueError(
                    f"Chainlink description mismatch: {latest.description!r}"
                )
            result["round_id"] = latest.round_id
            result["updated_at"] = latest.updated_at
            result["usd_price"] = str(latest.answer)
            result["causal_ready"] = True
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
        output.append(result)

    output.sort(key=lambda row: (row["first_launch_block"], row["quote_token"]))
    return output


def supersede_delayed_v3_quote_ownership(
    *,
    v3_routes: Iterable[dict],
    v3_initial: Iterable[dict],
    v3_updates: Iterable[dict],
    v4_routes: Iterable[dict],
    token: str,
) -> dict:
    """Drop one delayed V3 owner only after a causal V4 replacement exists.

    This is deliberately narrow.  It never resolves arbitrary venue overlap and
    it refuses to discard any pre-existing causal V3 state.  The helper exists
    for the Phase-1 SKHY handoff where a delayed V3/WETH route is superseded by
    a direct USDG V4 pool with proven state before first Pons use.
    """
    target = str(token).lower()
    v3_route_rows = [dict(row) for row in v3_routes]
    v3_initial_rows = [dict(row) for row in v3_initial]
    v3_update_rows = [dict(row) for row in v3_updates]
    v4_route_rows = [dict(row) for row in v4_routes]

    def token_of(row: dict) -> str:
        return str(row["quote_token"]).lower()

    v3_tokens = {token_of(row) for row in v3_route_rows}
    v4_tokens = {token_of(row) for row in v4_route_rows}
    overlap = v3_tokens & v4_tokens
    unexpected = overlap - {target}
    if unexpected:
        raise ValueError(
            "unexpected V3/V4 quote ownership overlap: "
            + ", ".join(sorted(unexpected))
        )
    if target not in overlap:
        return {
            "v3_routes": v3_route_rows,
            "v3_initial": v3_initial_rows,
            "v3_updates": v3_update_rows,
            "superseded_tokens": [],
        }

    target_v3 = [row for row in v3_route_rows if token_of(row) == target]
    target_v4 = [row for row in v4_route_rows if token_of(row) == target]
    if len(target_v3) != 1 or len(target_v4) != 1:
        raise ValueError(
            "SKHY ownership supersession requires exactly one V3 and one V4 route"
        )

    v3_route = target_v3[0]
    if not str(v3_route.get("route_type", "")).endswith("_delayed"):
        raise ValueError("refusing to supersede non-delayed V3 quote ownership")
    if any(token_of(row) == target for row in v3_initial_rows):
        raise ValueError("refusing to discard causal V3 state during supersession")

    v4_route = target_v4[0]
    if (
        v4_route.get("causal_state_block") is None
        or str(v4_route.get("route_type", "")).endswith("_delayed")
    ):
        raise ValueError("delayed V3 ownership requires a causal V4 replacement")

    return {
        "v3_routes": [
            row for row in v3_route_rows if token_of(row) != target
        ],
        "v3_initial": v3_initial_rows,
        "v3_updates": [
            row for row in v3_update_rows if token_of(row) != target
        ],
        "superseded_tokens": [target],
    }
