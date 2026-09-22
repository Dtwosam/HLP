"""Phase-3 adapters from source-normalized trades into the canonical trade schema."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
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
PHASE3_CURVE_TRADE_ADAPTER_VERSION = "phase3-curve-trade-adapter-v1"


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



def _source_inventory_row(
    source_id: str,
    required_phase: str | Iterable[str],
) -> dict:
    rows = {
        str(row["source_id"]): dict(row)
        for row in build_phase2_source_inventory()
    }
    source = rows.get(str(source_id))
    if source is None:
        raise ValueError(
            f"unknown Phase-3 AMM trade source id: {source_id}"
        )
    required = (
        {required_phase}
        if isinstance(required_phase, str)
        else {str(value) for value in required_phase}
    )
    advertised = set(source.get("market_phases") or [])
    if not (required & advertised):
        raise ValueError(
            f"{source_id} does not advertise any of "
            f"{sorted(required)}"
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

    source = _source_inventory_row(
        source_id,
        ("uniswap_v3", "sushiswap_v3"),
    )
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



def _as_row(raw: object) -> dict:
    if is_dataclass(raw):
        return asdict(raw)
    if isinstance(raw, Mapping):
        return dict(raw)
    raise TypeError(
        f"unsupported Phase-3 curve trade row: {type(raw)!r}"
    )


def _canonical_curve_trade(
    row: Mapping[str, object],
    *,
    source_id: str,
    venue: str,
    side: str,
    token_amount_raw: int,
    quote_amount_raw: int,
    quote_token: str,
) -> dict:
    token = normalize_address(str(row.get("token") or ""))
    quote = normalize_address(str(quote_token))
    event = _event_key(row)
    if side not in {"buy", "sell"}:
        raise ValueError("Phase-3 curve trade side is invalid")
    token_amount = int(token_amount_raw)
    quote_amount = int(quote_amount_raw)
    if token_amount <= 0 or quote_amount <= 0:
        raise ValueError(
            "Phase-3 curve trade amounts must be positive"
        )
    transaction_hash = str(
        row.get("transaction_hash") or ""
    ).lower()
    if not transaction_hash.startswith("0x") or len(
        transaction_hash
    ) != 66:
        raise ValueError(
            "Phase-3 curve trade transaction hash is invalid"
        )
    protocol_actor = row.get("actor")
    canonical = {
        "version": PHASE3_CANONICAL_TRADE_VERSION,
        "adapter_version": PHASE3_CURVE_TRADE_ADAPTER_VERSION,
        "token": token,
        "source_id": source_id,
        "venue": venue,
        "phase": "curve",
        "side": side,
        "initiator": normalize_address(
            str(row.get("initiator") or "")
        ),
        "protocol_actor": (
            None
            if protocol_actor is None
            else normalize_address(str(protocol_actor))
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
        "token_amount_raw": token_amount,
        "quote_amount_raw": quote_amount,
        "quote_token": quote,
        "canonical_phase3_trade": True,
        "outcome_derived": False,
    }
    return validate_phase3_canonical_trade_row(canonical)


def adapt_flap_trades_to_phase3(
    curve_rows: Iterable[Mapping[str, object]],
    transaction_rows: Iterable[Mapping[str, object]],
) -> list[dict]:
    """Adapt Flap TokenBought/TokenSold rows using tx.from identity."""

    source = _source_inventory_row("flap", "bonding_curve")
    trades = []
    for raw in curve_rows:
        row = _as_row(raw)
        if row.get("event_type") in {"token_bought", "token_sold"}:
            trades.append(row)
    enriched = attach_transaction_identities(
        trades,
        transaction_rows,
        label="Flap trade",
    )

    output = []
    seen = set()
    for row in enriched:
        event_type = str(row.get("event_type") or "")
        side = "buy" if event_type == "token_bought" else "sell"
        quote_token = row.get("quote_token")
        if quote_token is None:
            raise ValueError(
                "Flap Phase-3 trade has no quote token"
            )
        canonical = _canonical_curve_trade(
            row,
            source_id="flap",
            venue=str(source["venue"]),
            side=side,
            token_amount_raw=int(row.get("amount_raw") or 0),
            quote_amount_raw=int(
                row.get("quote_amount_raw") or 0
            ),
            quote_token=str(quote_token),
        )
        identity = (
            canonical["token"],
            *_event_key(canonical),
        )
        if identity in seen:
            raise ValueError(
                f"Flap Phase-3 trade repeats token event: {identity}"
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


def adapt_hood_fun_trades_to_phase3(
    curve_rows: Iterable[Mapping[str, object]],
    transaction_rows: Iterable[Mapping[str, object]],
    *,
    source_id: str,
) -> list[dict]:
    """Adapt current/previous hood.fun trade rows using tx.from identity."""

    if source_id not in {
        "hood_fun_current",
        "hood_fun_previous",
    }:
        raise ValueError(
            f"unsupported hood.fun Phase-3 source id: {source_id}"
        )
    source = _source_inventory_row(
        source_id,
        ("bonding_curve", "curve"),
    )
    trades = []
    for raw in curve_rows:
        row = _as_row(raw)
        if row.get("event_type") == "trade":
            generation = row.get("generation")
            if generation is not None:
                expected = (
                    "current"
                    if source_id == "hood_fun_current"
                    else "previous"
                )
                if str(generation) != expected:
                    raise ValueError(
                        f"{source_id} hood.fun generation drift: "
                        f"{generation}"
                    )
            trades.append(row)
    enriched = attach_transaction_identities(
        trades,
        transaction_rows,
        label="hood.fun trade",
    )

    output = []
    seen = set()
    for row in enriched:
        is_buy = row.get("is_buy")
        if is_buy not in {True, False}:
            raise ValueError(
                "hood.fun Phase-3 trade is_buy is invalid"
            )
        quote_token = row.get("quote_token")
        if quote_token is None:
            raise ValueError(
                "hood.fun Phase-3 trade has no quote token"
            )
        canonical = _canonical_curve_trade(
            row,
            source_id=source_id,
            venue=str(source["venue"]),
            side="buy" if is_buy else "sell",
            token_amount_raw=int(
                row.get("token_amount_raw") or 0
            ),
            quote_amount_raw=int(
                row.get("quote_amount_raw") or 0
            ),
            quote_token=str(quote_token),
        )
        identity = (
            canonical["token"],
            *_event_key(canonical),
        )
        if identity in seen:
            raise ValueError(
                "hood.fun Phase-3 trade repeats token event: "
                f"{identity}"
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


def adapt_trench_trades_to_phase3(
    event_rows: Iterable[object],
    registry_rows: Iterable[Mapping[str, object]],
    transaction_rows: Iterable[Mapping[str, object]],
) -> list[dict]:
    """Adapt trench.today purchase/sale events using frozen launch quotes."""

    source = _source_inventory_row(
        "trench_today",
        "bonding_curve",
    )
    registry = {}
    for raw in registry_rows:
        row = dict(raw)
        token = normalize_address(str(row.get("token") or ""))
        quote = normalize_address(
            str(row.get("quote_token") or "")
        )
        if token in registry:
            raise ValueError(
                f"trench.today Phase-3 registry repeats token: {token}"
            )
        registry[token] = quote
    if not registry:
        raise ValueError("trench.today Phase-3 registry is empty")

    trades = []
    for raw in event_rows:
        row = _as_row(raw)
        if row.get("event_type") in {
            "token_purchase",
            "token_sale",
        }:
            trades.append(row)
    enriched = attach_transaction_identities(
        trades,
        transaction_rows,
        label="trench.today trade",
    )

    output = []
    seen = set()
    for row in enriched:
        token = normalize_address(str(row.get("token") or ""))
        quote = registry.get(token)
        if quote is None:
            raise KeyError(
                "trench.today Phase-3 trade token absent from registry: "
                f"{token}"
            )
        event_type = str(row.get("event_type") or "")
        canonical = _canonical_curve_trade(
            row,
            source_id="trench_today",
            venue=str(source["venue"]),
            side=(
                "buy"
                if event_type == "token_purchase"
                else "sell"
            ),
            token_amount_raw=int(row.get("amount_raw") or 0),
            quote_amount_raw=int(
                row.get("quote_amount_raw") or 0
            ),
            quote_token=quote,
        )
        identity = (
            canonical["token"],
            *_event_key(canonical),
        )
        if identity in seen:
            raise ValueError(
                "trench.today Phase-3 trade repeats token event: "
                f"{identity}"
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
