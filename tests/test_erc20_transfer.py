from hlp.data.types import RawLog
from hlp.protocols.erc20 import TRANSFER_TOPIC, decode_erc20_transfer


TOKEN = "0x" + "11" * 20
FROM = "0x" + "22" * 20
TO = "0x" + "33" * 20


def topic_addr(address: str) -> str:
    return "0x" + address.removeprefix("0x").rjust(64, "0")


def test_decode_erc20_transfer():
    log = RawLog(
        chain_id=4663,
        block_number=10,
        block_hash=None,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=1,
        log_index=2,
        address=TOKEN,
        topics=(TRANSFER_TOPIC, topic_addr(FROM), topic_addr(TO)),
        data="0x" + f"{123:064x}",
        removed=False,
    )
    row = decode_erc20_transfer(log)
    assert row.token == TOKEN
    assert row.from_address == FROM
    assert row.to_address == TO
    assert row.value_raw == 123
