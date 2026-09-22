from hlp.data.phase3_trade_adapters import (
    PHASE3_CCA_TRADE_ADAPTER_VERSION,
    PHASE3_PONS_TRADE_ADAPTER_VERSION,
    adapt_pools_trade_cca_fills_to_phase3,
    adapt_pons_trades_to_phase3,
)
from hlp.data.phase3_trade_features import (
    PHASE3_CANONICAL_TRADE_VERSION,
    validate_phase3_canonical_trade_row,
)


TOKEN = "0x" + "11" * 20
QUOTE = "0x" + "22" * 20
WALLET = "0x" + "aa" * 20
TX = "0x" + "bb" * 32


def pons_row(version="v1"):
    return {
        "token": TOKEN,
        "pons_version": version,
        "phase": "v3" if version == "v1" else "curve",
        "side": "buy",
        "initiator": WALLET,
        "transaction_hash": TX,
        "block_number": 10,
        "block_timestamp": 1234,
        "transaction_index": 2,
        "log_index": 3,
        "token_amount_raw": 100,
        "quote_amount_raw": 200,
        "quote_token": QUOTE,
        "market_cap_proxy_usd": "999999",
        "drawdown_from_running_peak": "0.7",
        "seconds_since_first_priced_point": 123,
    }


def test_pons_phase3_adapter_maps_v1_v2_and_strips_derived_price_fields():
    rows = adapt_pons_trades_to_phase3([
        pons_row("v1"),
        {
            **pons_row("v2"),
            "transaction_hash": "0x" + "cc" * 32,
            "block_number": 11,
        },
    ])

    assert [row["source_id"] for row in rows] == [
        "pons_v1",
        "pons_v2",
    ]
    for row in rows:
        assert row["version"] == PHASE3_CANONICAL_TRADE_VERSION
        assert row["adapter_version"] == PHASE3_PONS_TRADE_ADAPTER_VERSION
        assert row["canonical_phase3_trade"] is True
        assert row["outcome_derived"] is False
        assert "market_cap_proxy_usd" not in row
        assert "drawdown_from_running_peak" not in row
        assert "seconds_since_first_priced_point" not in row
        assert validate_phase3_canonical_trade_row(row)["token"] == TOKEN


def test_pons_phase3_adapter_rejects_duplicate_token_event():
    import pytest

    with pytest.raises(ValueError, match="repeats token event"):
        adapt_pons_trades_to_phase3([
            pons_row("v1"),
            pons_row("v1"),
        ])



def test_pools_trade_cca_adapter_uses_finalized_exit_as_causal_event():
    initializer = "0x" + "33" * 20
    exit_tx = "0x" + "cc" * 32
    bid_tx = "0x" + "dd" * 32
    rows = adapt_pools_trade_cca_fills_to_phase3(
        [{
            "version": "pools-trade-cca-fill-v1",
            "auction": initializer,
            "bid_id": 4,
            "owner": WALLET,
            "max_price_q96": 1000,
            "currency_amount_submitted_raw": 500,
            "currency_refunded_raw": 100,
            "quote_amount_raw": 400,
            "token_amount_raw": 200,
            "bid_block_number": 10,
            "bid_transaction_hash": bid_tx,
            "bid_transaction_index": 1,
            "bid_log_index": 2,
            "exit_block_number": 20,
            "exit_transaction_hash": exit_tx,
            "exit_transaction_index": 3,
            "exit_log_index": 4,
            "finalized_fill": True,
            "outcome_derived": False,
        }],
        [{
            "initializer": initializer,
            "token": TOKEN,
            "quote_token": QUOTE,
        }],
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["adapter_version"] == PHASE3_CCA_TRADE_ADAPTER_VERSION
    assert row["source_id"] == "pools_trade_lbp"
    assert row["phase"] == "cca"
    assert row["side"] == "buy"
    assert row["initiator"] == WALLET
    assert row["token_amount_raw"] == 200
    assert row["quote_amount_raw"] == 400
    assert row["block_number"] == 20
    assert row["transaction_hash"] == exit_tx
    assert row["cca_bid_block_number"] == 10
    assert row["cca_bid_transaction_hash"] == bid_tx
    assert row["fill_finalization_kind"] == "cca_bid_exit"


def test_pools_trade_cca_adapter_rejects_unfinalized_fill():
    import pytest

    with pytest.raises(ValueError, match="not finalized"):
        adapt_pools_trade_cca_fills_to_phase3(
            [{
                "auction": "0x" + "33" * 20,
                "finalized_fill": False,
                "outcome_derived": False,
            }],
            [{
                "initializer": "0x" + "33" * 20,
                "token": TOKEN,
                "quote_token": QUOTE,
            }],
        )
