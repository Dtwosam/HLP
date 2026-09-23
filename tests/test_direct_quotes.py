import html

import pytest

from hlp.config import ROBINHOOD_USDG, ROBINHOOD_WETH
from hlp.data.direct_quotes import (
    ZERO_ADDRESS,
    build_direct_quote_registry,
    direct_quote_decimals,
    direct_quote_feed_specs,
)
from hlp.data.quote_registry import PONS_CBBTC


STOCK = "0x" + "11" * 20
MISSING = "0x" + "12" * 20
STOCK_FEED = "0x" + "22" * 20
CBBTC_FEED = "0x" + "33" * 20


def directory_page():
    text = (
        '"heartbeat":[0,86400],'
        '"name":[0,"Robinhood NVDA / USD"],'
        '"path":[0,"robinhood-nvda-usd-shared-svr"],'
        f'"proxyAddress":[0,"{STOCK_FEED}"],'
        f'"secondaryProxyAddress":[0,"0x{"44" * 20}"],'
        '"blockchainName":[0,"Robinhood"],'
        '"heartbeat":[0,3600],'
        '"name":[0,"CBBTC / USD"],'
        '"path":[0,"cbbtc-usd-shared-svr"],'
        f'"proxyAddress":[0,"{CBBTC_FEED}"],'
        f'"secondaryProxyAddress":[0,"0x{"55" * 20}"],'
        '"blockchainName":[0,"Robinhood"],'
        '"heartbeat":[0,1],'
    )
    return html.unescape(text)


def assets():
    return [
        {
            "asset_id": "asset-nvda",
            "token_symbol": "NVDA",
            "token_name": "Nvidia",
            "contract_address": STOCK,
            "chain_id": 4663,
            "token_decimals": 18,
            "status": "ASSET_STATUS_ACTIVE",
        },
        {
            "asset_id": "asset-miss",
            "token_symbol": "MISS",
            "token_name": "Missing Feed",
            "contract_address": MISSING,
            "chain_id": 4663,
            "token_decimals": 8,
            "status": "ASSET_STATUS_ACTIVE",
        },
    ]


def test_direct_quote_registry_preserves_priceable_and_missing_assets():
    rows = build_direct_quote_registry(
        assets(),
        chainlink_directory_page=directory_page(),
    )
    by_token = {row["quote_token"]: row for row in rows}

    assert by_token[ZERO_ADDRESS]["pricing_status"] == "priced_weth_usdg"
    assert by_token[ROBINHOOD_WETH.lower()]["quote_decimals"] == 18
    assert by_token[ROBINHOOD_USDG.lower()]["quote_decimals"] == 6
    assert by_token[STOCK]["pricing_status"] == (
        "priced_chainlink_stock_token"
    )
    assert by_token[STOCK]["feed"] == STOCK_FEED
    assert by_token[MISSING]["pricing_status"] == "missing_chainlink_feed"
    assert by_token[PONS_CBBTC]["pricing_status"] == (
        "priced_chainlink_crypto_token"
    )
    assert by_token[PONS_CBBTC]["feed"] == CBBTC_FEED


def test_direct_quote_decimals_excludes_missing_feed_assets():
    rows = build_direct_quote_registry(
        assets(),
        chainlink_directory_page=directory_page(),
    )
    allowlist = direct_quote_decimals(rows)

    assert allowlist[ZERO_ADDRESS] == 18
    assert allowlist[ROBINHOOD_WETH.lower()] == 18
    assert allowlist[ROBINHOOD_USDG.lower()] == 6
    assert allowlist[STOCK] == 18
    assert allowlist[PONS_CBBTC] == 8
    assert MISSING not in allowlist


def test_direct_quote_feed_specs_are_chainlink_only():
    rows = build_direct_quote_registry(
        assets(),
        chainlink_directory_page=directory_page(),
    )
    specs = direct_quote_feed_specs(rows)

    assert [row["quote_token"] for row in specs] == sorted([
        STOCK,
        PONS_CBBTC,
    ])
    assert all(row["feed"] for row in specs)


def test_direct_quote_registry_rejects_wrong_chain_asset():
    bad = assets()
    bad[0] = {**bad[0], "chain_id": 1}
    with pytest.raises(ValueError, match="wrong chain"):
        build_direct_quote_registry(
            bad,
            chainlink_directory_page=directory_page(),
        )
