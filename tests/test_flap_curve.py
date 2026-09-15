from decimal import Decimal

from hlp.data.flap_curve import (
    build_flap_curve_market_cap_points,
    summarize_flap_curve_market_caps,
)
from hlp.data.types import FlapEvent


TOKEN = "0x" + "11" * 20
ZERO = "0x" + "00" * 20


def event(kind, *, txi, logi, actor=None, price=None):
    return FlapEvent(
        event_type=kind,
        token=TOKEN,
        actor=actor,
        amount_raw=None,
        quote_amount_raw=None,
        fee_raw=None,
        post_price_raw=price,
        value_raw=None,
        value2_raw=None,
        pool=None,
        name=None,
        symbol=None,
        meta=None,
        block_number=10,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=txi,
        log_index=logi,
    )


def test_flap_curve_requires_observed_quote_and_uses_causal_usd():
    events = [
        event("token_created", txi=1, logi=0),
        event("quote_set", txi=1, logi=1, actor=ZERO),
        event("token_bought", txi=2, logi=0, price=10**10),
    ]
    anchors = [
        {
            "block_number": 10,
            "transaction_index": 1,
            "log_index": 2,
            "quote_per_token": "2000",
        }
    ]
    rows = list(
        build_flap_curve_market_cap_points(
            events,
            anchors,
            initial_weth_usd=Decimal("1900"),
        )
    )
    assert len(rows) == 1
    # Anchor precedes the trade: 1e-8 ETH * $2000 * 1B = $20,000.
    assert Decimal(rows[0]["quote_usd"]) == Decimal("2000")
    assert Decimal(rows[0]["market_cap_proxy_usd"]) == Decimal("20000")
    summary = summarize_flap_curve_market_caps(rows)
    assert summary[0]["crossed_100k"] is False


def test_flap_curve_does_not_guess_quote_before_quote_set():
    events = [
        event("token_created", txi=1, logi=0),
        event("token_bought", txi=1, logi=1, price=10**10),
    ]
    rows = list(
        build_flap_curve_market_cap_points(
            events,
            [],
            initial_weth_usd=Decimal("2000"),
        )
    )
    assert rows[0]["pricing_status"] == "missing_quote_event"
    assert rows[0]["market_cap_proxy_usd"] is None
