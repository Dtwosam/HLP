"""Generic transaction-initiator enrichment for causal trade research."""

from __future__ import annotations

from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.rpc import RpcClient


def fetch_transaction_identity_rows(
    rpc: RpcClient,
    transaction_hashes: Iterable[str],
    *,
    batch_size: int = 100,
    min_batch_size: int = 1,
) -> list[dict]:
    """Fetch immutable tx.from/to identity fields for exact transaction hashes."""

    hashes = sorted({str(value).lower() for value in transaction_hashes})
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
        observed = str(row["hash"]).lower()
        if observed != expected:
            raise ValueError(
                f"transaction identity mismatch: {observed} != {expected}"
            )
        sender = normalize_address(str(row["from"]))
        to = row.get("to")
        data = row.get("input") or "0x"
        output.append({
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
            "to": None if to is None else normalize_address(str(to)),
            "value_raw": int(row.get("value") or "0x0", 16),
            "input_selector": (
                data[:10].lower() if len(data) >= 10 else data.lower()
            ),
            "transaction_type": (
                None
                if row.get("type") is None
                else int(row["type"], 16)
            ),
        })
    return output


def attach_transaction_identities(
    rows: Iterable[Mapping[str, object]],
    transaction_rows: Iterable[Mapping[str, object]],
    *,
    label: str = "event",
) -> list[dict]:
    """Attach tx initiator fields and reject block/index identity drift."""

    transactions = {}
    for raw in transaction_rows:
        row = dict(raw)
        transaction_hash = str(row.get("transaction_hash") or "").lower()
        if not transaction_hash:
            raise ValueError(f"{label} transaction identity hash is empty")
        if transaction_hash in transactions:
            raise ValueError(
                f"{label} transaction identity repeats: {transaction_hash}"
            )
        transactions[transaction_hash] = row

    output = []
    for source in rows:
        row = dict(source)
        transaction_hash = str(
            row.get("transaction_hash") or ""
        ).lower()
        tx = transactions.get(transaction_hash)
        if tx is None:
            raise KeyError(
                f"missing transaction identity for {label} "
                f"{transaction_hash}"
            )
        row_block = int(row.get("block_number", -1))
        tx_block = tx.get("block_number")
        if tx_block is not None and row_block != int(tx_block):
            raise ValueError(
                f"{label}/transaction block mismatch for "
                f"{transaction_hash}"
            )
        row_index = row.get("transaction_index")
        tx_index = tx.get("transaction_index")
        if (
            row_index is not None
            and tx_index is not None
            and int(row_index) != int(tx_index)
        ):
            raise ValueError(
                f"{label}/transaction index mismatch for "
                f"{transaction_hash}"
            )
        row["initiator"] = normalize_address(str(tx["initiator"]))
        row["transaction_to"] = (
            None
            if tx.get("to") is None
            else normalize_address(str(tx["to"]))
        )
        row["transaction_value_raw"] = int(tx.get("value_raw") or 0)
        row["input_selector"] = str(
            tx.get("input_selector") or "0x"
        ).lower()
        row["transaction_type"] = (
            None
            if tx.get("transaction_type") is None
            else int(tx["transaction_type"])
        )
        output.append(row)

    output.sort(
        key=lambda row: (
            int(row["block_number"]),
            -1
            if row.get("transaction_index") is None
            else int(row["transaction_index"]),
            int(row["log_index"]),
            str(row.get("token") or ""),
            str(row.get("transaction_hash") or ""),
        )
    )
    return output
