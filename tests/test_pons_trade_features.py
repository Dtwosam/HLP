from decimal import Decimal

from hlp.data.pons_trade_features import build_pons_causal_trade_features


TOKEN = "0x" + "11" * 20
A = "0x" + "aa" * 20
B = "0x" + "bb" * 20


def trade(block, logi, wallet, side):
    return {
        "token": TOKEN,
        "pons_version": "v1",
        "phase": "v3",
        "side": side,
        "initiator": wallet,
        "transaction_hash": "0x" + f"{block * 10 + logi:064x}",
        "block_number": block,
        "block_timestamp": 1000 + block * 7,
        "transaction_index": 1,
        "log_index": logi,
        "token_amount_raw": 1,
        "quote_amount_raw": 1,
        "quote_token": "0x" + "22" * 20,
        "market_cap_proxy_usd": "100000",
    }


def test_causal_trade_features_track_new_and_repeat_buyers():
    rows = build_pons_causal_trade_features([
        trade(1, 0, A, "buy"),
        trade(2, 0, B, "buy"),
        trade(3, 0, A, "buy"),
        trade(4, 0, A, "sell"),
    ])
    assert rows[0]["is_new_buyer"] is True
    assert rows[1]["unique_buyers_so_far"] == 2
    assert rows[2]["is_repeat_buyer"] is True
    assert rows[2]["wallet_buy_number"] == 2
    assert Decimal(rows[2]["repeat_buyer_trade_share_so_far"]) == Decimal(1) / Decimal(3)
    assert rows[3]["is_new_seller"] is True
    assert rows[3]["unique_sellers_so_far"] == 1
    assert rows[3]["wallet_prior_buy_count"] == 2


def test_side_streak_resets_on_direction_change():
    rows = build_pons_causal_trade_features([
        trade(1, 0, A, "buy"),
        trade(2, 0, B, "buy"),
        trade(3, 0, A, "sell"),
    ])
    assert rows[1]["current_side_streak_trades"] == 2
    assert rows[2]["current_side_streak"] == "sell"
    assert rows[2]["current_side_streak_trades"] == 1
