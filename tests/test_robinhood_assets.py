import json

from hlp.data.robinhood_assets import RobinhoodAssetsClient


AAPL = "0x" + "11" * 20
OTHER = "0x" + "22" * 20


def transport(request, timeout):
    payload = {
        "assets": [
            {
                "id": "0xabc",
                "tokenSymbol": "AAPL",
                "tokenName": "Apple • Robinhood Token",
                "deployments": [
                    {"contractAddress": AAPL, "chainId": 4663},
                    {"contractAddress": OTHER, "chainId": 46630},
                ],
                "currentMultiplier": "1.0",
                "pendingMultiplier": "",
                "status": "ASSET_STATUS_ACTIVE",
                "tokenDecimals": 18,
            }
        ]
    }
    return json.dumps(payload).encode()


def test_canonical_chain_assets_filters_to_4663():
    client = RobinhoodAssetsClient(transport=transport)
    rows = client.canonical_chain_assets()
    assert rows == [
        {
            "asset_id": "0xabc",
            "token_symbol": "AAPL",
            "token_name": "Apple • Robinhood Token",
            "contract_address": AAPL,
            "chain_id": 4663,
            "token_decimals": 18,
            "status": "ASSET_STATUS_ACTIVE",
            "current_multiplier": "1.0",
            "pending_multiplier": "",
        }
    ]
    assert client.requests_made == 1


def test_address_map_is_canonical_address_keyed():
    client = RobinhoodAssetsClient(transport=transport)
    mapping = client.address_map()
    assert mapping[AAPL]["token_symbol"] == "AAPL"
