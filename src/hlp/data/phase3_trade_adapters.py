"""Phase-3 adapters from source-normalized trades into the canonical trade schema."""

from __future__ import annotations

from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase2_sources import build_phase2_source_inventory
from hlp.data.phase3_trade_features import (
    PHASE3_CANONICAL_TRADE_VERSION,
    validate_phase3_canonical_trade_row,
)
from hlp.data.transaction_identity import attach_transaction_identities


PHASE3_PONS_TRADE_ADAPTER_VERSION = "phase3-pons-trade-adapter-v1"
PHASE3_AMM_TRADE_ADAPTER_VERSION = "phase3-amm-trade-adapter-v1"


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



def _source_inventory_row(source_id: str, required_phase: str) -> dict:
    rows = {
        str(row["source_id"]): dict(row)
        for row in build_phase2_source_inventory()
    }
    source = rows.get(str(source_id))
    if source is None:
        raise ValueError(
            f"unknown Phase-3 AMM trade source id: {source_id}"
        )
    if required_phase not in set(source.get("market_phases") or []):
        raise ValueError(
            f"{source_id} does not advertise {required_phase}"
        )
    return source


def _market_map(
    market_rows: Iterable[Mapping[str, object]],
    *,
    key_field: str,
    label: str,
) -> dict[str, dict]:
    markets = {}
    for raw in market_rows:
        row = dict(raw)
        key = str(row.get(key_field) or "").lower()
        if not key:
            raise ValueError(f"{label} market id is empty")
        if key in markets:
            raise ValueError(f"{label} market id repeats: {key}")
        token = normalize_address(str(row.get("token") or ""))
        quote = normalize_address(str(row.get("quote_token") or ""))
        if token == quote:
            raise ValueError(f"{label} token/quote pair is invalid")
        markets[key] = {
            **row,
            "token": token,
            "quote_token": quote,
        }
    if not markets:
        raise ValueError(f"{label} market registry is empty")
    return markets


def _signed_amm_legs(
    row: Mapping[str, object],
    *,
    token: str,
    quote: str,
) -> tuple[str, int, int]:
    token_is_token0 = int(token, 16) < int(quote, 16)
    amount0 = int(row.get("amount0", 0))
    amount1 = int(row.get("amount1", 0))
    token_leg = amount0 if token_is_token0 else amount1
    quote_leg = amount1 if token_is_token0 else amount0
    if token_leg == 0 or quote_leg == 0:
        raise ValueError("Phase-3 AMM trade contains zero trade leg")
    side = "buy" if token_leg < 0 else "sell"
    if side == "buy" and quote_leg <= 0:
        raise ValueError("Phase-3 AMM buy has non-positive quote input")
    if side == "sell" and quote_leg >= 0:
        raise ValueError("Phase-3 AMM sell has non-negative quote output")
    return side, abs(token_leg), abs(quote_leg)


def _canonical_amm_trade(
    row: Mapping[str, object],
    *,
    market: Mapping[str, object],
    source_id: str,
    venue: str,
    phase: str,
) -> dict:
    token = str(market["token"])
    quote = str(market["quote_token"])
    side, token_amount_raw, quote_amount_raw = _signed_amm_legs(
        row,
        token=token,
        quote=quote,
    )
    event = _event_key(row)
    transaction_hash = str(
        row.get("transaction_hash") or ""
    ).lower()
    if not transaction_hash.startswith("0x") or len(
        transaction_hash
    ) != 66:
        raise ValueError("Phase-3 AMM transaction hash is invalid")
    initiator = normalize_address(str(row.get("initiator") or ""))
    protocol_sender = row.get("sender")
    canonical = {
        "version": PHASE3_CANONICAL_TRADE_VERSION,
        "adapter_version": PHASE3_AMM_TRADE_ADAPTER_VERSION,
        "token": token,
        "source_id": source_id,
        "venue": venue,
        "phase": phase,
        "side": side,
        "initiator": initiator,
        "protocol_sender": (
            None
            if protocol_sender is None
            else normalize_address(str(protocol_sender))
        ),
        "transaction_hash": transaction_hash,
        "transaction_to": row.get("transaction_to"),
        "input_selector": row.get("input_selector"),
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
        "quote_token": quote,
        "canonical_phase3_trade": True,
        "outcome_derived": False,
    }
    return validate_phase3_canonical_trade_row(canonical)


def adapt_v3_swaps_to_phase3(
    swap_rows: Iterable[Mapping[str, object]],
    market_rows: Iterable[Mapping[str, object]],
    transaction_rows: Iterable[Mapping[str, object]],
    *,
    source_id: str,
) -> list[dict]:
    """Adapt raw V3/Sushi V3 swaps using tx.from as the wallet identity."""

    source = _source_inventory_row(source_id, "uniswap_v3")
    markets = _market_map(
        market_rows,
        key_field="pool",
        label="Phase-3 V3",
    )
    enriched = attach_transaction_identities(
        swap_rows,
        transaction_rows,
        label="V3 swap",
    )
    output = []
    seen = set()
    for row in enriched:
        pool = str(row.get("pool") or "").lower()
        market = markets.get(pool)
        if market is None:
            raise KeyError(
                f"Phase-3 V3 swap pool is absent from registry: {pool}"
            )
        canonical = _canonical_amm_trade(
            row,
            market=market,
            source_id=source_id,
            venue=str(source["venue"]),
            phase="v3",
        )
        identity = (
            canonical["token"],
            *_event_key(canonical),
        )
        if identity in seen:
            raise ValueError(
                f"Phase-3 V3 trade repeats token event: {identity}"
            )
        seen.add(identity)
        output.append(canonical)
    output.sort(
        key=lambda row: (
            *_event_key(row),
            row["token"],
            row["source_id"],
        )
    )
    return output


def adapt_v4_swaps_to_phase3(
    swap_rows: Iterable[Mapping[str, object]],
    market_rows: Iterable[Mapping[str, object]],
    transaction_rows: Iterable[Mapping[str, object]],
    *,
    source_id: str,
) -> list[dict]:
    """Adapt raw V4 swaps using tx.from as the wallet identity."""

    source = _source_inventory_row(source_id, "uniswap_v4")
    markets = _market_map(
        market_rows,
        key_field="pool_id",
        label="Phase-3 V4",
    )
    enriched = attach_transaction_identities(
        swap_rows,
        transaction_rows,
        label="V4 swap",
    )
    output = []
    seen = set()
    for row in enriched:
        pool_id = str(row.get("pool_id") or "").lower()
        market = markets.get(pool_id)
        if market is None:
            raise KeyError(
                "Phase-3 V4 swap pool id is absent from registry: "
                f"{pool_id}"
            )
        canonical = _canonical_amm_trade(
            row,
            market=market,
            source_id=source_id,
            venue=str(source["venue"]),
            phase="v4",
        )
        identity = (
            canonical["token"],
            *_event_key(canonical),
        )
        if identity in seen:
            raise ValueError(
                f"Phase-3 V4 trade repeats token event: {identity}"
            )
        seen.add(identity)
        output.append(canonical)
    output.sort(
        key=lambda row: (
            *_event_key(row),
            row["token"],
            row["source_id"],
        )
    )
    return output
