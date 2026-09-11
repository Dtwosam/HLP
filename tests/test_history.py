from dataclasses import dataclass

from hlp.data.history import decode_tape, filter_by_addresses, iter_event_tape
from hlp.data.types import RawLog


TOPIC = "0x" + "11" * 32


class FakeRpc:
    def iter_logs_chunked(self, from_block, to_block, **kwargs):
        assert from_block == 10
        assert to_block == 20
        assert kwargs["topics"] == [TOPIC]
        yield RawLog(
            chain_id=4663,
            block_number=12,
            block_hash="0x" + "aa" * 32,
            transaction_hash="0x" + "bb" * 32,
            transaction_index=0,
            log_index=0,
            address="0x" + "22" * 20,
            topics=(TOPIC,),
            data="0x",
            removed=False,
        )


@dataclass
class Row:
    pool: str


def test_shared_event_tape_uses_one_event_family_query():
    rows = list(
        iter_event_tape(
            FakeRpc(),
            from_block=10,
            to_block=20,
            topic0=TOPIC,
            chunk_size=100,
        )
    )
    assert len(rows) == 1


def test_decode_and_local_address_filter():
    raw = [
        RawLog(
            chain_id=4663,
            block_number=1,
            block_hash=None,
            transaction_hash="0x" + "aa" * 32,
            transaction_index=0,
            log_index=0,
            address="0x" + "33" * 20,
            topics=(TOPIC,),
            data="0x",
            removed=False,
        )
    ]
    decoded = decode_tape(raw, lambda row: Row(pool=row.address))
    assert list(
        filter_by_addresses(
            decoded,
            {"0x" + "33" * 20},
            attribute="pool",
        )
    ) == [Row(pool="0x" + "33" * 20)]
