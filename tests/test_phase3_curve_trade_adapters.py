from dataclasses import replace

from hlp.data.phase3_trade_adapters import (
    PHASE3_CURVE_TRADE_ADAPTER_VERSION,
    adapt_flap_trades_to_phase3,
    adapt_hood_fun_trades_to_phase3,
    adapt_trench_trades_to_phase3,
    adapt_v3_swaps_to_phase3,
)
from hlp.data.types import TrenchEvent


TOKEN = "0x" + "11" * 20
QUOTE = "0x" + "22" * 20
WALLET = "0x" + "33" * 20
ACTOR = "0x" + "44" * 20
ROUTER = "0x" + "55" * 20
POOL = "0x" + "66" * 20
TX = "0x" + "77" * 32


def tx_identity(block=10, tx_hash=TX):
    return [{
        "transaction_hash": tx_hash,
        "block_number": block,
        "transaction_index": 2,
        "initiator": WALLET,
        "to": ROUTER,
        "value_raw": 0,
        "input_selector": "0x12345678",
        "transaction_type": 2,
    }]


def test_v3_adapter_accepts_sushiswap_v3_source():
    rows = adapt_v3_swaps_to_phase3(
        [{
            "pool": POOL,
            "sender": ROUTER,
            "recipient": WALLET,
            "amount0": -100,
            "amount1": 200,
            "block_number": 10,
            "transaction_hash": TX,
            "transaction_index": 2,
            "log_index": 4,
        }],
        [{
            "pool": POOL,
            "token": TOKEN,
            "quote_token": QUOTE,
        }],
        tx_identity(),
        source_id="pools_fun",
    )
    assert rows[0]["source_id"] == "pools_fun"
    assert rows[0]["side"] == "buy"


def test_flap_adapter_uses_tx_from_and_preserves_protocol_actor():
    rows = adapt_flap_trades_to_phase3(
        [{
            "event_type": "token_bought",
            "token": TOKEN,
            "actor": ACTOR,
            "quote_token": QUOTE,
            "amount_raw": 100,
            "quote_amount_raw": 200,
            "block_number": 10,
            "transaction_hash": TX,
            "transaction_index": 2,
            "log_index": 4,
        }],
        tx_identity(),
    )
    row = rows[0]
    assert row["adapter_version"] == PHASE3_CURVE_TRADE_ADAPTER_VERSION
    assert row["initiator"] == WALLET
    assert row["protocol_actor"] == ACTOR
    assert row["side"] == "buy"
    assert row["token_amount_raw"] == 100
    assert row["quote_amount_raw"] == 200


def test_hood_fun_adapter_maps_buy_and_generation():
    rows = adapt_hood_fun_trades_to_phase3(
        [{
            "generation": "current",
            "event_type": "trade",
            "token": TOKEN,
            "actor": ACTOR,
            "quote_token": QUOTE,
            "is_buy": False,
            "token_amount_raw": 100,
            "quote_amount_raw": 200,
            "block_number": 10,
            "transaction_hash": TX,
            "transaction_index": 2,
            "log_index": 4,
        }],
        tx_identity(),
        source_id="hood_fun_current",
    )
    row = rows[0]
    assert row["source_id"] == "hood_fun_current"
    assert row["initiator"] == WALLET
    assert row["side"] == "sell"


def test_trench_adapter_accepts_raw_dataclass_trade_event():
    event = TrenchEvent(
        event_type="token_purchase",
        token=TOKEN,
        actor=ACTOR,
        curve=None,
        quote_token=None,
        amount_raw=100,
        quote_amount_raw=200,
        protocol_fee_raw=1,
        extra_fee_raw=2,
        extra_fee_receiver=None,
        extra_fee_rate=None,
        real_quote_reserves_raw=None,
        real_token_reserves_raw=None,
        virtual_quote_raw=None,
        virtual_token_raw=None,
        name=None,
        symbol=None,
        token_uri=None,
        timestamp=None,
        block_number=10,
        transaction_hash=TX,
        transaction_index=2,
        log_index=4,
    )
    rows = adapt_trench_trades_to_phase3(
        [event],
        [{
            "token": TOKEN,
            "quote_token": QUOTE,
        }],
        tx_identity(),
    )
    row = rows[0]
    assert row["source_id"] == "trench_today"
    assert row["initiator"] == WALLET
    assert row["protocol_actor"] == ACTOR
    assert row["side"] == "buy"
