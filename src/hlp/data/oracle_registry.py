"""Resolve Pons Stock Token quote assets to official Chainlink feeds."""

from __future__ import annotations

from typing import Iterable

from hlp.config import ROBINHOOD_USDG, ROBINHOOD_WETH
from hlp.data.chainlink_directory import ChainlinkDirectoryClient
from hlp.data.robinhood_assets import RobinhoodAssetsClient


ZERO_ADDRESS = "0x" + "00" * 20


def resolve_stock_quote_feed_specs(
    registry_rows: Iterable[dict],
    *,
    assets_client: RobinhoodAssetsClient,
    directory_client: ChainlinkDirectoryClient,
) -> list[dict]:
    """Join Pons quote-token addresses to RHJ assets and Chainlink feeds."""
    expected_decimals: dict[str, int | None] = {}
    for row in registry_rows:
        token = row["pair_token"].lower()
        if token in {
            ZERO_ADDRESS,
            ROBINHOOD_WETH.lower(),
            ROBINHOOD_USDG.lower(),
        }:
            continue
        value = row.get("quote_decimals")
        decimals = None if value is None else int(value)
        if token in expected_decimals:
            prior = expected_decimals[token]
            if (
                prior is not None
                and decimals is not None
                and prior != decimals
            ):
                raise ValueError(
                    f"Pons registry has inconsistent quote decimals for {token}: "
                    f"{prior} vs {decimals}"
                )
            if prior is None and decimals is not None:
                expected_decimals[token] = decimals
        else:
            expected_decimals[token] = decimals

    if not expected_decimals:
        return []

    assets = assets_client.address_map()
    asset_rows = {}
    symbols = []
    for token, decimals in expected_decimals.items():
        asset = assets.get(token)
        if asset is None:
            raise KeyError(
                "Pons quote token is absent from official RHJ asset registry: "
                f"{token}"
            )
        asset_decimals = int(asset["token_decimals"])
        if decimals is not None and asset_decimals != decimals:
            raise ValueError(
                f"quote decimals disagree for {asset['token_symbol']} {token}: "
                f"Pons={decimals}, RHJ={asset_decimals}"
            )
        symbol = asset["token_symbol"].upper()
        asset_rows[symbol] = asset
        symbols.append(symbol)

    feed_rows = {
        row.symbol: row
        for row in directory_client.robinhood_feeds(symbols)
    }

    output = []
    for symbol in sorted(symbols):
        asset = asset_rows[symbol]
        feed = feed_rows.get(symbol)
        if feed is None:
            raise KeyError(f"no official Chainlink feed for RHJ asset {symbol}")
        output.append(
            {
                "quote_token": asset["contract_address"],
                "symbol": symbol,
                "quote_decimals": int(asset["token_decimals"]),
                "asset_id": asset["asset_id"],
                "asset_status": asset["status"],
                "directory_name": feed.name,
                "directory_path": feed.path,
                "feed": feed.proxy_address,
                "secondary_feed": feed.secondary_proxy_address,
                "heartbeat_seconds": feed.heartbeat_seconds,
            }
        )
    return output
