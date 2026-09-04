"""Point-in-time causality checks for Pons Stock Token USD feeds."""

from __future__ import annotations

from typing import Iterable

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
        if source["pricing_status"] != "priced_chainlink_stock_token":
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
