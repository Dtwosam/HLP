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


def test_find_first_code_block_binary_search():
    seen = []

    def transport(request, timeout):
        payload = json.loads(request.data)
        assert payload["method"] == "eth_getCode"
        block = int(payload["params"][1], 16)
        seen.append(block)
        result = "0x6000" if block >= 37 else "0x"
        return json.dumps({"jsonrpc": "2.0", "id": 1, "result": result}).encode()

    rpc = RpcClient("https://example.invalid", transport=transport)
    assert rpc.find_first_code_block("0x" + "11" * 20, low=0, high=100) == 37
    assert len(seen) < 12


def test_chunked_logs_adapts_to_provider_range_limit():
    calls = []

    class Limited(RpcClient):
        def get_logs(self, from_block, to_block, **kwargs):
            calls.append((from_block, to_block))
            if to_block - from_block + 1 > 4:
                raise __import__("hlp.data.rpc", fromlist=["RpcError"]).RpcError("range too wide")
            return []

    rpc = Limited("https://example.invalid")
    assert list(rpc.iter_logs_chunked(0, 9, chunk_size=8)) == []
    assert calls[0] == (0, 7)
    assert calls[1] == (0, 3)
    assert (4, 9) in calls
    assert calls[-1] == (8, 9)


def test_rpc_counts_transport_attempts():
    rpc = RpcClient(
        "https://example.invalid",
        transport=make_transport([("eth_chainId", hex(4663))]),
    )
    assert rpc.chain_id() == 4663
    assert rpc.requests_made == 1


def test_retry_after_header_is_parsed_for_429():
    import urllib.error

    error = urllib.error.HTTPError(
        "https://example.invalid",
        429,
        "Too Many Requests",
        {"Retry-After": "7"},
        None,
    )
    assert RpcClient._retry_after_seconds(error) == 7.0


def test_non_429_has_no_retry_after():
    import urllib.error

    error = urllib.error.HTTPError(
        "https://example.invalid",
        500,
        "Server Error",
        {"Retry-After": "7"},
        None,
    )
    assert RpcClient._retry_after_seconds(error) is None


def test_extra_headers_are_attached_without_changing_url():
    captured = {}

    def transport(request, timeout):
        captured["url"] = request.full_url
        captured["key"] = request.get_header("X-api-key")
        return json.dumps({"jsonrpc": "2.0", "id": 1, "result": hex(4663)}).encode()

    rpc = RpcClient(
        "https://rpc.example.invalid/evm/4663",
        extra_headers={"X-API-Key": "secret-value"},
        transport=transport,
    )
    assert rpc.chain_id() == 4663
    assert captured["url"] == "https://rpc.example.invalid/evm/4663"
    assert captured["key"] == "secret-value"


def test_chunked_logs_fail_fast_before_range_shrink():
    calls = []

    def transport(request, timeout):
        payload = json.loads(request.data)
        query = payload["params"][0]
        start = int(query["fromBlock"], 16)
        end = int(query["toBlock"], 16)
        calls.append((start, end))
        width = end - start + 1
        if width > 4:
            return json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {"code": -32602, "message": "range too wide"},
                }
            ).encode()
        return json.dumps({"jsonrpc": "2.0", "id": 1, "result": []}).encode()

    rpc = RpcClient(
        "https://example.invalid",
        attempts=5,
        transport=transport,
    )
    list(rpc.iter_logs_chunked(0, 7, chunk_size=8, min_chunk_size=1))
    # One failed width=8 request, then two successful width=4 pages.
    assert calls == [(0, 7), (0, 3), (4, 7)]



def test_batch_call_preserves_request_order():
    def transport(request, timeout):
        payload = json.loads(request.data)
        assert isinstance(payload, list)
        assert [item["method"] for item in payload] == [
            "eth_getBlockByNumber",
            "eth_getBlockByNumber",
        ]
        # Return deliberately reversed: JSON-RPC batch response order is not
        # guaranteed.
        return json.dumps(
            [
                {"jsonrpc": "2.0", "id": 2, "result": {"number": hex(11)}},
                {"jsonrpc": "2.0", "id": 1, "result": {"number": hex(10)}},
            ]
        ).encode()

    rpc = RpcClient("https://example.invalid", transport=transport)
    rows = rpc.get_blocks_batched([10, 11], batch_size=2)
    assert [int(row["number"], 16) for row in rows] == [10, 11]
    assert rpc.requests_made == 1


def test_batched_blocks_fall_back_to_single_rpc_if_batch_unsupported():
    calls = []

    def transport(request, timeout):
        payload = json.loads(request.data)
        calls.append(payload)
        if isinstance(payload, list):
            return json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {"code": -32600, "message": "batch disabled"},
                }
            ).encode()
        block = int(payload["params"][0], 16)
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"number": hex(block)},
            }
        ).encode()

    rpc = RpcClient("https://example.invalid", transport=transport)
    rows = rpc.get_blocks_batched(
        [10],
        batch_size=1,
        min_batch_size=1,
    )
    assert int(rows[0]["number"], 16) == 10
    assert len(calls) == 2
