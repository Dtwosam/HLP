import pytest

from hlp.data.direct_canonical import (
    DIRECT_CANONICAL_SERIES_VERSION,
    build_frozen_direct_canonical_series,
    iter_frozen_direct_canonical_series,
    summarize_frozen_direct_canonical_series,
)
from hlp.data.direct_selector import (
    DIRECT_SELECTOR_FREEZE_VERSION,
    DIRECT_SELECTOR_VERSION,
)


TOKEN = "0x" + "11" * 20
POOL_A = "0x" + "22" * 20
POOL_B = "0x" + "33" * 20


def selector():
    return {
        "version": DIRECT_SELECTOR_FREEZE_VERSION,
        "selector_version": DIRECT_SELECTOR_VERSION,
        "selection_rule_frozen": True,
        "source_coverage_complete": False,
        "selection_metric": "active_quote_liquidity_usd",
        "tie_break_rule": "stable market_id ascending",
        "state_semantics": "latest already-observed usable market state",
        "canonical_volume_policy": "selected market only",
        "cross_pool_volume_double_counting_allowed": False,
    }


def point(
    market,
    block,
    *,
    mcap,
    depth=None,
    source="direct_uniswap_v3",
    event_type="v3_swap",
):
    return {
        "source_id": source,
        "token": TOKEN,
        "market_id": market,
        "pool": market,
        "block_number": block,
        "transaction_hash": "0x" + f"{block:064x}",
        "transaction_index": 1,
        "log_index": block,
        "event_type": event_type,
        "market_cap_proxy_usd": str(mcap),
        "active_quote_liquidity_usd": (
            None if depth is None else str(depth)
        ),
    }


def test_direct_canonical_single_observed_market_includes_initialize():
    rows = build_frozen_direct_canonical_series(
        [
            point(
                POOL_A,
                1,
                mcap=90000,
                depth=None,
                event_type="v3_initialize",
            ),
            point(POOL_A, 2, mcap=110000, depth=100),
        ],
        selector(),
        expected_tokens=[TOKEN],
    )

    assert len(rows) == 2
    assert rows[0]["selection_reason"] == "only_observed_market"
    assert rows[0]["canonical_price_series"] is True
    assert rows[0]["canonical_volume_eligible"] is True
    assert rows[1]["selected_market_id"] == POOL_A


def test_direct_canonical_uses_liquidity_once_competition_is_observed():
    rows = build_frozen_direct_canonical_series(
        [
            point(
                POOL_A,
                1,
                mcap=90000,
                depth=None,
                event_type="v3_initialize",
            ),
            point(POOL_A, 2, mcap=100000, depth=100),
            point(
                POOL_B,
                3,
                mcap=120000,
                depth=None,
                event_type="v3_initialize",
            ),
            point(POOL_B, 4, mcap=130000, depth=200),
        ],
        selector(),
    )

    assert [row["selected_market_id"] for row in rows] == [
        POOL_A,
        POOL_A,
        POOL_B,
    ]
    assert rows[-1]["leadership_switched"] is True
    assert rows[-1]["canonical_volume_eligible"] is True


def test_direct_canonical_stale_winner_switch_is_synthetic_and_volume_free():
    rows = build_frozen_direct_canonical_series(
        [
            point(
                POOL_A,
                1,
                mcap=90000,
                depth=None,
                event_type="v3_initialize",
            ),
            point(POOL_A, 2, mcap=110000, depth=100),
            point(
                POOL_B,
                3,
                mcap=120000,
                depth=None,
                event_type="v3_initialize",
            ),
            point(POOL_B, 4, mcap=140000, depth=200),
            point(POOL_B, 5, mcap=130000, depth=50),
        ],
        selector(),
    )

    switch = rows[-1]
    assert switch["event_type"] == "selector_switch"
    assert switch["selected_market_id"] == POOL_A
    assert switch["selection_event_market_id"] == POOL_B
    assert switch["block_number"] == 5
    assert switch["selected_state_block_number"] == 2
    assert switch["canonical_volume_eligible"] is False
    assert switch["synthetic_selector_switch"] is True


def test_direct_canonical_summary_is_universe_ready():
    rows = build_frozen_direct_canonical_series(
        [
            point(
                POOL_A,
                1,
                mcap=90000,
                depth=None,
                event_type="v3_initialize",
            ),
            point(POOL_A, 2, mcap=150000, depth=100),
        ],
        selector(),
        expected_tokens=[TOKEN],
    )
    tokens, report = summarize_frozen_direct_canonical_series(rows)

    assert tokens[0]["crossed_100k"] is True
    assert tokens[0]["max_market_cap_proxy_usd"] == "150000"
    assert tokens[0]["pricing_complete"] is True
    assert report["version"] == DIRECT_CANONICAL_SERIES_VERSION
    assert report["selection_rule_frozen"] is True
    assert report["cross_pool_volume_double_counting_allowed"] is False


def test_direct_canonical_requires_exact_expected_token_population():
    with pytest.raises(ValueError, match="token population mismatch"):
        build_frozen_direct_canonical_series(
            [],
            selector(),
            expected_tokens=[TOKEN],
        )


def test_direct_canonical_stream_requires_chronological_input():
    rows = [
        point(POOL_A, 2, mcap=110000, depth=100),
        point(
            POOL_A,
            1,
            mcap=90000,
            depth=None,
            event_type="v3_initialize",
        ),
    ]

    with pytest.raises(ValueError, match="not chronological"):
        list(iter_frozen_direct_canonical_series(
            rows,
            selector(),
        ))

