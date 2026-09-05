from hlp.data.geckoterminal import GeckoTerminalClient


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
