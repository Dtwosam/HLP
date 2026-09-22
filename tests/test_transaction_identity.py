import pytest

from hlp.data.transaction_identity import (
    attach_transaction_identities,
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
        return [{
            "hash": transaction_hashes[0],
            "from": SENDER,
            "to": TO,
            "blockNumber": hex(10),
            "transactionIndex": hex(2),
            "value": hex(123),
            "input": "0x12345678deadbeef",
            "type": hex(2),
        }]


def test_generic_transaction_identity_enrichment():
    tx_rows = fetch_transaction_identity_rows(FakeRpc(), [HASH])
    enriched = attach_transaction_identities(
        [{
            "token": "0x" + "44" * 20,
            "block_number": 10,
            "transaction_hash": HASH,
            "transaction_index": 2,
            "log_index": 5,
        }],
        tx_rows,
        label="swap",
    )
    assert enriched[0]["initiator"] == SENDER
    assert enriched[0]["transaction_to"] == TO
    assert enriched[0]["transaction_value_raw"] == 123
    assert enriched[0]["input_selector"] == "0x12345678"


def test_generic_transaction_identity_rejects_index_drift():
    tx_rows = fetch_transaction_identity_rows(FakeRpc(), [HASH])
    with pytest.raises(ValueError, match="index mismatch"):
        attach_transaction_identities(
            [{
                "block_number": 10,
                "transaction_hash": HASH,
                "transaction_index": 3,
                "log_index": 5,
            }],
            tx_rows,
            label="swap",
        )
