import json
import urllib.error

import pytest

from hlp.data.rpc import RpcClient, RpcError


def test_chunked_logs_clamp_to_provider_advertised_range_limit():
    calls = []

    def transport(request, timeout):
        payload = json.loads(request.data)
        assert payload["method"] == "eth_getLogs"
        query = payload["params"][0]
        start = int(query["fromBlock"], 16)
        end = int(query["toBlock"], 16)
        calls.append((start, end))
        if end - start + 1 > 200:
            return json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "error": {
                        "code": -32602,
                        "message": "block range exceeds filtered limit",
                        "data": {
                            "reason": "filtered_range_limit",
                            "maxBlockRange": 200,
                        },
                    },
                }
            ).encode()
        return json.dumps(
            {"jsonrpc": "2.0", "id": payload["id"], "result": []}
        ).encode()

    rpc = RpcClient(
        "https://example.invalid",
        attempts=1,
        transport=transport,
    )

    assert list(
        rpc.iter_logs_chunked(
            0,
            499,
            chunk_size=2_000,
            min_chunk_size=25,
        )
    ) == []
    assert calls == [
        (0, 499),
        (0, 199),
        (200, 399),
        (400, 499),
    ]


def test_chunked_logs_do_not_shrink_range_after_exhausted_http_429():
    calls = 0

    def transport(request, timeout):
        nonlocal calls
        calls += 1
        raise urllib.error.HTTPError(
            request.full_url,
            429,
            "Too Many Requests",
            {"Retry-After": "0"},
            None,
        )

    rpc = RpcClient(
        "https://example.invalid",
        attempts=1,
        backoff_seconds=0,
        transport=transport,
    )

    with pytest.raises(RpcError) as raised:
        list(
            rpc.iter_logs_chunked(
                0,
                499,
                chunk_size=200,
                min_chunk_size=25,
            )
        )

    assert calls == 1
    assert raised.value.http_status == 429


def test_chunked_logs_reject_provider_range_below_caller_minimum():
    calls = 0

    def transport(request, timeout):
        nonlocal calls
        calls += 1
        payload = json.loads(request.data)
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "id": payload["id"],
                "error": {
                    "code": -32602,
                    "message": "block range exceeds filtered limit",
                    "data": {
                        "reason": "filtered_range_limit",
                        "maxBlockRange": 16,
                    },
                },
            }
        ).encode()

    rpc = RpcClient(
        "https://example.invalid",
        attempts=1,
        transport=transport,
    )

    with pytest.raises(RpcError) as raised:
        list(
            rpc.iter_logs_chunked(
                0,
                99,
                chunk_size=100,
                min_chunk_size=25,
            )
        )

    assert calls == 1
    assert raised.value.code == -32602
    assert raised.value.data["maxBlockRange"] == 16
