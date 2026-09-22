"""Phase-3 adapters from source-normalized trades into the canonical trade schema."""

from __future__ import annotations

from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase3_trade_features import (
    PHASE3_CANONICAL_TRADE_VERSION,
    validate_phase3_canonical_trade_row,
)


PHASE3_PONS_TRADE_ADAPTER_VERSION = "phase3-pons-trade-adapter-v1"


def _event_key(row: Mapping[str, object]) -> tuple[int, int, int]:
    block = int(row.get("block_number", -1))
    raw_tx = row.get("transaction_index")
    tx = -1 if raw_tx is None else int(raw_tx)
    log = int(row.get("log_index", -1))
    if block < 0 or tx < -1 or log < 0:
        raise ValueError("Pons Phase-3 trade event position is invalid")
    return block, tx, log


def adapt_pons_trades_to_phase3(
    rows: Iterable[Mapping[str, object]],
) -> list[dict]:
    """Strip Pons-normalized trades to the minimal source-agnostic trade tape."""

    output = []
    seen = set()
    for raw in rows:
        row = dict(raw)
        version = str(row.get("pons_version") or "").lower()
        if version not in {"v1", "v2"}:
            raise ValueError(
                f"unsupported Pons Phase-3 trade version: {version}"
            )
        source_id = "pons_v1" if version == "v1" else "pons_v2"
        token = normalize_address(str(row.get("token") or ""))
        initiator = normalize_address(str(row.get("initiator") or ""))
        event = _event_key(row)
        identity = (token, *event)
        if identity in seen:
            raise ValueError(
                f"Pons Phase-3 trade repeats token event: {identity}"
            )
        seen.add(identity)
        transaction_hash = str(
            row.get("transaction_hash") or ""
        ).lower()
        if not transaction_hash.startswith("0x") or len(
            transaction_hash
        ) != 66:
            raise ValueError(
                "Pons Phase-3 trade transaction hash is invalid"
            )
        token_amount_raw = int(row.get("token_amount_raw", 0))
        quote_amount_raw = int(row.get("quote_amount_raw", 0))
        if token_amount_raw <= 0 or quote_amount_raw <= 0:
            raise ValueError(
                "Pons Phase-3 trade amounts must be positive"
            )

        canonical = {
            "version": PHASE3_CANONICAL_TRADE_VERSION,
            "adapter_version": PHASE3_PONS_TRADE_ADAPTER_VERSION,
            "token": token,
            "source_id": source_id,
            "venue": "pons",
            "phase": str(row.get("phase") or ""),
            "side": str(row.get("side") or ""),
            "initiator": initiator,
            "transaction_hash": transaction_hash,
            "block_number": event[0],
            "block_timestamp": (
                None
                if row.get("block_timestamp") is None
                else int(row["block_timestamp"])
            ),
            "transaction_index": (
                None if event[1] == -1 else event[1]
            ),
            "log_index": event[2],
            "token_amount_raw": token_amount_raw,
            "quote_amount_raw": quote_amount_raw,
            "quote_token": normalize_address(
                str(row.get("quote_token") or "")
            ),
            "canonical_phase3_trade": True,
            "outcome_derived": False,
        }
        output.append(
            validate_phase3_canonical_trade_row(canonical)
        )

    output.sort(
        key=lambda row: (
            *_event_key(row),
            row["token"],
            row["source_id"],
        )
    )
    return output
