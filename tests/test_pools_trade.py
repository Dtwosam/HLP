from hlp.config import (
    POOLS_TRADE_LAUNCHER_CURRENT,
    POOLS_TRADE_INSTANT_STRATEGIES,
)
from hlp.data.types import RawLog
from hlp.protocols.pools_trade import (
    TOKEN_CREATED_TOPIC,
    TOKEN_DISTRIBUTED_TOPIC,
    TOKEN_LAUNCHED_TOPIC,
    decode_pools_trade_token_created,
    decode_pools_trade_token_distributed,
    decode_pools_trade_token_launched,
)


TOKEN = "0x" + "11" * 20
RECIPIENT = "0x" + "22" * 20
QUOTE = "0x" + "33" * 20
POOL_ID = "0x" + "44" * 32


def word(value: int) -> str:
    return f"{value & ((1 << 256) - 1):064x}"


def addr_word(address: str) -> str:
    return address.removeprefix("0x").rjust(64, "0")


def topic_addr(address: str) -> str:
    return "0x" + addr_word(address)


def raw(address, topics, data="0x"):
    return RawLog(
        chain_id=4663,
        block_number=100,
        block_hash=None,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=2,
        log_index=3,
        address=address.lower(),
        topics=tuple(t.lower() for t in topics),
        data=data,
        removed=False,
    )


def test_topics_match_published_signatures():
    assert TOKEN_CREATED_TOPIC == "0x2e2b3f61b70d2d131b2a807371103cc98d51adcaa5e9a8f9c32658ad8426e74e"
    assert TOKEN_DISTRIBUTED_TOPIC == "0x67226bacccef969dab310a9e55dc1cf821363658e433fd330344f5cc00c79ac8"
    assert TOKEN_LAUNCHED_TOPIC == "0x3b3d2bafdcae274a232217e1f80ee4305d3af6aa25c8b14b1681bd68d18042a4"


def test_decode_token_created():
    row = decode_pools_trade_token_created(
        raw(POOLS_TRADE_LAUNCHER_CURRENT, [TOKEN_CREATED_TOPIC, topic_addr(TOKEN)])
    )
    assert row.token == TOKEN


def test_decode_token_launched_pool_key():
    strategy = POOLS_TRADE_INSTANT_STRATEGIES[0]
    data = (
        "0x"
        + addr_word(TOKEN)
        + addr_word(QUOTE)
        + word(2500)
        + word(25)
        + addr_word("0x" + "00" * 20)
    )
    row = decode_pools_trade_token_launched(
        raw(
            strategy,
            [
                TOKEN_LAUNCHED_TOPIC,
                POOL_ID,
                topic_addr(TOKEN),
                topic_addr(RECIPIENT),
            ],
            data,
        )
    )
    assert row.pool_id == POOL_ID
    assert row.token == TOKEN
    assert row.currency0 == TOKEN
    assert row.currency1 == QUOTE
    assert row.tick_spacing == 25



def test_decode_token_distributed():
    strategy = POOLS_TRADE_INSTANT_STRATEGIES[0]
    row = decode_pools_trade_token_distributed(
        raw(
            POOLS_TRADE_LAUNCHER_CURRENT,
            [
                TOKEN_DISTRIBUTED_TOPIC,
                topic_addr(TOKEN),
                topic_addr(strategy),
            ],
            "0x" + word(123456),
        )
    )
    assert row.token == TOKEN
    assert row.strategy == strategy.lower()
    assert row.amount_raw == 123456
