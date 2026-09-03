from hlp.recorder import _extract_coin, _extract_exchange_time_ms


def test_extract_trade_batch_metadata() -> None:
    message = {
        "channel": "trades",
        "data": [
            {"coin": "HYPE", "time": 100, "px": "50.0", "sz": "1"},
            {"coin": "HYPE", "time": 110, "px": "50.1", "sz": "2"},
        ],
    }

    assert _extract_coin(message) == "HYPE"
    assert _extract_exchange_time_ms(message) == 110


def test_extract_book_metadata() -> None:
    message = {
        "channel": "l2Book",
        "data": {"coin": "HYPE", "time": 123, "levels": [[], []]},
    }

    assert _extract_coin(message) == "HYPE"
    assert _extract_exchange_time_ms(message) == 123


def test_extract_subscription_ack_coin() -> None:
    message = {
        "channel": "subscriptionResponse",
        "data": {
            "method": "subscribe",
            "subscription": {"type": "trades", "coin": "HYPE"},
        },
    }

    assert _extract_coin(message) == "HYPE"
