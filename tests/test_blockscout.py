import json

from hlp.data.blockscout import BlockscoutClient


class FakeBlockscout(BlockscoutClient):
    def _get(self, url):
        if "getcontractcreation" in url:
            return {
                "status": "1",
                "message": "OK",
                "result": [
                    {
                        "contractAddress": "0x" + "11" * 20,
                        "contractCreator": "0x" + "22" * 20,
                        "txHash": "0x" + "33" * 32,
                    }
                ],
            }
        return {
            "hash": "0x" + "33" * 32,
            "block": 12345,
            "timestamp": "2026-08-01T00:00:00.000000Z",
        }


def test_contract_deployment_joins_creation_and_transaction():
    client = FakeBlockscout()
    row = client.contract_deployment("0x" + "11" * 20)
    assert row["block_number"] == 12345
    assert row["creator"] == "0x" + "22" * 20
    assert row["transaction_hash"] == "0x" + "33" * 32
