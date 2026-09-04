import html
import json

from hlp.config import ROBINHOOD_USDG, ROBINHOOD_WETH
from hlp.data.chainlink_directory import ChainlinkDirectoryClient
from hlp.data.quote_registry import build_pons_quote_registry
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
