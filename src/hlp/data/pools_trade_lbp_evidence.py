"""Frozen pools.trade LBP PoolKey evidence for Phase 2."""

from __future__ import annotations

from typing import Mapping

from hlp.config import ROBINHOOD_CHAIN_ID, normalize_address
from hlp.protocols.pools_trade_lbp import POOLS_TRADE_LBP_STRATEGY
from hlp.protocols.uniswap import v4_pool_id


POOLS_TRADE_LBP_POOLKEY_VERSION = "phase2-pools-trade-lbp-poolkey-v1"


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower()
    if len(text) != 64:
        raise ValueError(f"{label} SHA-256 is invalid")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} SHA-256 is invalid") from exc
    return text


def validate_pools_trade_lbp_poolkey(
    descriptor: Mapping[str, object],
) -> dict:
    """Validate and recompute the frozen LBP PoolKey/PoolId."""
    version = str(descriptor.get("version") or "")
    if version != POOLS_TRADE_LBP_POOLKEY_VERSION:
        raise ValueError(
            f"pools.trade LBP PoolKey version changed: {version!r}"
        )
    if int(descriptor.get("chain_id", -1)) != ROBINHOOD_CHAIN_ID:
        raise ValueError("pools.trade LBP PoolKey chain changed")

    run_id = int(descriptor.get("evidence_run_id", 0))
    artifact_id = int(descriptor.get("artifact_id", 0))
    if run_id <= 0 or artifact_id <= 0:
        raise ValueError("pools.trade LBP PoolKey evidence IDs invalid")

    digest = str(descriptor.get("artifact_digest") or "").lower()
    if not digest.startswith("sha256:") or len(digest) != 71:
        raise ValueError("pools.trade LBP PoolKey artifact digest invalid")
    _sha256(
        digest.removeprefix("sha256:"),
        label="pools.trade LBP PoolKey artifact",
    )

    strategy = normalize_address(
        str(descriptor.get("strategy") or "")
    )
    if strategy != normalize_address(POOLS_TRADE_LBP_STRATEGY):
        raise ValueError("pools.trade LBP strategy changed")

    initializer = normalize_address(
        str(descriptor.get("initializer") or "")
    )
    token = normalize_address(str(descriptor.get("token") or ""))
    currency = normalize_address(
        str(descriptor.get("currency") or "")
    )
    hooks = normalize_address(
        str(descriptor.get("pool_hook") or "")
    )
    if token == currency:
        raise ValueError("pools.trade LBP token equals currency")

    fee = int(descriptor.get("pool_fee", -1))
    spacing = int(descriptor.get("pool_tick_spacing", 1 << 24))
    migration = int(descriptor.get("migration_block", 0))
    created = int(descriptor.get("initializer_created_block", 0))
    if created <= 0 or migration <= created:
        raise ValueError("pools.trade LBP block ordering changed")

    currency0, currency1 = sorted(
        (token, currency),
        key=lambda value: int(value, 16),
    )
    derived = v4_pool_id(
        currency0=currency0,
        currency1=currency1,
        fee=fee,
        tick_spacing=spacing,
        hooks=hooks,
    )
    expected = str(descriptor.get("derived_pool_id") or "").lower()
    if derived != expected:
        raise ValueError(
            "pools.trade LBP derived PoolId changed: "
            f"{derived} != {expected}"
        )

    reserved = int(
        str(descriptor.get("reserved_token_amount_for_lp") or "0")
    )
    if reserved < 0:
        raise ValueError("pools.trade LBP reserved allocation is negative")

    tx_hash = str(
        descriptor.get("initializer_created_transaction_hash") or ""
    ).lower()
    if not tx_hash.startswith("0x") or len(tx_hash) != 66:
        raise ValueError("pools.trade LBP creation tx hash invalid")
    int(tx_hash[2:], 16)

    return {
        "version": version,
        "chain_id": ROBINHOOD_CHAIN_ID,
        "evidence_run_id": run_id,
        "artifact_id": artifact_id,
        "artifact_name": str(descriptor.get("artifact_name") or ""),
        "artifact_digest": digest,
        "strategy": strategy,
        "initializer": initializer,
        "token": token,
        "currency": currency,
        "migration_block": migration,
        "reserved_token_amount_for_lp": reserved,
        "recipient": normalize_address(
            str(descriptor.get("recipient") or "")
        ),
        "position_recipient": normalize_address(
            str(descriptor.get("position_recipient") or "")
        ),
        "pool_fee": fee,
        "pool_tick_spacing": spacing,
        "pool_hook": hooks,
        "initializer_created_block": created,
        "initializer_created_transaction_hash": tx_hash,
        "initializer_created_transaction_index": int(
            descriptor.get("initializer_created_transaction_index", -1)
        ),
        "initializer_created_log_index": int(
            descriptor.get("initializer_created_log_index", -1)
        ),
        "derived_pool_id": derived,
    }
