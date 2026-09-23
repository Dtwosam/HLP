"""Frozen pools.trade CCA Q96 orientation evidence."""

from __future__ import annotations

from decimal import Decimal, localcontext
from typing import Mapping

from hlp.config import ROBINHOOD_CHAIN_ID, normalize_address
from hlp.data.pools_trade_cca import infer_cca_price_orientation
from hlp.protocols.uniswap import v4_pool_id


POOLS_TRADE_CCA_ORIENTATION_VERSION = (
    "phase2-pools-trade-cca-orientation-v1"
)
FROZEN_CCA_ORIENTATION = "quote_per_token"


def _bytes32(value: object, *, label: str) -> str:
    text = str(value or "").lower()
    if not text.startswith("0x") or len(text) != 66:
        raise ValueError(f"{label} must be bytes32")
    try:
        int(text[2:], 16)
    except ValueError as exc:
        raise ValueError(f"{label} must be bytes32") from exc
    return text


def _sha256_digest(value: object, *, label: str) -> str:
    text = str(value or "").lower()
    if not text.startswith("sha256:") or len(text) != 71:
        raise ValueError(f"{label} digest is invalid")
    _bytes32("0x" + text.removeprefix("sha256:"), label=label)
    return text


def _tx_hash(value: object, *, label: str) -> str:
    return _bytes32(value, label=label)


def validate_pools_trade_cca_orientation(
    descriptor: Mapping[str, object],
) -> dict:
    """Validate the exact same-transaction CCA→V4 orientation anchor."""
    version = str(descriptor.get("version") or "")
    if version != POOLS_TRADE_CCA_ORIENTATION_VERSION:
        raise ValueError(
            f"pools.trade CCA orientation version changed: {version!r}"
        )
    if int(descriptor.get("chain_id", -1)) != ROBINHOOD_CHAIN_ID:
        raise ValueError("pools.trade CCA orientation chain changed")
    if descriptor.get("orientation_frozen") is not True:
        raise ValueError("pools.trade CCA orientation is not frozen")
    orientation = str(descriptor.get("orientation") or "")
    if orientation != FROZEN_CCA_ORIENTATION:
        raise ValueError(
            f"pools.trade CCA orientation changed: {orientation!r}"
        )

    run_id = int(descriptor.get("evidence_run_id", 0))
    artifact_id = int(descriptor.get("artifact_id", 0))
    if run_id <= 0 or artifact_id <= 0:
        raise ValueError("pools.trade CCA orientation evidence IDs invalid")
    digest = _sha256_digest(
        descriptor.get("artifact_digest"),
        label="pools.trade CCA orientation artifact",
    )

    initializer = normalize_address(
        str(descriptor.get("initializer") or "")
    )
    token = normalize_address(str(descriptor.get("token") or ""))
    currency = normalize_address(
        str(descriptor.get("currency") or "")
    )
    pool_id = _bytes32(
        descriptor.get("pool_id"),
        label="pools.trade CCA orientation PoolId",
    )
    created = int(descriptor.get("created_block", -1))
    migration = int(
        descriptor.get("migration_block_parameter", -1)
    )
    if created < 0 or migration <= created:
        raise ValueError("pools.trade CCA orientation block ordering changed")

    cca_raw = descriptor.get("cca_checkpoint")
    v4_raw = descriptor.get("v4_initialize")
    if not isinstance(cca_raw, Mapping):
        raise ValueError("pools.trade CCA checkpoint evidence missing")
    if not isinstance(v4_raw, Mapping):
        raise ValueError("pools.trade V4 Initialize evidence missing")
    cca = dict(cca_raw)
    v4 = dict(v4_raw)

    if str(cca.get("event_type") or "") != "checkpoint":
        raise ValueError("pools.trade CCA anchor is not a checkpoint")
    clearing_price_x96 = int(cca.get("clearing_price_x96", 0))
    if clearing_price_x96 <= 0:
        raise ValueError("pools.trade CCA anchor price is invalid")
    cca_block = int(cca.get("block_number", -1))
    cca_tx_index = int(cca.get("transaction_index", -1))
    cca_log_index = int(cca.get("log_index", -1))
    cca_tx = _tx_hash(
        cca.get("transaction_hash"),
        label="pools.trade CCA anchor transaction",
    )

    v4_pool_id = _bytes32(
        v4.get("pool_id"),
        label="pools.trade V4 Initialize PoolId",
    )
    if v4_pool_id != pool_id:
        raise ValueError("pools.trade CCA/V4 PoolId mismatch")
    currency0 = normalize_address(str(v4.get("currency0") or ""))
    currency1 = normalize_address(str(v4.get("currency1") or ""))
    if int(currency0, 16) >= int(currency1, 16):
        raise ValueError("pools.trade V4 currencies are not ordered")
    if {currency0, currency1} != {token, currency}:
        raise ValueError("pools.trade V4 currencies changed")
    fee = int(v4.get("fee", -1))
    spacing = int(v4.get("tick_spacing", 1 << 24))
    hooks = normalize_address(str(v4.get("hooks") or ""))
    if v4_pool_id != v4_pool_id_fn(
        currency0=currency0,
        currency1=currency1,
        fee=fee,
        tick_spacing=spacing,
        hooks=hooks,
    ):
        raise ValueError("pools.trade V4 PoolKey does not derive PoolId")

    v4_block = int(v4.get("block_number", -1))
    v4_tx_index = int(v4.get("transaction_index", -1))
    v4_log_index = int(v4.get("log_index", -1))
    v4_tx = _tx_hash(
        v4.get("transaction_hash"),
        label="pools.trade V4 Initialize transaction",
    )
    if (
        cca_block != v4_block
        or cca_tx != v4_tx
        or cca_tx_index != v4_tx_index
        or cca_log_index >= v4_log_index
    ):
        raise ValueError(
            "pools.trade CCA/V4 orientation anchor is not ordered "
            "within one transaction"
        )
    if v4_block < migration:
        raise ValueError(
            "pools.trade V4 Initialize precedes migration parameter block"
        )

    v4_quote_per_token = Decimal(
        str(descriptor.get("v4_raw_quote_per_token") or "0")
    )
    if v4_quote_per_token <= 0:
        raise ValueError("pools.trade V4 quote-per-token is invalid")
    inferred = infer_cca_price_orientation(
        clearing_price_x96,
        migrated_quote_per_token=v4_quote_per_token,
    )
    if inferred["orientation"] != FROZEN_CCA_ORIENTATION:
        raise ValueError("pools.trade CCA orientation inference changed")

    direct = Decimal(
        str(descriptor.get("direct_quote_per_token") or "0")
    )
    direct_error = Decimal(
        str(descriptor.get("direct_relative_error") or "0")
    )
    inverse_error = Decimal(
        str(descriptor.get("inverse_relative_error") or "0")
    )
    max_error = Decimal(
        str(descriptor.get("max_accepted_relative_error") or "0")
    )
    if max_error <= 0:
        raise ValueError("pools.trade CCA max error threshold invalid")
    recomputed_direct = inferred["direct_quote_per_token"]
    recomputed_direct_error = inferred["direct_relative_error"]
    recomputed_inverse_error = inferred["inverse_relative_error"]

    with localcontext() as context:
        context.prec = 80
        price_evidence_error = abs(
            direct / recomputed_direct - Decimal(1)
        )
        direct_error_evidence_error = abs(
            direct_error - recomputed_direct_error
        )
        inverse_error_evidence_error = abs(
            inverse_error - recomputed_inverse_error
        )
        inverse_error_scale = max(
            Decimal(1),
            abs(recomputed_inverse_error),
        )
        inverse_error_relative = (
            inverse_error_evidence_error / inverse_error_scale
        )
    if price_evidence_error > max_error:
        raise ValueError(
            "pools.trade CCA direct price evidence exceeds error threshold"
        )
    if direct_error_evidence_error > max_error:
        raise ValueError(
            "pools.trade CCA direct error evidence exceeds error threshold"
        )
    if inverse_error_relative > max_error:
        raise ValueError(
            "pools.trade CCA inverse error evidence exceeds error threshold"
        )
    if recomputed_direct_error > max_error:
        raise ValueError(
            "pools.trade CCA direct orientation exceeds error threshold"
        )
    if recomputed_inverse_error <= recomputed_direct_error:
        raise ValueError(
            "pools.trade CCA inverse orientation is not worse"
        )

    return {
        "version": version,
        "chain_id": ROBINHOOD_CHAIN_ID,
        "orientation": FROZEN_CCA_ORIENTATION,
        "orientation_frozen": True,
        "evidence_run_id": run_id,
        "artifact_id": artifact_id,
        "artifact_name": str(descriptor.get("artifact_name") or ""),
        "artifact_digest": digest,
        "initializer": initializer,
        "token": token,
        "currency": currency,
        "pool_id": pool_id,
        "created_block": created,
        "migration_block_parameter": migration,
        "cca_block": cca_block,
        "v4_initialize_block": v4_block,
        "same_transaction": True,
        "direct_quote_per_token": str(direct),
        "v4_raw_quote_per_token": str(v4_quote_per_token),
        "direct_relative_error": str(direct_error),
        "inverse_relative_error": str(inverse_error),
        "max_accepted_relative_error": str(max_error),
    }


# Alias avoids shadowing the local pool_id value in validation code.
v4_pool_id_fn = v4_pool_id
