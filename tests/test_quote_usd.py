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
