from hlp.data.pons_transactions import (
    attach_pons_transaction_identities,
    fetch_transaction_identity_rows,
)


HASH = "0x" + "11" * 32
SENDER = "0x" + "22" * 20
TO = "0x" + "33" * 20


class FakeRpc:
    def get_transactions_batched(
        self,
        transaction_hashes,
        *,
        batch_size=100,
        min_batch_size=1,
    ):
        assert transaction_hashes == [HASH]
        return [{
            "hash": HASH,
            "from": SENDER,
            "to": TO,
            "blockNumber": hex(10),
            "transactionIndex": hex(2),
            "value": hex(123),
            "input": "0x12345678deadbeef",
            "type": hex(2),
        }]


def test_fetch_and_attach_transaction_initiator():
    tx_rows = fetch_transaction_identity_rows(FakeRpc(), [HASH, HASH])
    assert len(tx_rows) == 1
    assert tx_rows[0]["initiator"] == SENDER
    assert tx_rows[0]["input_selector"] == "0x12345678"

    points = [{
        "token": "0x" + "44" * 20,
        "block_number": 10,
        "transaction_hash": HASH,
        "transaction_index": 2,
        "log_index": 5,
    }]
    enriched = attach_pons_transaction_identities(points, tx_rows)
    assert enriched[0]["initiator"] == SENDER
    assert enriched[0]["transaction_to"] == TO
    assert enriched[0]["transaction_value_raw"] == 123
