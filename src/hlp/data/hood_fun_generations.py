"""Frozen hood.fun generation/deployment evidence for Phase 2."""

from __future__ import annotations

from typing import Mapping

from hlp.config import (
    HOOD_FUN_CURRENT,
    HOOD_FUN_PREVIOUS,
    ROBINHOOD_CHAIN_ID,
    UNISWAP_V3_WETH_USDG_ANCHOR_POOL,
    normalize_address,
)


HOOD_FUN_DEPLOYMENTS_VERSION = "phase2-hoodfun-deployments-v1"
HOOD_FUN_LEGACY_COMPATIBILITY_VERSION = (
    "phase2-hoodfun-legacy-compatibility-v1"
)


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower()
    if len(text) != 64:
        raise ValueError(f"{label} SHA-256 is invalid")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} SHA-256 is invalid") from exc
    return text


def _contract_row(
    raw: Mapping[str, object],
    *,
    expected_address: str,
    label: str,
) -> dict:
    address = normalize_address(str(raw.get("address") or ""))
    expected = normalize_address(expected_address)
    if address != expected:
        raise ValueError(
            f"{label} address drift: {address} != {expected}"
        )
    first = int(raw.get("first_code_block", 0))
    size = int(raw.get("code_bytes", 0))
    if first <= 0 or size <= 0:
        raise ValueError(f"{label} deployment evidence is incomplete")
    return {
        "address": address,
        "first_code_block": first,
        "code_bytes": size,
        "code_sha256": _sha256(
            raw.get("code_sha256"),
            label=f"{label} code",
        ),
    }


def validate_hood_fun_deployments(
    descriptor: Mapping[str, object],
) -> dict:
    """Validate the frozen hood.fun generations and USD-anchor ordering."""
    version = str(descriptor.get("version") or "")
    if version != HOOD_FUN_DEPLOYMENTS_VERSION:
        raise ValueError(
            f"hood.fun deployment version changed: {version!r}"
        )
    if int(descriptor.get("chain_id", -1)) != ROBINHOOD_CHAIN_ID:
        raise ValueError("hood.fun deployment chain changed")

    snapshot = int(descriptor.get("snapshot_head_block", 0))
    if snapshot <= 0:
        raise ValueError("hood.fun deployment snapshot is invalid")

    evidence_run_id = int(descriptor.get("evidence_run_id", 0))
    artifact_id = int(descriptor.get("artifact_id", 0))
    if evidence_run_id <= 0 or artifact_id <= 0:
        raise ValueError("hood.fun deployment evidence IDs are invalid")
    artifact_digest = str(
        descriptor.get("artifact_digest") or ""
    ).lower()
    if not artifact_digest.startswith("sha256:") or len(
        artifact_digest
    ) != 71:
        raise ValueError("hood.fun deployment artifact digest is invalid")
    _sha256(
        artifact_digest.removeprefix("sha256:"),
        label="hood.fun deployment artifact",
    )

    raw_generations = descriptor.get("generations")
    if not isinstance(raw_generations, Mapping):
        raise ValueError("hood.fun generations are missing")
    if set(raw_generations) != {"previous", "current"}:
        raise ValueError("hood.fun generation set changed")

    previous = _contract_row(
        raw_generations["previous"],
        expected_address=HOOD_FUN_PREVIOUS,
        label="previous hood.fun",
    )
    current = _contract_row(
        raw_generations["current"],
        expected_address=HOOD_FUN_CURRENT,
        label="current hood.fun",
    )
    anchor_raw = descriptor.get("pricing_anchor")
    if not isinstance(anchor_raw, Mapping):
        raise ValueError("hood.fun pricing anchor is missing")
    anchor = _contract_row(
        anchor_raw,
        expected_address=UNISWAP_V3_WETH_USDG_ANCHOR_POOL,
        label="hood.fun WETH/USD anchor",
    )

    if not (
        anchor["first_code_block"]
        < previous["first_code_block"]
        < current["first_code_block"]
        <= snapshot
    ):
        raise ValueError(
            "hood.fun deployment/anchor ordering changed"
        )

    return {
        "version": version,
        "chain_id": ROBINHOOD_CHAIN_ID,
        "snapshot_head_block": snapshot,
        "evidence_run_id": evidence_run_id,
        "artifact_id": artifact_id,
        "artifact_name": str(
            descriptor.get("artifact_name") or ""
        ),
        "artifact_digest": artifact_digest,
        "pricing_anchor": anchor,
        "generations": {
            "previous": previous,
            "current": current,
        },
    }



def validate_hood_fun_legacy_compatibility(
    descriptor: Mapping[str, object],
) -> dict:
    """Validate frozen evidence that legacy hood.fun shares the core ABI."""
    version = str(descriptor.get("version") or "")
    if version != HOOD_FUN_LEGACY_COMPATIBILITY_VERSION:
        raise ValueError(
            f"hood.fun legacy compatibility version changed: {version!r}"
        )
    if int(descriptor.get("chain_id", -1)) != ROBINHOOD_CHAIN_ID:
        raise ValueError("hood.fun legacy compatibility chain changed")
    if str(descriptor.get("generation") or "") != "previous":
        raise ValueError("hood.fun legacy compatibility generation changed")

    contract = normalize_address(str(descriptor.get("contract") or ""))
    if contract != normalize_address(HOOD_FUN_PREVIOUS):
        raise ValueError("hood.fun legacy compatibility contract changed")

    evidence_run_id = int(descriptor.get("evidence_run_id", 0))
    artifact_id = int(descriptor.get("artifact_id", 0))
    if evidence_run_id <= 0 or artifact_id <= 0:
        raise ValueError("hood.fun legacy compatibility evidence IDs invalid")

    artifact_digest = str(
        descriptor.get("artifact_digest") or ""
    ).lower()
    if (
        not artifact_digest.startswith("sha256:")
        or len(artifact_digest) != 71
    ):
        raise ValueError(
            "hood.fun legacy compatibility artifact digest invalid"
        )
    _sha256(
        artifact_digest.removeprefix("sha256:"),
        label="hood.fun legacy compatibility artifact",
    )

    first = int(descriptor.get("first_code_block", 0))
    limit = int(descriptor.get("probe_limit_block", 0))
    blocks = int(descriptor.get("probe_blocks_scanned", 0))
    chunks = int(descriptor.get("chunks_scanned", 0))
    requests = int(descriptor.get("requests_made", 0))
    if first <= 0 or limit < first:
        raise ValueError("hood.fun legacy compatibility block range invalid")
    if blocks <= 0 or chunks <= 0 or requests <= 0:
        raise ValueError(
            "hood.fun legacy compatibility probe accounting invalid"
        )

    counts = descriptor.get("event_counts")
    if not isinstance(counts, Mapping):
        raise ValueError("hood.fun legacy compatibility event counts missing")
    created = int(counts.get("token_created", 0))
    trades = int(counts.get("trade", 0))
    if created <= 0 or trades <= 0:
        raise ValueError(
            "hood.fun legacy compatibility lacks both core event types"
        )

    if descriptor.get("current_surface_compatible") is not True:
        raise ValueError("hood.fun legacy core event surface not compatible")
    if descriptor.get("stopped_on_compatibility") is not True:
        raise ValueError("hood.fun legacy probe did not stop on compatibility")

    topics = descriptor.get("known_topics")
    if not isinstance(topics, Mapping):
        raise ValueError("hood.fun legacy known topics missing")
    from hlp.protocols.hood_fun import TOKEN_CREATED_TOPIC, TRADE_TOPIC

    if str(topics.get("token_created") or "").lower() != TOKEN_CREATED_TOPIC:
        raise ValueError("hood.fun legacy TokenCreated topic changed")
    if str(topics.get("trade") or "").lower() != TRADE_TOPIC:
        raise ValueError("hood.fun legacy Trade topic changed")

    samples = descriptor.get("first_samples")
    if not isinstance(samples, Mapping):
        raise ValueError("hood.fun legacy first samples missing")
    for event_type in ("token_created", "trade"):
        raw = samples.get(event_type)
        if not isinstance(raw, Mapping):
            raise ValueError(
                f"hood.fun legacy {event_type} sample missing"
            )
        block = int(raw.get("block_number", 0))
        if block < first or block > limit:
            raise ValueError(
                f"hood.fun legacy {event_type} sample out of range"
            )
        normalize_address(str(raw.get("token") or ""))

    return {
        "version": version,
        "chain_id": ROBINHOOD_CHAIN_ID,
        "generation": "previous",
        "contract": contract,
        "evidence_run_id": evidence_run_id,
        "artifact_id": artifact_id,
        "artifact_name": str(descriptor.get("artifact_name") or ""),
        "artifact_digest": artifact_digest,
        "first_code_block": first,
        "probe_limit_block": limit,
        "probe_blocks_scanned": blocks,
        "chunks_scanned": chunks,
        "requests_made": requests,
        "event_counts": {
            "token_created": created,
            "trade": trades,
        },
        "current_surface_compatible": True,
        "stopped_on_compatibility": True,
    }
