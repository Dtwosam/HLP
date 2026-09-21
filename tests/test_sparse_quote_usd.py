from dataclasses import dataclass
from types import SimpleNamespace

from hlp.data.types import RawLog
from hlp.data import sparse_quote_usd


TOKEN = "0x" + "11" * 20
QUOTE = "0x" + "22" * 20
POOL = "0x" + "33" * 20


@dataclass(frozen=True)
class Target:
    block_number: int
    transaction_index: int
    log_index: int


class FakeRpc:
    def __init__(self, logs):
        self.logs = logs
        self.log_calls = []

    def get_logs(self, lo, hi, *, address=None, topics=None):
        self.log_calls.append((lo, hi, address, topics))
        return [
            row
            for row in self.logs
            if lo <= row.block_number <= hi
        ]


def raw_swap(block, tx, log_index):
    return RawLog(
        chain_id=4663,
        block_number=block,
        block_hash="0x" + "aa" * 32,
        transaction_hash="0x" + f"{tx:064x}",
        transaction_index=tx,
        log_index=log_index,
        address=POOL,
        topics=("0x" + "00" * 32,),
        data="0x",
        removed=False,
    )


def patch_context(monkeypatch):
    monkeypatch.setattr(
        sparse_quote_usd,
        "read_sparse_v3_quote_context",
        lambda *args, **kwargs: sparse_quote_usd.SparseV3QuoteContext(
            token=TOKEN,
            quote_token=QUOTE,
            pool=POOL,
            token_is_token0=True,
            token_decimals=18,
            quote_decimals=18,
        ),
    )
    monkeypatch.setattr(
        sparse_quote_usd,
        "read_v3_slot0",
        lambda *args, **kwargs: SimpleNamespace(sqrt_price_x96=100),
    )
    monkeypatch.setattr(
        sparse_quote_usd,
        "_quote_from_sqrt_price",
        lambda sqrt_price_x96, context: {
            100: 10,
            200: 20,
            300: 30,
        }[sqrt_price_x96],
    )


def test_sparse_quote_sampling_respects_same_block_order(monkeypatch):
    patch_context(monkeypatch)
    logs = [
        raw_swap(2_100, 2, 0),
        raw_swap(2_100, 8, 0),
    ]
    decoded = {
        logs[0].transaction_hash: SimpleNamespace(
            block_number=2_100,
            transaction_index=2,
            log_index=0,
            sqrt_price_x96=200,
        ),
        logs[1].transaction_hash: SimpleNamespace(
            block_number=2_100,
            transaction_index=8,
            log_index=0,
            sqrt_price_x96=300,
        ),
    }
    monkeypatch.setattr(
        sparse_quote_usd,
        "decode_v3_swap",
        lambda row: decoded[row.transaction_hash],
    )
    rpc = FakeRpc(logs)

    rows = sparse_quote_usd.build_sparse_v3_quote_points(
        rpc,
        [
            Target(2_100, 1, 0),
            Target(2_100, 5, 0),
            Target(2_100, 9, 0),
        ],
        token=TOKEN,
        quote_token=QUOTE,
        pool=POOL,
        window_size=2_000,
    )

    assert [row["quote_per_token"] for row in rows] == [
        "10",
        "20",
        "30",
    ]
    assert len(rpc.log_calls) == 1
    assert rpc.log_calls[0][:2] == (2_000, 2_100)


def test_sparse_quote_sampling_skips_windows_without_targets(monkeypatch):
    patch_context(monkeypatch)
    monkeypatch.setattr(
        sparse_quote_usd,
        "decode_v3_swap",
        lambda row: None,
    )
    rpc = FakeRpc([])

    rows = sparse_quote_usd.build_sparse_v3_quote_points(
        rpc,
        [
            Target(2_100, 1, 0),
            Target(8_100, 1, 0),
        ],
        token=TOKEN,
        quote_token=QUOTE,
        pool=POOL,
        window_size=2_000,
    )

    assert len(rows) == 2
    assert [(lo, hi) for lo, hi, *_ in rpc.log_calls] == [
        (2_000, 2_100),
        (8_000, 8_100),
    ]
