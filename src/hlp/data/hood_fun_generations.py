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
