"""Classify every Pons quote asset and resolve official USD sources."""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from hlp.config import ROBINHOOD_USDG, ROBINHOOD_WETH
from hlp.data.chainlink_directory import ChainlinkDirectoryClient
from hlp.data.robinhood_assets import RobinhoodAssetsClient


ZERO_ADDRESS = "0x" + "00" * 20


def build_pons_quote_registry(
    registry_rows: Iterable[dict],
    *,
    assets_client: RobinhoodAssetsClient,
    directory_client: ChainlinkDirectoryClient,
) -> list[dict]:
    """Return one explicit pricing-source row per Pons pair token."""
    stats: dict[str, dict] = {}
    for launch in registry_rows:
        token = launch["pair_token"].lower()
        current = stats.get(token)
        block = int(launch["block_number"])
        version = str(launch["version"])
        raw_decimals = launch.get("quote_decimals")
        decimals = None if raw_decimals is None else int(raw_decimals)
        if current is None:
            current = {
                "quote_token": token,
                "launches": 0,
                "first_launch_block": block,
                "last_launch_block": block,
                "versions": Counter(),
                "observed_decimals": set(),
            }
            stats[token] = current
        current["launches"] += 1
        current["first_launch_block"] = min(current["first_launch_block"], block)
        current["last_launch_block"] = max(current["last_launch_block"], block)
        current["versions"][version] += 1
        if decimals is not None:
            current["observed_decimals"].add(decimals)

    for token, current in stats.items():
        if len(current["observed_decimals"]) > 1:
            raise ValueError(
                f"inconsistent Pons quote decimals for {token}: "
                f"{sorted(current['observed_decimals'])}"
            )

    assets = assets_client.address_map()
    stock_symbols = []
    asset_by_token = {}
    for token in stats:
        if token in {
            ZERO_ADDRESS,
            ROBINHOOD_WETH.lower(),
            ROBINHOOD_USDG.lower(),
        }:
            continue
        asset = assets.get(token)
        if asset is None:
            continue
        asset_by_token[token] = asset
        stock_symbols.append(asset["token_symbol"].upper())

    feeds = {
        row.symbol: row
        for row in directory_client.robinhood_feeds(sorted(set(stock_symbols)))
    } if stock_symbols else {}

    output = []
    for token in sorted(stats):
        current = stats[token]
        observed = sorted(current["observed_decimals"])
        base = {
            "quote_token": token,
            "launches": int(current["launches"]),
            "first_launch_block": int(current["first_launch_block"]),
            "last_launch_block": int(current["last_launch_block"]),
            "versions": dict(sorted(current["versions"].items())),
            "observed_quote_decimals": observed[0] if observed else None,
            "pricing_status": None,
            "symbol": None,
            "quote_decimals": None,
            "asset_id": None,
            "asset_status": None,
            "feed": None,
            "secondary_feed": None,
            "heartbeat_seconds": None,
            "directory_name": None,
            "directory_path": None,
        }

        if token == ZERO_ADDRESS:
            base.update({
                "pricing_status": "priced_weth_usdg",
                "symbol": "ETH",
                "quote_decimals": 18,
            })
        elif token == ROBINHOOD_WETH.lower():
            base.update({
                "pricing_status": "priced_weth_usdg",
                "symbol": "WETH",
                "quote_decimals": 18,
            })
        elif token == ROBINHOOD_USDG.lower():
            base.update({
                "pricing_status": "priced_usdg_nominal",
                "symbol": "USDG",
                "quote_decimals": 6,
            })
        else:
            asset = asset_by_token.get(token)
            if asset is None:
                base["pricing_status"] = "unsupported_quote"
            else:
                asset_decimals = int(asset["token_decimals"])
                if observed and observed[0] != asset_decimals:
                    raise ValueError(
                        f"quote decimals disagree for {asset['token_symbol']} "
                        f"{token}: Pons={observed[0]}, RHJ={asset_decimals}"
                    )
                symbol = asset["token_symbol"].upper()
                feed = feeds.get(symbol)
                base.update({
                    "symbol": symbol,
                    "quote_decimals": asset_decimals,
                    "asset_id": asset["asset_id"],
                    "asset_status": asset["status"],
                })
                if feed is None:
                    base["pricing_status"] = "missing_chainlink_feed"
                else:
                    base.update({
                        "pricing_status": "priced_chainlink_stock_token",
                        "feed": feed.proxy_address,
                        "secondary_feed": feed.secondary_proxy_address,
                        "heartbeat_seconds": feed.heartbeat_seconds,
                        "directory_name": feed.name,
                        "directory_path": feed.path,
                    })
        output.append(base)

    return output
