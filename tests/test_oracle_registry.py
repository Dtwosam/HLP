import html
import json

from hlp.data.chainlink_directory import ChainlinkDirectoryClient
from hlp.data.oracle_registry import resolve_stock_quote_feed_specs
from hlp.data.robinhood_assets import RobinhoodAssetsClient


STOCK = "0x" + "11" * 20
FEED = "0x" + "22" * 20


def asset_transport(request, timeout):
    return json.dumps(
        {
            "assets": [
                {
                    "id": "asset-1",
                    "tokenSymbol": "NVDA",
                    "tokenName": "Nvidia",
                    "deployments": [
                        {"contractAddress": STOCK, "chainId": 4663}
                    ],
                    "currentMultiplier": "1",
                    "pendingMultiplier": "",
                    "status": "ASSET_STATUS_ACTIVE",
                    "tokenDecimals": 18,
                }
            ]
        }
    ).encode()


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


def test_resolve_stock_quote_feed_specs():
    rows = [
        {
            "pair_token": STOCK,
            "quote_decimals": 18,
        }
    ]
    result = resolve_stock_quote_feed_specs(
        rows,
        assets_client=RobinhoodAssetsClient(transport=asset_transport),
        directory_client=ChainlinkDirectoryClient(transport=directory_transport),
    )
    assert len(result) == 1
    assert result[0]["symbol"] == "NVDA"
    assert result[0]["quote_token"] == STOCK
    assert result[0]["feed"] == FEED
    assert result[0]["heartbeat_seconds"] == 86400
