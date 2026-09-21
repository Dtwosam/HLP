import pytest

from hlp.data.pools_trade_lbp_search import (
    POOLS_TRADE_LBP_POOL_INIT_SEARCH_VERSION,
    validate_pools_trade_lbp_pool_init_search,
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


def report(*, found=False):
    initialize = None
    if found:
        initialize = {
            "pool_id": POOL_ID,
            "currency0": CURRENCY,
            "currency1": TOKEN,
            "fee": 2500,
            "tick_spacing": 50,
            "hooks": HOOKS,
            "sqrt_price_x96": 2**96,
            "tick": 0,
            "block_number": 150,
            "transaction_hash": "0x" + "aa" * 32,
            "transaction_index": 1,
            "log_index": 2,
        }
    return {
        "version": POOLS_TRADE_LBP_POOL_INIT_SEARCH_VERSION,
        "chain_id": 4663,
        "token": TOKEN,
        "pool_id": POOL_ID,
        "search_from_block": 100,
        "search_to_block": 200,
        "continuous": True,
        "missing_ranges": [],
        "shards": 4,
        "initialize_found": found,
        "initialize": initialize,
        "rpc_requests": 20,
        "rpc_routes": ["solidrpc_keyless_public"],
    }


def validate(row):
    return validate_pools_trade_lbp_pool_init_search(
        row,
        expected_token=TOKEN,
        expected_pool_id=POOL_ID,
        expected_from_block=100,
        expected_to_block=200,
    )


def test_validate_lbp_pool_init_search_accepts_proven_absence():
    row = validate(report())
    assert row["initialize_found"] is False
    assert row["initialize"] is None
    assert row["continuous"] is True


def test_validate_lbp_pool_init_search_accepts_exact_initialize():
    row = validate(report(found=True))
    assert row["initialize_found"] is True
    assert row["initialize"]["pool_id"] == POOL_ID
    assert row["initialize"]["block_number"] == 150


def test_validate_lbp_pool_init_search_rejects_gap():
    data = report()
    data["missing_ranges"] = [[150, 160]]
    with pytest.raises(ValueError, match="missing ranges"):
        validate(data)


def test_validate_lbp_pool_init_search_rejects_poolkey_drift():
    data = report(found=True)
    data["initialize"]["fee"] = 3000
    with pytest.raises(ValueError, match="does not derive PoolId"):
        validate(data)


def test_validate_lbp_pool_init_search_rejects_flag_row_mismatch():
    data = report()
    data["initialize"] = {
        "pool_id": POOL_ID,
    }
    with pytest.raises(ValueError, match="absence contains"):
        validate(data)
