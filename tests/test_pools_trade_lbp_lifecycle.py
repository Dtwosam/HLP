import pytest

from hlp.data.pools_trade_lbp import (
    merge_pools_trade_lbp_market_cap_summaries,
)


TOKEN = "0x" + "11" * 20
POOL_ID = "0x" + "22" * 32


def registry():
    return [{
        "token": TOKEN,
        "initializer": "0x" + "33" * 20,
        "pool_id": POOL_ID,
        "quote_token": "0x" + "00" * 20,
        "initializer_block": 100,
        "migration_block": 200,
    }]


def cca(*, max_value="90000", crossed=False, priced=2, total=2):
    return [{
        "token": TOKEN,
        "price_points": total,
        "priced_points": priced,
        "pricing_statuses": ["priced_weth_usdg"],
        "max_market_cap_proxy_usd": max_value,
        "max_market_cap_block": 150,
        "crossed_100k": crossed,
    }]


def v4(*, max_value="150000", crossed=True):
    return [{
        "token": TOKEN,
        "price_points": 3,
        "priced_points": 3,
        "max_market_cap_proxy_usd": max_value,
        "max_market_cap_block": 250,
        "crossed_100k": crossed,
    }]


def test_merge_lbp_lifecycle_uses_v4_max_when_larger():
    rows = merge_pools_trade_lbp_market_cap_summaries(
        registry(),
        cca_summary=cca(),
        v4_summary=v4(),
    )
    assert rows[0]["price_points"] == 5
    assert rows[0]["priced_points"] == 5
    assert rows[0]["eligibility_status"] == "eligible"
    assert rows[0]["max_market_cap_proxy_usd"] == "150000"
    assert rows[0]["max_market_cap_phase"] == "v4"
    assert rows[0]["has_v4_price_points"] is True


def test_merge_lbp_lifecycle_allows_failed_non_migrating_auction():
    rows = merge_pools_trade_lbp_market_cap_summaries(
        registry(),
        cca_summary=cca(),
    )
    assert rows[0]["has_v4_price_points"] is False
    assert rows[0]["eligibility_status"] == "ineligible"
    assert rows[0]["max_market_cap_phase"] == "cca"


def test_merge_lbp_lifecycle_preserves_unknown_when_unpriced():
    rows = merge_pools_trade_lbp_market_cap_summaries(
        registry(),
        cca_summary=cca(max_value="90000", priced=1, total=2),
    )
    assert rows[0]["unpriced_points"] == 1
    assert rows[0]["eligibility_status"] == "unknown"


def test_merge_lbp_lifecycle_requires_cca_for_every_registry_token():
    with pytest.raises(ValueError, match="cover registry exactly"):
        merge_pools_trade_lbp_market_cap_summaries(
            registry(),
            cca_summary=[],
        )


def test_merge_lbp_lifecycle_rejects_v4_outside_registry():
    extra = v4()
    extra[0]["token"] = "0x" + "44" * 20
    with pytest.raises(ValueError, match="outside registry"):
        merge_pools_trade_lbp_market_cap_summaries(
            registry(),
            cca_summary=cca(),
            v4_summary=extra,
        )
