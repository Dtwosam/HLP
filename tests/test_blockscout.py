import json
import urllib.parse

import pytest

from hlp.data.blockscout import BlockscoutClient, BlockscoutError


ADDRESS = "0x" + "11" * 20
CREATOR = "0x" + "22" * 20
TX = "0x" + "33" * 32
TOPIC = "0x" + "44" * 32


def rpc_log(block: int, index: int = 0):
    return {
        "address": ADDRESS,
        "blockHash": "0x" + "aa" * 32,
        "blockNumber": hex(block),
        "data": "0x",
        "logIndex": hex(index),
        "topics": [TOPIC],
        "transactionHash": TX,
        "transactionIndex": "0x0",
    }


class FakeBlockscout(BlockscoutClient):
    def _get(self, url):
        if "getcontractcreation" in url:
            return {
                "status": "1",
                "message": "OK",
                "result": [
                    {
                        "contractAddress": ADDRESS,
                        "contractCreator": CREATOR,
                        "txHash": TX,
                    }
                ],
            }
        if "/api/v2/transactions/" in url:
            return {
                "hash": TX,
                "block": 12345,
                "timestamp": "2026-08-01T00:00:00.000000Z",
            }
        raise AssertionError(url)


def test_contract_deployment_joins_creation_and_transaction():
    client = FakeBlockscout()
    row = client.contract_deployment(ADDRESS)
    assert row["block_number"] == 12345
    assert row["creator"] == CREATOR
    assert row["transaction_hash"] == TX


def test_indexed_logs_build_address_and_topic_query():
    seen = []

    def transport(request, timeout):
        seen.append(request.full_url)
        payload = {
            "status": "1",
            "message": "OK",
            "result": [rpc_log(25, 2)],
        }
        return json.dumps(payload).encode()

    client = BlockscoutClient(transport=transport)
    rows = client.get_indexed_logs(20, 30, address=ADDRESS, topic0=TOPIC)
    assert len(rows) == 1
    assert rows[0].block_number == 25
    assert rows[0].log_index == 2

    query = urllib.parse.parse_qs(urllib.parse.urlsplit(seen[0]).query)
    assert query["module"] == ["logs"]
    assert query["action"] == ["getLogs"]
    assert query["address"] == [ADDRESS]
    assert query["topic0"] == [TOPIC]
    assert query["fromBlock"] == ["20"]
    assert query["toBlock"] == ["30"]


def test_no_logs_is_empty_not_failure():
    def transport(request, timeout):
        return json.dumps(
            {"status": "0", "message": "No logs found", "result": []}
        ).encode()

    client = BlockscoutClient(transport=transport)
    assert client.get_indexed_logs(1, 10, address=ADDRESS) == []


def test_bisect_splits_capped_ranges_and_preserves_order():
    calls = []

    class SplitClient(BlockscoutClient):
        def get_indexed_logs(self, start, end, **kwargs):
            calls.append((start, end))
            if (start, end) == (0, 9):
                return [self._raw_log(rpc_log(i % 10, i)) for i in range(4)]
            if (start, end) == (0, 4):
                return [self._raw_log(rpc_log(1, 0)), self._raw_log(rpc_log(3, 0))]
            if (start, end) == (5, 9):
                return [self._raw_log(rpc_log(6, 0)), self._raw_log(rpc_log(8, 0))]
            raise AssertionError((start, end))

    client = SplitClient()
    rows = list(
        client.iter_indexed_logs_bisect(
            0,
            9,
            address=ADDRESS,
            topic0=TOPIC,
            result_limit=4,
        )
    )
    assert calls == [(0, 9), (0, 4), (5, 9)]
    assert [r.block_number for r in rows] == [1, 3, 6, 8]


def test_bisect_fails_closed_if_single_block_hits_cap():
    class DenseClient(BlockscoutClient):
        def get_indexed_logs(self, start, end, **kwargs):
            return [self._raw_log(rpc_log(start, i)) for i in range(3)]

    with pytest.raises(BlockscoutError, match="single block"):
        list(
            DenseClient().iter_indexed_logs_bisect(
                7,
                7,
                address=ADDRESS,
                result_limit=3,
            )
        )


def test_max_records_stops_chronologically():
    class OrderedClient(BlockscoutClient):
        def get_indexed_logs(self, start, end, **kwargs):
            return [self._raw_log(rpc_log(i, 0)) for i in range(start, end + 1)]

    rows = list(
        OrderedClient().iter_indexed_logs_bisect(
            1,
            5,
            address=ADDRESS,
            result_limit=10,
            max_records=2,
        )
    )
    assert [r.block_number for r in rows] == [1, 2]
