import pytest

from hlp.data.pools_trade_lbp_success import (
    POOLS_TRADE_LBP_SUCCESS_SAMPLE_VERSION,
    validate_pools_trade_lbp_success_sample,
)
from hlp.protocols.uniswap import v4_pool_id


TOKEN = "0x" + "22" * 20
CURRENCY = "0x" + "11" * 20
HOOKS = "0x" + "00" * 20
POOL_ID = v4_pool_id(
    currency0=CURRENCY,
    currency1=TOKEN,
    fee=2500,
    tick_spacing=50,
    hooks=HOOKS,
)


def sample():
    return {
        "version": POOLS_TRADE_LBP_SUCCESS_SAMPLE_VERSION,
        "chain_id": 4663,
        "discovery_from_block": 100,
        "discovery_to_block": 200,
        "search_from_block": 100,
        "search_to_block": 300,
        "continuous_search": True,
        "missing_ranges": [],
        "candidates": 1,
        "successful_candidates": 1,
        "matches": [{
            "candidate": {
                "initializer": "0x" + "33" * 20,
                "token": TOKEN,
                "currency": CURRENCY,
                "pool_fee": 2500,
                "pool_tick_spacing": 50,
                "pool_hook": HOOKS,
                "initializer_created_block": 150,
                "derived_pool_id": POOL_ID,
            },
            "initialize": {
                "pool_id": POOL_ID,
                "currency0": CURRENCY,
                "currency1": TOKEN,
                "fee": 2500,
                "tick_spacing": 50,
                "hooks": HOOKS,
                "sqrt_price_x96": 2**96,
                "tick": 0,
                "block_number": 220,
                "transaction_hash": "0x" + "aa" * 32,
                "transaction_index": 1,
                "log_index": 2,
            },
        }],
        "search_rpc_requests": 10,
    }


def validate(row):
    return validate_pools_trade_lbp_success_sample(
        row,
        expected_discovery_from=100,
        expected_discovery_to=200,
        expected_search_from=100,
        expected_search_to=300,
    )


def test_validate_lbp_success_sample_accepts_exact_poolkey_match():
    row = validate(sample())
    assert row["successful_candidates"] == 1
    assert row["matches"][0]["initialize"]["pool_id"] == POOL_ID


def test_validate_lbp_success_sample_accepts_zero_successes():
    data = sample()
    data["successful_candidates"] = 0
    data["matches"] = []
    row = validate(data)
    assert row["successful_candidates"] == 0


def test_validate_lbp_success_sample_rejects_poolkey_mismatch():
    data = sample()
    data["initialize"] = None
    data["matches"][0]["initialize"]["fee"] = 3000
    with pytest.raises(ValueError, match="PoolKey disagrees"):
        validate(data)


def test_validate_lbp_success_sample_rejects_incomplete_search():
    data = sample()
    data["missing_ranges"] = [[201, 210]]
    with pytest.raises(ValueError, match="missing ranges"):
        validate(data)
