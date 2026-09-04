from decimal import Decimal

from hlp.data.reconstruct import attach_quote_usd_anchor, reconstruct_v3_price_points
from hlp.data.types import RawLog
from hlp.protocols.evm import function_selector
from hlp.protocols.state import SLOT0_SELECTOR, TOKEN0_SELECTOR, TOKEN1_SELECTOR
from hlp.protocols.erc20 import DECIMALS_SELECTOR, TOTAL_SUPPLY_SELECTOR
from hlp.protocols.uniswap import V3_SWAP_TOPIC


TOKEN = "0x" + "11" * 20
QUOTE = "0x" + "22" * 20
POOL = "0x" + "33" * 20


def word(value: int) -> str:
    return f"{value:064x}"


def address_word(address: str) -> str:
    return address.removeprefix("0x").rjust(64, "0")


class FakeRpc:
    def eth_call(self, to, data, block="latest"):
        if to.lower() == POOL and data == TOKEN0_SELECTOR:
            return "0x" + address_word(TOKEN)
        if to.lower() == POOL and data == TOKEN1_SELECTOR:
            return "0x" + address_word(QUOTE)
        if to.lower() == TOKEN and data == DECIMALS_SELECTOR:
            return "0x" + word(18)
        if to.lower() == TOKEN and data == TOTAL_SUPPLY_SELECTOR:
            return "0x" + word(1_000_000_000 * 10**18)
        if to.lower() == QUOTE and data == DECIMALS_SELECTOR:
            return "0x" + word(18)
        if to.lower() == QUOTE and data == TOTAL_SUPPLY_SELECTOR:
            return "0x" + word(1)
        raise AssertionError((to, data, block))

    def iter_logs_chunked(self, *args, **kwargs):
        # sqrtPriceX96 = 2**96 => 1 quote token per token when decimals match.
        data = (
            "0x"
            + word(10**18)
            + word((1 << 256) - 2 * 10**18)
            + word(2**96)
            + word(123)
            + word(0)
        )
        yield RawLog(
            chain_id=4663,
            block_number=101,
            block_hash="0x" + "aa" * 32,
            transaction_hash="0x" + "bb" * 32,
            transaction_index=0,
            log_index=1,
            address=POOL,
            topics=(
                V3_SWAP_TOPIC,
                "0x" + address_word("0x" + "44" * 20),
                "0x" + address_word("0x" + "55" * 20),
            ),
            data=data,
            removed=False,
        )


def test_reconstruct_v3_price_points():
    rows = list(
        reconstruct_v3_price_points(
            FakeRpc(),
            token=TOKEN,
            quote_token=QUOTE,
            pool=POOL,
            from_block=100,
            to_block=200,
        )
    )
    assert len(rows) == 1
    row = rows[0]
    assert Decimal(row["quote_per_token"]) == Decimal(1)
    assert Decimal(row["market_cap_quote"]) == Decimal(1_000_000_000)
    assert row["token_is_token0"] is True
    assert row["block_number"] == 101



def test_quote_usd_anchor_respects_within_block_order():
    targets = [
        {
            "block_number": 10,
            "transaction_index": 1,
            "log_index": 5,
            "quote_per_token": "2",
            "market_cap_quote": "200",
        },
        {
            "block_number": 10,
            "transaction_index": 3,
            "log_index": 1,
            "quote_per_token": "3",
            "market_cap_quote": "300",
        },
    ]
    anchors = [
        {
            "block_number": 10,
            "transaction_index": 2,
            "log_index": 0,
            "quote_per_token": "2500",
        }
    ]
    rows = list(
        attach_quote_usd_anchor(
            targets,
            anchors,
            initial_quote_usd=Decimal("2400"),
        )
    )
    # First target occurs before the same-block WETH/USD anchor swap.
    assert Decimal(rows[0]["quote_usd"]) == Decimal("2400")
    assert Decimal(rows[0]["market_cap_proxy_usd"]) == Decimal("480000")
    # Second target occurs after it and may use 2500.
    assert Decimal(rows[1]["quote_usd"]) == Decimal("2500")
    assert Decimal(rows[1]["market_cap_proxy_usd"]) == Decimal("750000")
