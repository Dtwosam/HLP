import html
import json

from hlp.config import ROBINHOOD_USDG, ROBINHOOD_WETH
from hlp.data.chainlink_directory import ChainlinkDirectoryClient
from hlp.data.quote_registry import PONS_CBBTC, build_pons_quote_registry
from hlp.data.robinhood_assets import RobinhoodAssetsClient


STOCK = "0x" + "11" * 20
UNKNOWN = "0x" + "99" * 20
FEED = "0x" + "22" * 20


def asset_transport(request, timeout):
    return json.dumps({
        "assets": [{
            "id": "asset-1",
            "tokenSymbol": "NVDA",
            "tokenName": "Nvidia",
            "deployments": [{"contractAddress": STOCK, "chainId": 4663}],
            "currentMultiplier": "1",
            "pendingMultiplier": "",
            "status": "ASSET_STATUS_ACTIVE",
            "tokenDecimals": 18,
        }]
    }).encode()


def directory_transport(request, timeout):
    text = (
        '"heartbeat":[0,86400],'
        '"name":[0,"Robinhood NVDA / USD"],'
        '"path":[0,"robinhood-nvda-usd-shared-svr"],'
        f'"proxyAddress":[0,"{FEED}"],'
        f'"secondaryProxyAddress":[0,"0x{"33" * 20}"],'
        '"docs":[0,{"blockchainName":[0,"Robinhood"]}],'
        '"heartbeat":[0,1],'
    )
    return html.escape(text).encode()


def test_quote_registry_classifies_special_stock_and_unknown():
    rows = [
        {"version": "v1", "pair_token": ROBINHOOD_WETH, "block_number": 10},
        {"version": "v2", "pair_token": ROBINHOOD_USDG, "block_number": 11, "quote_decimals": 6},
        {"version": "v1", "pair_token": STOCK, "block_number": 12},
        {"version": "v2", "pair_token": STOCK, "block_number": 13, "quote_decimals": 18},
        {"version": "v1", "pair_token": UNKNOWN, "block_number": 14},
    ]
    result = build_pons_quote_registry(
        rows,
        assets_client=RobinhoodAssetsClient(transport=asset_transport),
        directory_client=ChainlinkDirectoryClient(transport=directory_transport),
    )
    by_token = {row["quote_token"]: row for row in result}
    assert by_token[ROBINHOOD_WETH.lower()]["pricing_status"] == "priced_weth_usdg"
    assert by_token[ROBINHOOD_USDG.lower()]["pricing_status"] == "priced_usdg_nominal"
    assert by_token[STOCK]["pricing_status"] == "priced_chainlink_stock_token"
    assert by_token[STOCK]["first_launch_block"] == 12
    assert by_token[STOCK]["versions"] == {"v1": 1, "v2": 1}
    assert by_token[UNKNOWN]["pricing_status"] == "unsupported_quote"


def test_quote_registry_marks_missing_chainlink_feed():
    def empty_directory(request, timeout):
        return b"<html>no matching feed</html>"

    rows = build_pons_quote_registry(
        [{
            "version": "v2",
            "pair_token": STOCK,
            "quote_decimals": 18,
            "block_number": 12,
        }],
        assets_client=RobinhoodAssetsClient(transport=asset_transport),
        directory_client=ChainlinkDirectoryClient(transport=empty_directory),
    )
    assert rows[0]["pricing_status"] == "missing_chainlink_feed"
    assert rows[0]["symbol"] == "NVDA"
    assert rows[0]["feed"] is None



def test_quote_registry_classifies_verified_cbbtc_chainlink_quote():
    def no_stock_assets(request, timeout):
        return json.dumps({"assets": []}).encode()

    crypto_feed = "0x" + "44" * 20

    def crypto_directory(request, timeout):
        text = (
            '"heartbeat":[0,3600],'
            '"name":[0,"CBBTC / USD"],'
            '"path":[0,"cbbtc-usd-shared-svr"],'
            f'"proxyAddress":[0,"{crypto_feed}"],'
            f'"secondaryProxyAddress":[0,"0x{"55" * 20}"],'
            '"docs":[0,{"blockchainName":[0,"Robinhood"]}],'
            '"heartbeat":[0,1],'
        )
        return html.escape(text).encode()

    rows = build_pons_quote_registry(
        [{
            "version": "v2",
            "pair_token": PONS_CBBTC,
            "quote_decimals": 8,
            "block_number": 48_515_552,
        }],
        assets_client=RobinhoodAssetsClient(transport=no_stock_assets),
        directory_client=ChainlinkDirectoryClient(
            transport=crypto_directory
        ),
    )

    row = rows[0]
    assert row["pricing_status"] == "priced_chainlink_crypto_token"
    assert row["symbol"] == "CBBTC"
    assert row["quote_decimals"] == 8
    assert row["feed"] == crypto_feed
    assert row["directory_name"] == "CBBTC / USD"
