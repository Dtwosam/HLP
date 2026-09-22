from argparse import Namespace
import json

from hlp.cli import cmd_rpc_transaction_identity_enrich


TX = "0x" + "11" * 32
SENDER = "0x" + "22" * 20
TO = "0x" + "33" * 20
TOKEN = "0x" + "44" * 20


class FakeRpc:
    requests_made = 1
    response_bytes_received = 100
    route_label = "unit"

    def assert_robinhood(self):
        return None

    def get_transactions_batched(
        self,
        hashes,
        *,
        batch_size,
        min_batch_size,
    ):
        assert hashes == [TX]
        return [{
            "hash": TX,
            "from": SENDER,
            "to": TO,
            "input": "0x12345678",
            "value": "0x0",
            "blockNumber": "0xa",
            "transactionIndex": "0x1",
            "type": "0x2",
        }]


def test_generic_transaction_identity_enrichment(
    tmp_path,
    monkeypatch,
):
    events = tmp_path / "events.jsonl"
    events.write_text(json.dumps({
        "token": TOKEN,
        "transaction_hash": TX,
        "block_number": 10,
        "transaction_index": 1,
        "log_index": 2,
    }) + "\n")
    transactions = tmp_path / "transactions.jsonl"
    enriched = tmp_path / "enriched.jsonl"
    monkeypatch.setattr("hlp.cli._archive_rpc", lambda args: FakeRpc())

    rc = cmd_rpc_transaction_identity_enrich(Namespace(
        events=str(events),
        transactions_out=str(transactions),
        out=str(enriched),
        label="unit event",
        batch_size=100,
        min_batch_size=1,
    ))
    assert rc == 0

    tx = json.loads(transactions.read_text())
    row = json.loads(enriched.read_text())
    assert tx["initiator"] == SENDER
    assert row["initiator"] == SENDER
    assert row["transaction_to"] == TO
    assert row["input_selector"] == "0x12345678"
