from decimal import Decimal

from hlp.config import ROBINHOOD_WETH
from hlp.data.quote_usd import QuoteUsdTimeline


STOCK = "0x" + "11" * 20


def test_timeline_respects_same_block_order_for_stock_and_weth():
    timeline = QuoteUsdTimeline(
        initial_weth_usd=Decimal("1900"),
        initial_quote_usd={STOCK: Decimal("200")},
        weth_anchor_points=[
            {
                "block_number": 10,
                "transaction_index": 2,
                "log_index": 0,
                "quote_per_token": "1910",
            }
        ],
        oracle_updates=[
            {
                "quote_token": STOCK,
                "block_number": 10,
                "transaction_index": 3,
                "log_index": 0,
                "usd_price": "205",
            }
        ],
    )

    timeline.advance_to((10, 1, 0))
    assert timeline.price(ROBINHOOD_WETH) == Decimal("1900")
    assert timeline.price(STOCK) == Decimal("200")

    timeline.advance_to((10, 2, 1))
    assert timeline.price(ROBINHOOD_WETH) == Decimal("1910")
    assert timeline.price(STOCK) == Decimal("200")

    timeline.advance_to((10, 4, 0))
    assert timeline.price(STOCK) == Decimal("205")
    assert timeline.pricing_status(STOCK) == "priced_chainlink_stock_token"



def test_timeline_does_not_materialize_full_sources():
    consumed = {"anchor": 0, "oracle": 0}

    def anchors():
        for block in (10, 20, 30):
            consumed["anchor"] += 1
            yield {
                "block_number": block,
                "transaction_index": 1,
                "log_index": 0,
                "quote_per_token": str(1900 + block),
            }

    def oracles():
        for block in (15, 25, 35):
            consumed["oracle"] += 1
            yield {
                "quote_token": STOCK,
                "block_number": block,
                "transaction_index": 1,
                "log_index": 0,
                "usd_price": str(200 + block),
            }

    timeline = QuoteUsdTimeline(
        initial_weth_usd=Decimal("1900"),
        initial_quote_usd={STOCK: Decimal("200")},
        weth_anchor_points=anchors(),
        oracle_updates=oracles(),
    )

    # Lazy merge seeds at most one row from each source.
    assert consumed == {"anchor": 1, "oracle": 1}

    timeline.advance_to((10, 1, 0))
    assert timeline.price(ROBINHOOD_WETH) == Decimal("1910")
    assert consumed["anchor"] <= 2
    assert consumed["oracle"] == 1


def test_timeline_rejects_out_of_order_source_lazily():
    timeline = QuoteUsdTimeline(
        initial_weth_usd=Decimal("1900"),
        weth_anchor_points=[
            {
                "block_number": 20,
                "transaction_index": 1,
                "log_index": 0,
                "quote_per_token": "1920",
            },
            {
                "block_number": 10,
                "transaction_index": 1,
                "log_index": 0,
                "quote_per_token": "1910",
            },
        ],
    )
    try:
        timeline.advance_to((20, 1, 0))
    except ValueError as exc:
        assert "not chronological" in str(exc)
    else:
        raise AssertionError("out-of-order USD source must fail closed")



def test_prepare_quote_usd_inputs_activates_staggered_state_causally():
    from hlp.data.quote_usd import prepare_quote_usd_inputs

    initial, updates = prepare_quote_usd_inputs(
        [{
            "quote_token": STOCK,
            "activation_block": 100,
            "block_number": 99,
            "usd_price": "200",
        }],
        [[]],
    )
    assert initial == {}

    timeline = QuoteUsdTimeline(
        initial_weth_usd=Decimal("1900"),
        initial_quote_usd=initial,
        oracle_updates=updates,
    )
    timeline.advance_to((99, 999, 999))
    assert timeline.price(STOCK) is None
    timeline.advance_to((100, -1, -1))
    assert timeline.price(STOCK) == Decimal("200")


def test_prepare_quote_usd_inputs_keeps_true_pre_window_state_active():
    from hlp.data.quote_usd import prepare_quote_usd_inputs

    initial, updates = prepare_quote_usd_inputs(
        [{"quote_token": STOCK, "block_number": 9, "usd_price": "200"}],
        [[]],
    )
    assert initial == {STOCK: Decimal("200")}
    assert list(updates) == []


def test_prepare_quote_usd_inputs_rejects_duplicate_source_state():
    from hlp.data.quote_usd import prepare_quote_usd_inputs

    try:
        prepare_quote_usd_inputs(
            [
                {
                    "quote_token": STOCK,
                    "activation_block": 10,
                    "usd_price": "200",
                },
                {
                    "quote_token": STOCK,
                    "activation_block": 20,
                    "usd_price": "210",
                },
            ],
            [],
        )
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("duplicate quote source state must fail closed")



def test_timeline_preserves_chainlink_crypto_status():
    timeline = QuoteUsdTimeline(
        initial_weth_usd=Decimal("1900"),
        oracle_updates=[{
            "quote_token": STOCK,
            "pricing_status": "priced_chainlink_crypto_token",
            "block_number": 10,
            "transaction_index": 1,
            "log_index": 0,
            "usd_price": "100000",
        }],
    )
    timeline.advance_to((10, 1, 0))
    assert timeline.pricing_status(STOCK) == "priced_chainlink_crypto_token"


def test_timeline_marks_v3_and_v4_fallback_sources():
    v3 = "0x" + "22" * 20
    v4 = "0x" + "33" * 20
    timeline = QuoteUsdTimeline(
        initial_weth_usd=Decimal("1900"),
        oracle_updates=[
            {
                "quote_token": v3,
                "pricing_source": "uniswap_v3_direct_usdg",
                "block_number": 10,
                "transaction_index": 1,
                "log_index": 0,
                "usd_price": "200",
            },
            {
                "quote_token": v4,
                "pricing_source": "uniswap_v4_direct_usdg",
                "block_number": 11,
                "transaction_index": 1,
                "log_index": 0,
                "usd_price": "210",
            },
        ],
    )
    timeline.advance_to((11, 1, 0))
    assert timeline.pricing_status(v3) == "priced_v3_quote_fallback"
    assert timeline.pricing_status(v4) == "priced_v4_quote_fallback"



def test_merge_quote_usd_tapes_merges_disjoint_sources():
    from hlp.data.quote_usd import merge_quote_usd_tapes

    v3 = "0x" + "22" * 20
    v4 = "0x" + "33" * 20
    states, updates = merge_quote_usd_tapes([
        (
            [{
                "quote_token": v3,
                "activation_block": 10,
                "block_number": 9,
                "usd_price": "200",
            }],
            [{
                "quote_token": v3,
                "block_number": 20,
                "transaction_index": 1,
                "log_index": 0,
                "usd_price": "201",
            }],
        ),
        (
            [],
            [{
                "quote_token": v4,
                "block_number": 15,
                "transaction_index": 1,
                "log_index": 0,
                "usd_price": "300",
            }],
        ),
    ])
    assert [row["quote_token"] for row in states] == [v3]
    assert [row["quote_token"] for row in updates] == [v4, v3]


def test_merge_quote_usd_tapes_rejects_source_overlap():
    from hlp.data.quote_usd import merge_quote_usd_tapes

    try:
        _, updates = merge_quote_usd_tapes([
            (
                [{
                    "quote_token": STOCK,
                    "activation_block": 10,
                    "block_number": 9,
                    "usd_price": "200",
                }],
                [],
            ),
            (
                [],
                [{
                    "quote_token": STOCK,
                    "block_number": 20,
                    "transaction_index": 1,
                    "log_index": 0,
                    "usd_price": "201",
                }],
            ),
        ])
        list(updates)
    except ValueError as exc:
        assert "multiple sources" in str(exc)
    else:
        raise AssertionError("overlapping quote/USD sources must fail closed")
