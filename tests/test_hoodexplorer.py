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


def test_iter_logs_pages_until_short_page():
    calls = []

    class Paged(FakeHood):
        def get_logs_page(self, **kwargs):
            calls.append(kwargs["page"])
            if kwargs["page"] == 1:
                return ["a", "b"]
            if kwargs["page"] == 2:
                return ["c"]
            return []

    rows = list(Paged(api_key="test").iter_logs(topic0="0x" + "55" * 32, page_size=2))
    assert rows == ["a", "b", "c"]
    assert calls == [1, 2]


def test_iter_logs_respects_max_records():
    class Paged(FakeHood):
        def get_logs_page(self, **kwargs):
            return ["a", "b", "c"]

    rows = list(
        Paged(api_key="test").iter_logs(
            topic0="0x" + "55" * 32,
            page_size=3,
            max_records=2,
        )
    )
    assert rows == ["a", "b"]
