import pytest

from hlp.data.flap_lifecycle import (
    build_flap_graduation_market_handoffs,
    summarize_flap_graduation_market_handoffs,
)


TOKEN = "0x" + "11" * 20
QUOTE = "0x" + "22" * 20
POOL = "0x" + "33" * 20


def flap_row(pool=POOL, quote=QUOTE):
    return {
        "token": TOKEN,
        "graduation_block": 20,
        "graduation_transaction_hash": "0x" + "aa" * 32,
        "graduation_transaction_index": 2,
        "graduation_log_index": 5,
        "graduation_pool": pool,
        "graduation_quote_token": quote,
        "graduation_dex_id": 2,
        "graduation_lp_fee_profile": 1,
    }


def market_row(pool=POOL, token=TOKEN, quote=QUOTE):
    return {
        "source_id": "direct_uniswap_v3",
        "venue": "uniswap_v3",
        "source_kind": "direct_dex",
        "token": token,
        "quote_token": quote,
        "quote_decimals": 18,
        "pool": pool,
        "initialize_block": 20,
        "initialize_transaction_index": 2,
        "initialize_log_index": 3,
        "initial_sqrt_price_x96": 2**96,
        "initial_tick": 0,
    }


def test_flap_graduation_handoff_matches_exact_address_market():
    rows = build_flap_graduation_market_handoffs(
        [flap_row()],
        [market_row()],
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["market_handoff_complete"] is True
    assert row["market_source_id"] == "direct_uniswap_v3"
    assert row["market_available_at_graduation"] is True
    assert row["market_initialize_order_relation"] == "before_graduation"

    summary = summarize_flap_graduation_market_handoffs(rows)
    assert summary["graduated_tokens"] == 1
    assert summary["matched_address_markets"] == 1
    assert summary["all_graduations_resolved"] is True
    assert summary["v4_pool_id_inference_used"] is False


def test_flap_graduation_handoff_keeps_unmatched_pool_unresolved():
    rows = build_flap_graduation_market_handoffs(
        [flap_row()],
        [],
    )

    assert rows[0]["market_match_status"] == "unmatched_address_market"
    assert rows[0]["market_handoff_complete"] is False
    assert summarize_flap_graduation_market_handoffs(rows)[
        "all_graduations_resolved"
    ] is False


def test_flap_graduation_handoff_ignores_pool_id_only_market():
    v4 = {
        **market_row(),
        "source_id": "direct_uniswap_v4",
        "venue": "uniswap_v4",
        "pool_id": "0x" + "44" * 32,
    }
    del v4["pool"]
    rows = build_flap_graduation_market_handoffs(
        [flap_row()],
        [v4],
    )
    assert rows[0]["market_handoff_complete"] is False


def test_flap_graduation_handoff_rejects_token_or_quote_mismatch():
    with pytest.raises(ValueError, match="token mismatch"):
        build_flap_graduation_market_handoffs(
            [flap_row()],
            [market_row(token="0x" + "55" * 20)],
        )
    with pytest.raises(ValueError, match="quote mismatch"):
        build_flap_graduation_market_handoffs(
            [flap_row()],
            [market_row(quote="0x" + "66" * 20)],
        )


def test_flap_graduation_handoff_rejects_duplicate_market_pool():
    with pytest.raises(ValueError, match="duplicate address-based"):
        build_flap_graduation_market_handoffs(
            [flap_row()],
            [market_row(), market_row()],
        )
