import json

from hlp.data.rpc import RpcClient


def make_transport(results):
    queue = list(results)

    def transport(request, timeout):
        payload = json.loads(request.data)
        expected_method, result = queue.pop(0)
        assert payload["method"] == expected_method
        return json.dumps({"jsonrpc": "2.0", "id": 1, "result": result}).encode()

    return transport


def test_chain_and_head_quantities():
    rpc = RpcClient(
        "https://example.invalid",
        transport=make_transport(
            [
                ("eth_chainId", hex(4663)),
                ("eth_blockNumber", hex(12345)),
            ]
        ),
    )
    rpc.assert_robinhood()
    assert rpc.block_number() == 12345


def test_get_logs_normalizes_rpc_record():
    log = {
        "address": "0x" + "aa" * 20,
        "blockHash": "0x" + "11" * 32,
        "blockNumber": hex(10),
        "data": "0x",
        "logIndex": hex(2),
        "removed": False,
        "topics": ["0x" + "22" * 32],
        "transactionHash": "0x" + "33" * 32,
        "transactionIndex": hex(1),
    }
    rpc = RpcClient(
        "https://example.invalid",
        transport=make_transport([("eth_getLogs", [log])]),
    )
    records = rpc.get_logs(10, 10)
    assert len(records) == 1
    assert records[0].block_number == 10
    assert records[0].log_index == 2
    assert records[0].chain_id == 4663
