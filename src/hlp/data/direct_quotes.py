"""Canonical supported quote registry for Phase-2 direct DEX discovery.

Direct-market discovery must not treat arbitrary pair symbols as priceable.
This module freezes address-level quote identity, decimals, and USD pricing
provenance before a DEX pair can enter the direct-market candidate population.
"""

from __future__ import annotations

from typing import Iterable, Mapping

from hlp.config import (
    ROBINHOOD_CHAIN_ID,
    ROBINHOOD_USDG,
    ROBINHOOD_WETH,
    normalize_address,
)
from hlp.data.chainlink_directory import (
    ChainlinkDirectoryClient,
    ChainlinkDirectoryError,
)
from hlp.data.quote_registry import (
    PONS_CBBTC,
    PONS_CHAINLINK_CRYPTO_QUOTES,
)
from hlp.data.robinhood_assets import RobinhoodAssetsClient


ZERO_ADDRESS = "0x" + "00" * 20
DIRECT_QUOTE_REGISTRY_VERSION = "phase2-direct-quotes-v1"
DIRECT_PRICEABLE_STATUSES = frozenset({
    "priced_weth_usdg",
    "priced_usdg_nominal",
    "priced_chainlink_stock_token",
    "priced_chainlink_crypto_token",
})


def _feed_fields(feed) -> dict:
    return {
        "feed": feed.proxy_address,
        "secondary_feed": feed.secondary_proxy_address,
        "heartbeat_seconds": int(feed.heartbeat_seconds),
        "directory_name": feed.name,
        "directory_path": feed.path,
    }


def build_direct_quote_registry(
    robinhood_asset_rows: Iterable[Mapping[str, object]],
    *,
    chainlink_directory_page: str,
) -> list[dict]:
    """Build address-keyed direct-DEX quote pricing provenance.

    Canonical Robinhood Stock Token/ETF assets are retained even when their
    official Chainlink feed is absent. Such rows remain explicitly unpriceable
    and therefore cannot silently enter the direct-market quote allowlist.
    """
    page = str(chainlink_directory_page)
    if not page:
        raise ValueError("Chainlink directory page cannot be empty")

    rows = [
        {
            "quote_token": ZERO_ADDRESS,
            "symbol": "ETH",
            "quote_decimals": 18,
            "pricing_status": "priced_weth_usdg",
            "identity_source": "hlp.config",
            "asset_id": None,
            "asset_status": None,
            "feed": None,
            "secondary_feed": None,
            "heartbeat_seconds": None,
            "directory_name": None,
            "directory_path": None,
        },
        {
            "quote_token": normalize_address(ROBINHOOD_WETH),
            "symbol": "WETH",
            "quote_decimals": 18,
            "pricing_status": "priced_weth_usdg",
            "identity_source": "hlp.config",
            "asset_id": None,
            "asset_status": None,
            "feed": None,
            "secondary_feed": None,
            "heartbeat_seconds": None,
            "directory_name": None,
            "directory_path": None,
        },
        {
            "quote_token": normalize_address(ROBINHOOD_USDG),
            "symbol": "USDG",
            "quote_decimals": 6,
            "pricing_status": "priced_usdg_nominal",
            "identity_source": "hlp.config",
            "asset_id": None,
            "asset_status": None,
            "feed": None,
            "secondary_feed": None,
            "heartbeat_seconds": None,
            "directory_name": None,
            "directory_path": None,
        },
    ]

    for raw in robinhood_asset_rows:
        chain_id = int(raw.get("chain_id", -1))
        if chain_id != ROBINHOOD_CHAIN_ID:
            raise ValueError(
                f"direct quote asset has wrong chain: {chain_id}"
            )
        token = normalize_address(str(raw["contract_address"]))
        symbol = str(raw.get("token_symbol") or "").upper().strip()
        if not symbol:
            raise ValueError(f"direct quote asset has no symbol: {token}")
        decimals = int(raw.get("token_decimals", 18))
        if decimals < 0 or decimals > 255:
            raise ValueError(
                f"direct quote asset has invalid decimals: {token}"
            )
        row = {
            "quote_token": token,
            "symbol": symbol,
            "quote_decimals": decimals,
            "pricing_status": "missing_chainlink_feed",
            "identity_source": "robinhood_rhj_assets",
            "asset_id": str(raw.get("asset_id") or ""),
            "asset_status": str(raw.get("status") or ""),
            "feed": None,
            "secondary_feed": None,
            "heartbeat_seconds": None,
            "directory_name": None,
            "directory_path": None,
        }
        try:
            feed = ChainlinkDirectoryClient.parse_robinhood_feed(
                page,
                symbol,
            )
        except ChainlinkDirectoryError:
            pass
        else:
            row["pricing_status"] = "priced_chainlink_stock_token"
            row.update(_feed_fields(feed))
        rows.append(row)

    crypto = PONS_CHAINLINK_CRYPTO_QUOTES[PONS_CBBTC]
    crypto_row = {
        "quote_token": normalize_address(PONS_CBBTC),
        "symbol": str(crypto["symbol"]),
        "quote_decimals": int(crypto["quote_decimals"]),
        "pricing_status": "missing_chainlink_feed",
        "identity_source": "verified_phase1_crypto_quote",
        "asset_id": None,
        "asset_status": None,
        "feed": None,
        "secondary_feed": None,
        "heartbeat_seconds": None,
        "directory_name": None,
        "directory_path": None,
    }
    try:
        feed = ChainlinkDirectoryClient.parse_robinhood_crypto_usd_feed(
            page,
            crypto_row["symbol"],
        )
    except ChainlinkDirectoryError:
        pass
    else:
        crypto_row["pricing_status"] = "priced_chainlink_crypto_token"
        crypto_row.update(_feed_fields(feed))
    rows.append(crypto_row)

    by_address: dict[str, dict] = {}
    for row in rows:
        token = normalize_address(str(row["quote_token"]))
        if token in by_address:
            raise ValueError(
                f"duplicate direct quote asset address: {token}"
            )
        item = dict(row)
        item["quote_token"] = token
        by_address[token] = item

    return [by_address[token] for token in sorted(by_address)]


def direct_quote_decimals(
    registry_rows: Iterable[Mapping[str, object]],
) -> dict[str, int]:
    """Return the exact address->decimals allowlist for priceable quotes."""
    output: dict[str, int] = {}
    for raw in registry_rows:
        token = normalize_address(str(raw["quote_token"]))
        status = str(raw.get("pricing_status") or "")
        if status not in DIRECT_PRICEABLE_STATUSES:
            continue
        decimals = int(raw["quote_decimals"])
        if decimals < 0 or decimals > 255:
            raise ValueError(
                f"invalid direct quote decimals for {token}: {decimals}"
            )
        if token in output:
            raise ValueError(f"duplicate priceable direct quote: {token}")
        output[token] = decimals
    if not output:
        raise ValueError("direct quote allowlist is empty")
    return dict(sorted(output.items()))


def direct_quote_feed_specs(
    registry_rows: Iterable[Mapping[str, object]],
) -> list[dict]:
    """Return only Chainlink-priced quote rows for historical USD acquisition."""
    output = []
    seen: set[str] = set()
    for raw in registry_rows:
        status = str(raw.get("pricing_status") or "")
        if status not in {
            "priced_chainlink_stock_token",
            "priced_chainlink_crypto_token",
        }:
            continue
        token = normalize_address(str(raw["quote_token"]))
        if token in seen:
            raise ValueError(f"duplicate direct quote feed spec: {token}")
        seen.add(token)
        feed = raw.get("feed")
        if not isinstance(feed, str) or not feed:
            raise ValueError(
                f"Chainlink-priced direct quote has no feed: {token}"
            )
        output.append({
            "quote_token": token,
            "symbol": str(raw["symbol"]),
            "quote_decimals": int(raw["quote_decimals"]),
            "pricing_status": status,
            "feed": normalize_address(feed),
            "secondary_feed": (
                None
                if raw.get("secondary_feed") is None
                else normalize_address(str(raw["secondary_feed"]))
            ),
            "heartbeat_seconds": int(raw["heartbeat_seconds"]),
            "directory_name": str(raw["directory_name"]),
            "directory_path": str(raw["directory_path"]),
        })
    output.sort(key=lambda row: row["quote_token"])
    return output


def build_direct_quote_registry_from_clients(
    assets_client: RobinhoodAssetsClient,
    directory_client: ChainlinkDirectoryClient,
) -> list[dict]:
    """Resolve official live identity sources, then build the pure registry."""
    assets = assets_client.canonical_chain_assets()
    page = directory_client.fetch_text()
    return build_direct_quote_registry(
        assets,
        chainlink_directory_page=page,
    )
