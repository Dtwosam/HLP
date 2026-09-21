import pytest

from hlp.data.direct_markets import (
    attribute_direct_market_origins,
    build_v3_direct_market_registry,
    build_v4_direct_market_registry,
    select_v3_direct_market_candidates,
    select_v4_direct_market_candidates,
    summarize_direct_market_registry,
)
from hlp.data.types import V3PoolCreated, V3PoolInitialized, V4PoolInitialized
from hlp.protocols.erc20 import Erc20StaticState


TOKEN = "0x" + "11" * 20
QUOTE = "0x" + "22" * 20
OTHER = "0x" + "33" * 20
FACTORY = "0x" + "44" * 20
POOL = "0x" + "55" * 20
MANAGER = "0x" + "66" * 20
HOOK = "0x" + "00" * 20
POOL_ID = "0x" + "aa" * 32


def state(token=TOKEN, block=20):
    return Erc20StaticState(
        token=token,
        block_number=block,
        decimals=18,
        total_supply=1_000_000 * 10**18,
    )


def v3_created(token0=TOKEN, token1=QUOTE):
    return V3PoolCreated(
        factory=FACTORY,
        token0=token0,
        token1=token1,
        fee=3000,
        tick_spacing=60,
        pool=POOL,
        block_number=10,
        transaction_hash="0x" + "01" * 32,
        transaction_index=1,
        log_index=2,
    )


def v3_init():
    return V3PoolInitialized(
        pool=POOL,
        sqrt_price_x96=2**96,
        tick=0,
        block_number=20,
        transaction_hash="0x" + "02" * 32,
        transaction_index=2,
        log_index=3,
    )


def v4_init(currency0=TOKEN, currency1=QUOTE):
    return V4PoolInitialized(
        pool_manager=MANAGER,
        pool_id=POOL_ID,
        currency0=currency0,
        currency1=currency1,
        fee=3000,
        tick_spacing=60,
        hooks=HOOK,
        sqrt_price_x96=2**96,
        tick=0,
        block_number=20,
        transaction_hash="0x" + "03" * 32,
        transaction_index=2,
        log_index=3,
    )



def test_v3_candidate_filter_requires_exactly_one_supported_quote_side():
    rows = select_v3_direct_market_candidates(
        [
            v3_created(),
            V3PoolCreated(
                factory=FACTORY,
                token0=QUOTE,
                token1=OTHER,
                fee=500,
                tick_spacing=10,
                pool="0x" + "77" * 20,
                block_number=11,
                transaction_hash="0x" + "04" * 32,
                transaction_index=1,
                log_index=4,
            ),
        ],
        factory=FACTORY,
        quote_decimals={QUOTE: 18, OTHER: 6},
    )

    assert len(rows) == 1
    assert rows[0]["pool"] == POOL
    assert rows[0]["token"] == TOKEN
    assert rows[0]["quote_token"] == QUOTE
    assert rows[0]["quote_decimals"] == 18


def test_v4_candidate_filter_exposes_exact_state_read_coordinates():
    rows = select_v4_direct_market_candidates(
        [v4_init()],
        pool_manager=MANAGER,
        quote_decimals={QUOTE: 18},
    )

    assert rows == [{
        "token": TOKEN,
        "quote_token": QUOTE,
        "quote_decimals": 18,
        "pool_id": POOL_ID,
        "pool_manager": MANAGER,
        "currency0": TOKEN,
        "currency1": QUOTE,
        "fee": 3000,
        "tick_spacing": 60,
        "hooks": HOOK,
        "initialize_block": 20,
        "initialize_transaction_hash": "0x" + "03" * 32,
        "initialize_transaction_index": 2,
        "initialize_log_index": 3,
        "initial_sqrt_price_x96": 2**96,
        "initial_tick": 0,
    }]


def test_v4_candidate_filter_skips_quote_quote_without_state_reads():
    assert select_v4_direct_market_candidates(
        [v4_init(QUOTE, OTHER)],
        pool_manager=MANAGER,
        quote_decimals={QUOTE: 18, OTHER: 6},
    ) == []


def test_v3_discovers_exactly_one_supported_quote_side():
    rows = build_v3_direct_market_registry(
        [v3_created()],
        [v3_init()],
        [state()],
        source_id="direct_uniswap_v3",
        venue="uniswap_v3",
        factory=FACTORY,
        quote_decimals={QUOTE: 18},
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["token"] == TOKEN
    assert row["quote_token"] == QUOTE
    assert row["supply_raw"] == 1_000_000 * 10**18
    assert row["state_block"] == row["initialize_block"] == 20
    assert row["origin_classification"] == "unresolved"


def test_v3_skips_quote_quote_and_unpriceable_pairs():
    quote2 = OTHER
    assert build_v3_direct_market_registry(
        [v3_created(QUOTE, quote2)],
        [v3_init()],
        [],
        source_id="direct_uniswap_v3",
        venue="uniswap_v3",
        factory=FACTORY,
        quote_decimals={QUOTE: 18, quote2: 6},
    ) == []

    assert build_v3_direct_market_registry(
        [v3_created(TOKEN, OTHER)],
        [v3_init()],
        [],
        source_id="direct_uniswap_v3",
        venue="uniswap_v3",
        factory=FACTORY,
        quote_decimals={QUOTE: 18},
    ) == []


def test_v3_requires_exact_initialize_block_supply():
    with pytest.raises(KeyError, match="exact-block ERC20 state"):
        build_v3_direct_market_registry(
            [v3_created()],
            [v3_init()],
            [state(block=21)],
            source_id="direct_uniswap_v3",
            venue="uniswap_v3",
            factory=FACTORY,
            quote_decimals={QUOTE: 18},
        )


def test_v4_discovers_priceable_poolkey_without_claiming_launch_origin():
    rows = build_v4_direct_market_registry(
        [v4_init()],
        [state()],
        source_id="direct_uniswap_v4",
        venue="uniswap_v4",
        pool_manager=MANAGER,
        quote_decimals={QUOTE: 18},
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["pool_id"] == POOL_ID
    assert row["currency0"] == TOKEN
    assert row["currency1"] == QUOTE
    assert row["token"] == TOKEN
    assert row["origin_classification"] == "unresolved"


def test_v4_duplicate_initialize_fails_closed():
    with pytest.raises(ValueError, match="multiple V4 Initialize"):
        build_v4_direct_market_registry(
            [v4_init(), v4_init()],
            [state()],
            source_id="direct_uniswap_v4",
            venue="uniswap_v4",
            pool_manager=MANAGER,
            quote_decimals={QUOTE: 18},
        )


def test_discovery_summary_keeps_canonical_selection_open():
    rows = build_v4_direct_market_registry(
        [v4_init()],
        [state()],
        source_id="direct_uniswap_v4",
        venue="uniswap_v4",
        pool_manager=MANAGER,
        quote_decimals={QUOTE: 18},
    )
    report = summarize_direct_market_registry(rows)

    assert report["markets"] == 1
    assert report["tokens"] == 1
    assert report["unresolved_origin_markets"] == 1
    assert report["canonical_market_selection_complete"] is False



def test_market_origin_attribution_matches_exact_token_address_only():
    rows = build_v4_direct_market_registry(
        [v4_init()],
        [state()],
        source_id="direct_uniswap_v4",
        venue="uniswap_v4",
        pool_manager=MANAGER,
        quote_decimals={QUOTE: 18},
    )
    attributed = attribute_direct_market_origins(
        rows,
        {
            "pons_v2": [{"token": TOKEN}],
            "noxa": [{"token": OTHER}],
        },
    )

    row = attributed[0]
    assert row["origin_classification"] == "known_launch_source"
    assert row["origin_attribution_complete"] is True
    assert row["launch_source_ids"] == ["pons_v2"]


def test_unmatched_market_origin_stays_unattributed_not_direct_by_assumption():
    rows = build_v4_direct_market_registry(
        [v4_init()],
        [state()],
        source_id="direct_uniswap_v4",
        venue="uniswap_v4",
        pool_manager=MANAGER,
        quote_decimals={QUOTE: 18},
    )
    attributed = attribute_direct_market_origins(
        rows,
        {"pons_v2": [{"token": OTHER}]},
    )

    row = attributed[0]
    assert row["origin_classification"] == "unattributed"
    assert row["origin_attribution_complete"] is False
    assert row["launch_source_ids"] == []


def test_origin_registry_duplicate_token_fails_closed():
    rows = build_v4_direct_market_registry(
        [v4_init()],
        [state()],
        source_id="direct_uniswap_v4",
        venue="uniswap_v4",
        pool_manager=MANAGER,
        quote_decimals={QUOTE: 18},
    )

    with pytest.raises(ValueError, match="repeats token"):
        attribute_direct_market_origins(
            rows,
            {
                "pons_v2": [
                    {"token": TOKEN},
                    {"token": TOKEN},
                ]
            },
        )
