from decimal import Decimal

from hlp.data.flap_curve import (
    build_flap_curve_market_cap_points,
    flap_registry_state_before,
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


def test_flap_curve_does_not_preload_future_registry_quote():
    quote = "0x" + "33" * 20
    events = [
        event("token_created", txi=1, logi=0),
        event("token_bought", txi=1, logi=1, price=10**10),
        event("quote_set", txi=2, logi=0, actor=quote),
    ]
    registry = [{
        "token": TOKEN,
        "quote_token": quote,
        "launch_block": 10,
        "launch_transaction_index": 1,
        "launch_log_index": 0,
        "quote_set_block": 10,
        "quote_set_transaction_index": 2,
        "quote_set_log_index": 0,
    }]
    rows = list(
        build_flap_curve_market_cap_points(
            events,
            [],
            initial_weth_usd=Decimal("2000"),
            initial_quote_usd={quote: Decimal("2")},
            launch_registry=registry,
        )
    )
    assert len(rows) == 1
    assert rows[0]["pricing_status"] == "missing_quote_event"
    assert rows[0]["market_cap_proxy_usd"] is None


def test_flap_curve_bootstraps_only_pre_window_registry_state():
    quote = "0x" + "33" * 20
    trade = event("token_bought", txi=2, logi=0, price=10**18)
    registry = [{
        "token": TOKEN,
        "quote_token": quote,
        "launch_block": 9,
        "launch_transaction_index": 1,
        "launch_log_index": 0,
        "quote_set_block": 9,
        "quote_set_transaction_index": 1,
        "quote_set_log_index": 1,
    }]
    rows = list(
        build_flap_curve_market_cap_points(
            [trade],
            [],
            initial_weth_usd=Decimal("2000"),
            initial_quote_usd={quote: Decimal("2")},
            launch_registry=registry,
        )
    )
    assert len(rows) == 1
    assert rows[0]["quote_token"] == quote
    assert rows[0]["market_cap_proxy_usd"] == "2000000000"


def test_flap_curve_bootstraps_historical_quote_not_future_final_quote():
    quote_a = "0x" + "33" * 20
    quote_b = "0x" + "44" * 20
    trade = event("token_bought", txi=2, logi=0, price=10**18)
    registry = [{
        "token": TOKEN,
        "quote_token": quote_b,
        "launch_block": 9,
        "launch_transaction_index": 1,
        "launch_log_index": 0,
        "quote_set_block": 11,
        "quote_set_transaction_index": 1,
        "quote_set_log_index": 0,
        "quote_history": [
            {
                "quote_token": quote_a,
                "block_number": 9,
                "transaction_index": 1,
                "log_index": 1,
            },
            {
                "quote_token": quote_b,
                "block_number": 11,
                "transaction_index": 1,
                "log_index": 0,
            },
        ],
    }]

    launches, quotes = flap_registry_state_before(
        registry,
        (10, 2, 0),
    )
    assert TOKEN in launches
    assert quotes[TOKEN] == quote_a

    rows = list(
        build_flap_curve_market_cap_points(
            [trade],
            [],
            initial_weth_usd=Decimal("2000"),
            initial_quote_usd={
                quote_a: Decimal("2"),
                quote_b: Decimal("3"),
            },
            launch_registry=registry,
        )
    )
    assert rows[0]["quote_token"] == quote_a
    assert rows[0]["market_cap_proxy_usd"] == "2000000000"

