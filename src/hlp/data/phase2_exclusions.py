"""Deterministic Phase-2 address exclusion registry."""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Mapping

from hlp.config import (
    ROBINHOOD_CHAIN_ID,
    ROBINHOOD_USDG,
    ROBINHOOD_WETH,
    normalize_address,
)


PHASE2_EXCLUSION_REGISTRY_VERSION = "phase2-exclusion-registry-v1"


def _static_rows() -> list[dict]:
    return [
        {
            "address": normalize_address(ROBINHOOD_WETH),
            "exclusion_class": "canonical_weth",
            "identity_source": "hlp.config.ROBINHOOD_WETH",
            "reason": "canonical wrapped native asset",
            "asset_id": None,
            "token_symbol": None,
            "token_name": None,
        },
        {
            "address": normalize_address(ROBINHOOD_USDG),
            "exclusion_class": "canonical_usdg",
            "identity_source": "hlp.config.ROBINHOOD_USDG",
            "reason": "canonical USD stablecoin",
            "asset_id": None,
            "token_symbol": None,
            "token_name": None,
        },
    ]


def build_phase2_exclusion_registry(
    robinhood_chain_assets: Iterable[Mapping[str, object]],
) -> tuple[list[dict], dict]:
    """Build canonical non-memecoin exclusions using address identity only.

    Robinhood's official asset registry is authoritative for Stock Token/ETF
    deployment identity. Symbols and names are retained only as audit metadata
    and never participate in matching.
    """
    by_address = {
        row["address"]: dict(row)
        for row in _static_rows()
    }
    official_addresses: set[str] = set()

    for raw in robinhood_chain_assets:
        row = dict(raw)
        if int(row.get("chain_id", -1)) != ROBINHOOD_CHAIN_ID:
            raise ValueError(
                "Robinhood exclusion asset belongs to another chain"
            )
        address = normalize_address(str(row.get("contract_address") or ""))
        asset_id = str(row.get("asset_id") or "").strip().lower()
        if not asset_id:
            raise ValueError(
                f"Robinhood exclusion asset lacks asset_id: {address}"
            )
        if address in official_addresses:
            raise ValueError(
                f"Robinhood exclusion registry repeats address: {address}"
            )
        official_addresses.add(address)

        if address in by_address:
            # Static WETH/USDG identity has precedence if the official endpoint
            # ever starts listing either address. The official row is still
            # recorded as metadata so the overlap is auditable.
            current = by_address[address]
            current["robinhood_asset_id"] = asset_id
            current["robinhood_token_symbol"] = str(
                row.get("token_symbol") or ""
            )
            current["robinhood_token_name"] = str(
                row.get("token_name") or ""
            )
            continue

        by_address[address] = {
            "address": address,
            "exclusion_class": "robinhood_canonical_asset",
            "identity_source": "official_robinhood_rhj_assets",
            "reason": (
                "canonical Robinhood asset deployment; excluded by address"
            ),
            "asset_id": asset_id,
            "token_symbol": str(row.get("token_symbol") or ""),
            "token_name": str(row.get("token_name") or ""),
        }

    if not official_addresses:
        raise ValueError(
            "Robinhood canonical asset registry returned no chain assets"
        )

    output = sorted(
        by_address.values(),
        key=lambda row: row["address"],
    )
    if len(output) != len({
        row["address"] for row in output
    }):
        raise ValueError("Phase-2 exclusion registry repeats address")

    categories = Counter(
        str(row["exclusion_class"])
        for row in output
    )
    summary = {
        "version": PHASE2_EXCLUSION_REGISTRY_VERSION,
        "chain_id": ROBINHOOD_CHAIN_ID,
        "excluded_addresses": len(output),
        "official_robinhood_addresses": len(official_addresses),
        "exclusion_class_counts": dict(sorted(categories.items())),
        "required_static_addresses": sorted([
            normalize_address(ROBINHOOD_WETH),
            normalize_address(ROBINHOOD_USDG),
        ]),
        "matching_semantics": "exact_normalized_address_only",
        "symbol_or_name_matching_allowed": False,
        "broader_asset_class_heuristics_allowed": False,
    }
    return output, summary


def apply_phase2_exclusion_registry(
    token_addresses: Iterable[str],
    exclusion_rows: Iterable[Mapping[str, object]],
) -> tuple[list[str], list[dict]]:
    """Partition candidate token addresses by exact registry membership."""
    exclusions: dict[str, dict] = {}
    for raw in exclusion_rows:
        row = dict(raw)
        address = normalize_address(str(row.get("address") or ""))
        if address in exclusions:
            raise ValueError(
                f"duplicate Phase-2 exclusion address: {address}"
            )
        exclusions[address] = row

    included: list[str] = []
    excluded: list[dict] = []
    seen: set[str] = set()
    for raw in token_addresses:
        address = normalize_address(str(raw))
        if address in seen:
            continue
        seen.add(address)
        match = exclusions.get(address)
        if match is None:
            included.append(address)
        else:
            excluded.append({
                "address": address,
                "exclusion_class": match["exclusion_class"],
                "identity_source": match["identity_source"],
            })

    included.sort()
    excluded.sort(key=lambda row: row["address"])
    return included, excluded
