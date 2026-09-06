from hlp.config import NOXA_LAUNCH_FACTORY
from hlp.data.types import RawLog
from hlp.protocols.noxa import TOKEN_LAUNCHED_TOPIC, decode_noxa_launch


TOKEN = "0x" + "11" * 20
DEPLOYER = "0x" + "22" * 20
DEX = "0x" + "33" * 20
PAIR = "0x" + "44" * 20
POOL = "0x" + "55" * 20


def word(value: int) -> str:
    return f"{value:064x}"


def addr_word(address: str) -> str:
    return address.removeprefix("0x").rjust(64, "0")


def topic_addr(address: str) -> str:
    return "0x" + addr_word(address)


def test_decode_noxa_launch():
    log = RawLog(
        chain_id=4663,
        block_number=123,
        block_hash=None,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=1,
        log_index=2,
        address=NOXA_LAUNCH_FACTORY.lower(),
        topics=(
            TOKEN_LAUNCHED_TOPIC,
            topic_addr(TOKEN),
            topic_addr(DEPLOYER),
            topic_addr(DEX),
        ),
        data=(
            "0x"
            + addr_word(PAIR)
            + addr_word(POOL)
            + word(0)
            + word(0)
            + word(1234)
            + word(5678)
            + word(9)
        ),
        removed=False,
    )
    row = decode_noxa_launch(log)
    assert row.venue == "noxa"
    assert row.token == TOKEN
    assert row.pool == POOL
    assert row.pair_token == PAIR
    assert row.position_id == 1234
    assert row.initial_buy_amount == 9
