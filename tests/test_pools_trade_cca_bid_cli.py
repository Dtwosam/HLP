from argparse import Namespace
import json

from hlp.cli import cmd_rpc_pools_trade_lbp_cca_bid_window
from hlp.data.types import RawLog
from hlp.protocols.pools_trade_lbp import (
    CCA_BID_EXITED_TOPIC,
    CCA_BID_SUBMITTED_TOPIC,
)


AUCTION = "0x" + "11" * 20
TOKEN = "0x" + "22" * 20
QUOTE = "0x" + "33" * 20
OWNER = "0x" + "44" * 20


def topic_uint(value):
    return "0x" + f"{value:064x}"


def data_words(*values):
    return "0x" + "".join(f"{value:064x}" for value in values)


def raw(topic0, bid_id, data, block, log_index):
    return RawLog(
        chain_id=4663,
        block_number=block,
        block_hash=None,
        transaction_hash="0x" + f"{block:064x}",
        transaction_index=0,
        log_index=log_index,
        address=AUCTION,
        topics=(
            topic0,
            topic_uint(bid_id),
            "0x" + "0" * 24 + OWNER.removeprefix("0x"),
        ),
        data=data,
        removed=False,
    )


class FakeRpc:
    requests_made = 1
    response_bytes_received = 100
    route_label = "unit"

    def assert_robinhood(self):
        return None

    def iter_logs_chunked(self, *args, **kwargs):
        return iter([
            raw(
                CCA_BID_SUBMITTED_TOPIC,
                7,
                data_words(10, 1000),
                11,
                1,
            ),
            raw(
                CCA_BID_EXITED_TOPIC,
                7,
                data_words(20, 250),
                12,
                2,
            ),
        ])


def test_cca_bid_window_writes_separate_submission_and_exit_tapes(
    tmp_path,
    monkeypatch,
):
    registry = tmp_path / "registry.jsonl"
    registry.write_text(json.dumps({
        "launch_kind": "crowd_lbp",
        "initializer": AUCTION,
        "token": TOKEN,
        "quote_token": QUOTE,
        "initializer_block": 10,
        "initializer_transaction_index": 0,
        "initializer_log_index": 0,
    }) + "\n")
    submitted = tmp_path / "submitted.jsonl"
    exited = tmp_path / "exited.jsonl"
    monkeypatch.setattr("hlp.cli._archive_rpc", lambda args: FakeRpc())

    rc = cmd_rpc_pools_trade_lbp_cca_bid_window(Namespace(
        registry=str(registry),
        from_block=10,
        to_block=20,
        chunk_size=100,
        min_chunk_size=1,
        submitted_out=str(submitted),
        exited_out=str(exited),
    ))
    assert rc == 0
    submitted_row = json.loads(submitted.read_text())
    exited_row = json.loads(exited.read_text())
    assert submitted_row["owner"] == OWNER
    assert submitted_row["amount_raw"] == 1000
    assert exited_row["tokens_filled_raw"] == 20
    assert exited_row["currency_refunded_raw"] == 250
