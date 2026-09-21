import pytest

from hlp.data.trench_lifecycle import (
    build_trench_limit_market_candidates,
    summarize_trench_limit_market_candidates,
)


TOKEN = "0x" + "11" * 20
ZERO = "0x" + "00" * 20
WETH = "0x0bd7d308f8e1639fab988df18a8011f41eacad73"


def launch():
    return {
        "token": TOKEN,
        "quote_token": ZERO,
        "limit_reach_block": 100,
        "limit_reach_transaction_hash": "0x" + "aa" * 32,
        "limit_reach_transaction_index": 4,
        "limit_reach_log_index": 8,
    }


def market(
    *,
    source_id="direct_uniswap_v3",
    pool="0x" + "22" * 20,
    block=100,
    tx_hash="0x" + "aa" * 32,
    tx_index=4,
    log_index=9,
):
    return {
        "source_id": source_id,
        "venue": "uniswap_v3",
        "source_kind": "direct_dex",
        "token": TOKEN,
        "quote_token": WETH,
        "pool": pool,
        "initialize_block": block,
        "initialize_transaction_hash": tx_hash,
        "initialize_transaction_index": tx_index,
        "initialize_log_index": log_index,
    }


def test_trench_limit_candidates_map_native_quote_to_weth():
    rows = build_trench_limit_market_candidates(
        [launch()],
        [market()],
    )
    assert len(rows) == 1
    assert rows[0]["candidate_status"] == "matching_direct_market"
    assert rows[0]["dex_quote_token"] == WETH
    assert rows[0]["same_transaction"] is True
    assert rows[0]["same_block"] is True
    assert rows[0]["initialize_order_relation"] == "after_limit"


def test_trench_limit_candidates_preserve_multiple_markets():
    rows = build_trench_limit_market_candidates(
        [launch()],
        [
            market(),
            market(
                source_id="direct_sushiswap_v3",
                pool="0x" + "33" * 20,
                block=101,
                tx_hash="0x" + "bb" * 32,
                tx_index=1,
                log_index=2,
            ),
        ],
    )
    assert len(rows) == 2
    assert {row["candidate_count_for_token"] for row in rows} == {2}
    summary = summarize_trench_limit_market_candidates(rows)
    assert summary["multi_candidate_tokens"] == 1
    assert summary["handoff_rule_frozen"] is False


def test_trench_limit_candidates_keep_unmatched_token_explicit():
    rows = build_trench_limit_market_candidates([launch()], [])
    assert len(rows) == 1
    assert rows[0]["candidate_status"] == "no_matching_direct_market"
    summary = summarize_trench_limit_market_candidates(rows)
    assert summary["tokens_without_candidates"] == 1
    assert summary["source_coverage_complete"] is False


def test_trench_limit_candidates_reject_non_direct_market():
    bad = {
        **market(),
        "source_kind": "launchpad",
    }
    with pytest.raises(ValueError, match="not direct_dex"):
        build_trench_limit_market_candidates([launch()], [bad])
