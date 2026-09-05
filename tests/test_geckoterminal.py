from email.message import Message
import json
import urllib.error

import pytest

import hlp.data.geckoterminal as geckoterminal
from hlp.data.geckoterminal import GeckoTerminalClient, GeckoTerminalError



class FakeGecko(GeckoTerminalClient):
    def __init__(self, payloads):
        super().__init__(min_interval_seconds=0)
        self.payloads = list(payloads)
        self.calls = []

    def _request(self, path, params=None):
        self.calls.append((path, params))
        return self.payloads.pop(0)


def test_pool_normalizes_geckoterminal_relationship_tokens():
    client = FakeGecko(
        [
            {
                "data": {
                    "attributes": {
                        "address": "0x" + "AA" * 20,
                        "name": "MEME / WETH",
                        "base_token_price_usd": "0.00123",
                        "quote_token_price_usd": "2500",
                        "reserve_in_usd": "12345.67",
                        "pool_created_at": "2026-08-01T00:00:00Z",
                    },
                    "relationships": {
                        "base_token": {
                            "data": {
                                "id": "robinhood_0x" + "11" * 20,
                            }
                        },
                        "quote_token": {
                            "data": {
                                "id": "robinhood_0x" + "22" * 20,
                            }
                        },
                    },
                }
            }
        ]
    )
    row = client.pool("0x" + "aa" * 20)
    assert row["pool_address"] == "0x" + "aa" * 20
    assert row["base_token"] == "0x" + "11" * 20
    assert row["quote_token"] == "0x" + "22" * 20
    assert row["base_token_price_usd"] == "0.00123"
    assert row["reserve_in_usd"] == "12345.67"
    assert client.calls == [
        (
            "/networks/robinhood/pools/" + "0x" + "aa" * 20,
            None,
        )
    ]


def test_ohlcv_normalizes_and_sorts_rows():
    client = FakeGecko(
        [
            {
                "data": {
                    "attributes": {
                        "ohlcv_list": [
                            [200, 2, 3, 1, 2.5, 10],
                            [100, "1", "2", "0.5", "1.5", "8"],
                        ]
                    }
                }
            }
        ]
    )
    rows = client.ohlcv(
        "0x" + "33" * 32,
        aggregate=5,
        before_timestamp=300,
        limit=20,
    )
    assert [row["timestamp"] for row in rows] == [100, 200]
    assert rows[0]["low"] == "0.5"
    assert rows[1]["close"] == "2.5"
    path, params = client.calls[0]
    assert path.endswith("/ohlcv/minute")
    assert params["aggregate"] == 5
    assert params["before_timestamp"] == 300
    assert params["limit"] == 20
    assert params["currency"] == "usd"
    assert params["token"] == "base"


def test_ohlcv_rejects_invalid_parameters():
    client = FakeGecko([])
    try:
        client.ohlcv("0x1", timeframe="minute", aggregate=4)
    except ValueError as exc:
        assert "invalid minute OHLCV aggregate" in str(exc)
    else:
        raise AssertionError("invalid aggregate should fail")

    try:
        client.ohlcv("0x1", limit=1001)
    except ValueError as exc:
        assert "limit must be between 1 and 1000" in str(exc)
    else:
        raise AssertionError("invalid limit should fail")


class _FakeResponse:
    def __init__(self, payload):
        self.raw = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.raw


def test_request_paces_retry_attempts_and_counts_all_http_calls(monkeypatch):
    now = [0.0]
    sleeps = []
    calls = []
    headers = Message()
    headers["Retry-After"] = "1"

    def monotonic():
        return now[0]

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    def urlopen(request, timeout):
        calls.append((request.full_url, timeout, now[0]))
        if len(calls) == 1:
            raise urllib.error.HTTPError(
                request.full_url,
                429,
                "rate limited",
                headers,
                None,
            )
        return _FakeResponse({"data": {"attributes": {}}})

    monkeypatch.setattr(geckoterminal.time, "monotonic", monotonic)
    monkeypatch.setattr(geckoterminal.time, "sleep", sleep)
    monkeypatch.setattr(geckoterminal.urllib.request, "urlopen", urlopen)

    client = GeckoTerminalClient(
        attempts=2,
        min_interval_seconds=6.1,
    )
    payload = client._request("/probe")

    assert payload["data"] == {"attributes": {}}
    assert client.requests_made == 2
    assert client.bytes_received > 0
    assert len(calls) == 2
    assert calls[1][2] == pytest.approx(6.1)
    assert sum(sleeps) == pytest.approx(6.1)


def test_request_honors_long_retry_after(monkeypatch):
    now = [0.0]
    sleeps = []
    calls = 0
    headers = Message()
    headers["Retry-After"] = "9"

    def monotonic():
        return now[0]

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    def urlopen(request, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise urllib.error.HTTPError(
                request.full_url,
                503,
                "unavailable",
                headers,
                None,
            )
        return _FakeResponse({"data": {}})

    monkeypatch.setattr(geckoterminal.time, "monotonic", monotonic)
    monkeypatch.setattr(geckoterminal.time, "sleep", sleep)
    monkeypatch.setattr(geckoterminal.urllib.request, "urlopen", urlopen)

    client = GeckoTerminalClient(
        attempts=2,
        min_interval_seconds=6.1,
    )
    client._request("/probe")

    assert calls == 2
    assert sleeps == [9.0]
    assert client.requests_made == 2


def test_request_does_not_retry_permanent_http_error(monkeypatch):
    calls = 0

    def urlopen(request, timeout):
        nonlocal calls
        calls += 1
        raise urllib.error.HTTPError(
            request.full_url,
            404,
            "not found",
            Message(),
            None,
        )

    monkeypatch.setattr(geckoterminal.urllib.request, "urlopen", urlopen)

    client = GeckoTerminalClient(
        attempts=3,
        min_interval_seconds=0,
    )
    with pytest.raises(GeckoTerminalError, match="HTTP Error 404"):
        client._request("/missing")

    assert calls == 1
    assert client.requests_made == 1


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("attempts", 0, "attempts must be positive"),
        ("timeout", 0, "timeout must be positive"),
        (
            "min_interval_seconds",
            -1,
            "min_interval_seconds cannot be negative",
        ),
    ],
)
def test_request_rejects_invalid_client_limits(field, value, message):
    kwargs = {field: value}
    client = GeckoTerminalClient(**kwargs)

    with pytest.raises(ValueError, match=message):
        client._request("/probe")
