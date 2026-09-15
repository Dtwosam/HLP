"""Resolve Pons Stock Token quote assets to official Chainlink feeds."""

from __future__ import annotations

from typing import Iterable

from hlp.config import ROBINHOOD_USDG, ROBINHOOD_WETH
from hlp.data.chainlink_directory import ChainlinkDirectoryClient
from hlp.data.robinhood_assets import RobinhoodAssetsClient
from hlp.data.quote_registry import build_pons_quote_registry


ZERO_ADDRESS = "0x" + "00" * 20


def resolve_stock_quote_feed_specs(
    registry_rows: Iterable[dict],
    *,
    assets_client: RobinhoodAssetsClient,
    directory_client: ChainlinkDirectoryClient,
) -> list[dict]:
    """Join all canonical Pons Stock Token quotes to official Chainlink feeds."""
    quote_rows = build_pons_quote_registry(
        registry_rows,
        assets_client=assets_client,
        directory_client=directory_client,
    )
    blocking = [
        row
        for row in quote_rows
        if row["pricing_status"] in {
            "unsupported_quote",
            "missing_chainlink_feed",
        }
    ]
    if blocking:
        raise KeyError(
            "Pons quote registry contains assets without canonical USD pricing: "
            + ", ".join(
                f"{row['quote_token']}={row['pricing_status']}"
                for row in blocking
            )
        )

    output = []
    for row in quote_rows:
        if row["pricing_status"] != "priced_chainlink_stock_token":
            continue
        output.append(
            {
                "quote_token": row["quote_token"],
                "symbol": row["symbol"],
                "quote_decimals": int(row["quote_decimals"]),
                "asset_id": row["asset_id"],
                "asset_status": row["asset_status"],
                "directory_name": row["directory_name"],
                "directory_path": row["directory_path"],
                "feed": row["feed"],
                "secondary_feed": row["secondary_feed"],
                "heartbeat_seconds": row["heartbeat_seconds"],
            }
        )
    return output
