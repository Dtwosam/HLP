from decimal import Decimal

import pytest

from hlp.data.sparse_chainlink_usd import (
    build_sparse_chainlink_usd_points,
)
from hlp.protocols.chainlink import (
    ChainlinkAnswerUpdate,
    ChainlinkRound,
)


QUOTE = "0x" + "11" * 20
FEED = "0x" + "22" * 20
AGGREGATOR = "0x" + "33" * 20


class FakeRpc:
    def __init__(self):
        self.calls = []

    def get_logs(
        self,
        from_block,
        to_block,
        *,
        address=None,
        topics=None,
    ):
        self.calls.append({
            "from_block": from_block,
            "to_block": to_block,
            "address": address,
            "topics": topics,
        })
        return [object()]


def target(txi, logi):
    return {
        "quote_token": QUOTE,
        "block_number": 210,
        "transaction_index": txi,
        "log_index": logi,
    }


def test_sparse_chainlink_respects_same_block_event_order(monkeypatch):
    rpc = FakeRpc()
    aggregator_reads = []

    def fake_aggregator(rpc, feed, *, block):
        aggregator_reads.append((feed, block))
        return AGGREGATOR

    monkeypatch.setattr(
        "hlp.data.sparse_chainlink_usd.read_chainlink_aggregator",
        fake_aggregator,
    )
    monkeypatch.setattr(
        "hlp.data.sparse_chainlink_usd.read_chainlink_latest_round",
        lambda rpc, feed, *, block: ChainlinkRound(
            feed=feed,
            round_id=7,
            answer_raw=100 * 10**8,
            started_at=1,
            updated_at=2,
            answered_in_round=7,
            decimals=8,
            description="Robinhood TEST / USD",
            block_number=block,
        ),
    )
    monkeypatch.setattr(
        "hlp.data.sparse_chainlink_usd.decode_chainlink_answer_updated",
        lambda raw: ChainlinkAnswerUpdate(
            aggregator=AGGREGATOR,
            answer_raw=110 * 10**8,
            round_id=8,
            updated_at=3,
            block_number=210,
            transaction_hash="0x" + "aa" * 32,
            transaction_index=3,
            log_index=0,
        ),
    )

    rows = build_sparse_chainlink_usd_points(
        rpc,
        [target(2, 5), target(4, 1)],
        feed_specs=[{
            "quote_token": QUOTE,
            "symbol": "TEST",
            "feed": FEED,
            "pricing_status": "priced_chainlink_stock_token",
            "directory_name": "Robinhood TEST / USD",
        }],
        window_size=200,
    )

    assert [Decimal(row["usd_price"]) for row in rows] == [
        Decimal("100"),
        Decimal("110"),
    ]
    assert [row["round_id"] for row in rows] == [7, 8]
    assert rows[0]["oracle_updates_applied"] == 0
    assert rows[1]["oracle_updates_applied"] == 1
    assert aggregator_reads == [(FEED, 199), (FEED, 210)]
    assert rpc.calls[0]["from_block"] == 200
    assert rpc.calls[0]["to_block"] == 210
    assert rpc.calls[0]["address"] == AGGREGATOR


def test_sparse_chainlink_rejects_aggregator_change(monkeypatch):
    rpc = FakeRpc()

    monkeypatch.setattr(
        "hlp.data.sparse_chainlink_usd.read_chainlink_aggregator",
        lambda rpc, feed, *, block: (
            AGGREGATOR if block == 199 else "0x" + "44" * 20
        ),
    )
    monkeypatch.setattr(
        "hlp.data.sparse_chainlink_usd.read_chainlink_latest_round",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("state read should follow aggregator stability check")
        ),
    )

    with pytest.raises(RuntimeError, match="aggregator changed"):
        build_sparse_chainlink_usd_points(
            rpc,
            [target(2, 5)],
            feed_specs=[{
                "quote_token": QUOTE,
                "symbol": "TEST",
                "feed": FEED,
            }],
            window_size=200,
        )


def test_sparse_chainlink_rejects_missing_quote_spec():
    with pytest.raises(KeyError, match="missing sparse Chainlink quote spec"):
        build_sparse_chainlink_usd_points(
            FakeRpc(),
            [target(2, 5)],
            feed_specs=[],
        )
