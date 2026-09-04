import json

from hlp.data.hoodexplorer import HoodExplorerClient


class FakeHood(HoodExplorerClient):
    def _request(self, params):
        module = params["module"]
        action = params["action"]
        if module == "contract":
            return {
                "status": "1",
                "message": "OK",
                "result": [{
                    "contractAddress": "0x" + "11" * 20,
                    "contractCreator": "0x" + "22" * 20,
                    "txHash": "0x" + "33" * 32,
                }],
            }
        if module == "proxy" and action == "eth_getTransactionByHash":
            return {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "hash": "0x" + "33" * 32,
                    "blockNumber": hex(12345),
                },
            }
        if module == "logs":
            return {
                "status": "1",
                "message": "OK",
                "result": [{
                    "address": "0x" + "44" * 20,
                    "topics": ["0x" + "55" * 32],
                    "data": "0x",
                    "blockNumber": "12345",
                    "transactionHash": "0x" + "66" * 32,
                    "logIndex": "7",
                }],
            }
        raise AssertionError(params)


def test_contract_deployment_uses_archive_proxy():
    row = FakeHood().contract_deployment("0x" + "11" * 20)
    assert row["block_number"] == 12345
    assert row["creator"] == "0x" + "22" * 20


def test_logs_page_normalizes_indexed_log():
    rows = FakeHood().get_logs_page(topic0="0x" + "55" * 32)
    assert len(rows) == 1
    assert rows[0].block_number == 12345
    assert rows[0].log_index == 7
    assert rows[0].block_hash is None
