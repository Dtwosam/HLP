"""Transaction-initiator enrichment for Pons market-path research."""

from __future__ import annotations

from typing import Iterable

from hlp.config import normalize_address
from hlp.data.rpc import RpcClient


def fetch_transaction_identity_rows(
    rpc: RpcClient,
    transaction_hashes: Iterable[str],
    *,
    batch_size: int = 100,
    min_batch_size: int = 1,
) -> list[dict]:
    hashes = sorted({value.lower() for value in transaction_hashes})
    if not hashes:
        return []
    raw_rows = rpc.get_transactions_batched(
        hashes,
        batch_size=batch_size,
        min_batch_size=min_batch_size,
    )
    if len(raw_rows) != len(hashes):
        raise RuntimeError("transaction batch response length mismatch")

    output = []
    for expected, row in zip(hashes, raw_rows):
        observed = row["hash"].lower()
        if observed != expected:
            raise ValueError(
                f"transaction identity mismatch: {observed} != {expected}"
            )
        sender = normalize_address(row["from"])
        to = row.get("to")
        data = row.get("input") or "0x"
        output.append(
            {
                "transaction_hash": observed,
                "block_number": (
                    None
                    if row.get("blockNumber") is None
                    else int(row["blockNumber"], 16)
                ),
                "transaction_index": (
                    None
                    if row.get("transactionIndex") is None
                    else int(row["transactionIndex"], 16)
                ),
                "initiator": sender,
                "to": None if to is None else normalize_address(to),
                "value_raw": int(row.get("value") or "0x0", 16),
                "input_selector": (
                    data[:10].lower() if len(data) >= 10 else data.lower()
                ),
                "transaction_type": (
                    None
                    if row.get("type") is None
                    else int(row["type"], 16)
                ),
            }
        )
    return output


def attach_pons_transaction_identities(
    points: Iterable[dict],
    transaction_rows: Iterable[dict],
) -> list[dict]:
    transactions = {
        row["transaction_hash"].lower(): row
        for row in transaction_rows
    }
    output = []
    for source in points:
        row = dict(source)
        transaction_hash = row["transaction_hash"].lower()
        tx = transactions.get(transaction_hash)
        if tx is None:
            raise KeyError(
                f"missing transaction identity for Pons point {transaction_hash}"
            )
        if (
            tx["block_number"] is not None
            and int(row["block_number"]) != int(tx["block_number"])
        ):
            raise ValueError(
                f"Pons point/transaction block mismatch for {transaction_hash}"
            )
        row["initiator"] = tx["initiator"]
        row["transaction_to"] = tx["to"]
        row["transaction_value_raw"] = tx["value_raw"]
        row["input_selector"] = tx["input_selector"]
        row["transaction_type"] = tx["transaction_type"]
        output.append(row)

    output.sort(
        key=lambda row: (
            row["block_number"],
            -1
            if row.get("transaction_index") is None
            else row["transaction_index"],
            row["log_index"],
            row["token"],
        )
    )
    return output
