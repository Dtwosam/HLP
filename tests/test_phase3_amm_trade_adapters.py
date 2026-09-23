from hlp.data.phase3_trade_adapters import (
    PHASE3_AMM_TRADE_ADAPTER_VERSION,
    adapt_v3_swaps_to_phase3,
    adapt_v4_swaps_to_phase3,
)


TOKEN = "0x" + "11" * 20
QUOTE = "0x" + "22" * 20
POOL = "0x" + "33" * 20
POOL_ID = "0x" + "44" * 32
ROUTER = "0x" + "55" * 20
WALLET = "0x" + "66" * 20
TX = "0x" + "77" * 32


def tx_identity():
    return [{
        "transaction_hash": TX,
        "block_number": 10,
        "transaction_index": 2,
        "initiator": WALLET,
        "to": ROUTER,
        "value_raw": 0,
        "input_selector": "0x12345678",
        "transaction_type": 2,
    }]


def test_v3_adapter_uses_transaction_initiator_not_protocol_sender():
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
        source_id="direct_uniswap_v3",
    )

    row = rows[0]
    assert row["adapter_version"] == PHASE3_AMM_TRADE_ADAPTER_VERSION
    assert row["initiator"] == WALLET
    assert row["protocol_sender"] == ROUTER
    assert row["side"] == "buy"
    assert row["token_amount_raw"] == 100
    assert row["quote_amount_raw"] == 200
    assert row["source_id"] == "direct_uniswap_v3"


def test_v4_adapter_derives_sell_from_signed_token_leg():
    rows = adapt_v4_swaps_to_phase3(
        [{
            "pool_id": POOL_ID,
            "sender": ROUTER,
            "amount0": 100,
            "amount1": -200,
            "block_number": 10,
            "transaction_hash": TX,
            "transaction_index": 2,
            "log_index": 4,
        }],
        [{
            "pool_id": POOL_ID,
            "token": TOKEN,
            "quote_token": QUOTE,
        }],
        tx_identity(),
        source_id="direct_uniswap_v4",
    )

    row = rows[0]
    assert row["initiator"] == WALLET
    assert row["side"] == "sell"
    assert row["token_amount_raw"] == 100
    assert row["quote_amount_raw"] == 200
    assert row["source_id"] == "direct_uniswap_v4"


def test_amm_adapter_refuses_source_without_required_market_phase():
    import pytest

    with pytest.raises(ValueError, match="does not advertise"):
        adapt_v4_swaps_to_phase3(
            [],
            [{
                "pool_id": POOL_ID,
                "token": TOKEN,
                "quote_token": QUOTE,
            }],
            [],
            source_id="pools_fun",
        )
