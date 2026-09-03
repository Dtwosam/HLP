from hlp.config import default_subscriptions


def test_subscription_contract() -> None:
    subscriptions = default_subscriptions()

    assert len(subscriptions) == 17
    assert {"type": "l2Book", "coin": "HYPE"} in subscriptions
    assert not any(
        item["type"] == "l2Book" and item.get("coin") in {"BTC", "ETH", "SOL"}
        for item in subscriptions
    )
