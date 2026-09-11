import pytest

from hlp.data.pons_trades import normalize_pons_trades


TOKEN = "0x" + "11" * 20
QUOTE = "0x" + "22" * 20
INITIATOR = "0x" + "33" * 20


def base(**updates):
    row = {
        "token": TOKEN,
        "quote_token": QUOTE,
        "pons_version": "v1",
        "phase": "v3",
        "event_type": "v3_swap",
        "initiator": INITIATOR,
        "transaction_hash": "0x" + "aa" * 32,
        "transaction_to": "0x" + "44" * 20,
        "input_selector": "0x12345678",
        "block_number": 10,
        "block_timestamp": 1000,
        "transaction_index": 1,
        "log_index": 2,
        "amount0": -100,
        "amount1": 20,
        "market_cap_proxy_usd": "120000",
        "drawdown_from_running_peak": "0.2",
        "seconds_since_first_priced_point": 30,
    }
    row.update(updates)
    return row


def test_normalize_v3_buy_and_sell_from_signed_token_leg():
    buy = normalize_pons_trades([base()])[0]
    assert buy["side"] == "buy"
    assert buy["token_amount_raw"] == 100
    assert buy["quote_amount_raw"] == 20

    sell = normalize_pons_trades([
        base(
            transaction_hash="0x" + "bb" * 32,
            amount0=50,
            amount1=-11,
        )
    ])[0]
    assert sell["side"] == "sell"
    assert sell["token_amount_raw"] == 50
    assert sell["quote_amount_raw"] == 11


def test_normalize_v2_curve_uses_explicit_protocol_side():
    row = base(
        pons_version="v2",
        phase="curve",
        event_type="curve_sell",
        token_amount=700,
        quote_amount=90,
        fee=2,
        tax=1,
    )
    out = normalize_pons_trades([row])[0]
    assert out["side"] == "sell"
    assert out["token_amount_raw"] == 700
    assert out["quote_amount_raw"] == 90
    assert out["fee_raw"] == 2
    assert out["tax_raw"] == 1


def test_protocol_buyback_and_initialization_are_not_wallet_trades():
    rows = [
        base(
            pons_version="v2",
            phase="curve",
            event_type="curve_initialized",
        ),
        base(
            pons_version="v2",
            phase="curve",
            event_type="curve_buyback",
        ),
        base(
            event_type="v3_initialize",
        ),
    ]
    assert normalize_pons_trades(rows) == []


def test_amm_side_invariant_fails_if_both_legs_same_direction():
    with pytest.raises(ValueError):
        normalize_pons_trades([base(amount0=-100, amount1=-20)])
