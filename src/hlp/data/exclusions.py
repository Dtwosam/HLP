"""Deterministic Phase-2 asset exclusion registry.

Universe exclusion is address-based only. Symbols and names are retained as
metadata but never participate in classification.
"""

from __future__ import annotations

from typing import Iterable, Mapping

from hlp.config import (
    ROBINHOOD_CHAIN_ID,
    ROBINHOOD_USDG,
    ROBINHOOD_WETH,
    normalize_address,
)
from hlp.data.robinhood_assets import RobinhoodAssetsClient


EXTRA_EXCLUSION_CATEGORIES = frozenset(
    {
        "lp_position_token",
        "protocol_system_token",
        "bridge_infrastructure_token",
    }
)


def _canonical_entry(
    *,
    address: str,
    category: str,
    source: str,
    reason: str,
    metadata: Mapping[str, object] | None = None,
) -> dict:
    row = {
        "address": normalize_address(address),
        "chain_id": ROBINHOOD_CHAIN_ID,
        "category": str(category),
        "source": str(source),
        "reason": str(reason),
    }
    if metadata:
        row["metadata"] = dict(metadata)
    return row


def build_phase2_exclusion_registry(
    robinhood_asset_rows: Iterable[Mapping[str, object]] = (),
    *,
    extra_verified_assets: Iterable[Mapping[str, object]] = (),
) -> list[dict]:
    """Build the frozen address-keyed exclusion registry.

    Robinhood canonical assets are accepted only from rows whose deployment is
    already resolved to Robinhood Chain. Additional LP/system/bridge assets
    must be supplied explicitly with an allowed deterministic category and
    source provenance.
    """
    rows = [
        _canonical_entry(
            address=ROBINHOOD_WETH,
            category="wrapped_native",
            source="hlp.config",
            reason="canonical Robinhood Chain WETH",
        ),
        _canonical_entry(
            address=ROBINHOOD_USDG,
            category="stablecoin",
            source="hlp.config",
            reason="canonical Robinhood Chain USDG",
        ),
    ]

    for asset in robinhood_asset_rows:
        chain_id = int(asset.get("chain_id", -1))
        if chain_id != ROBINHOOD_CHAIN_ID:
            raise ValueError(
                "Robinhood canonical asset row has wrong chain: "
                f"{chain_id}"
            )
        address = asset.get("contract_address")
        if not isinstance(address, str) or not address:
            raise ValueError(
                "Robinhood canonical asset row has no contract address"
            )
        rows.append(
            _canonical_entry(
                address=address,
                category="robinhood_canonical_asset",
                source="robinhood_rhj_assets",
                reason="canonical Robinhood Stock Token/ETF registry asset",
                metadata={
                    "asset_id": str(asset.get("asset_id") or ""),
                    "token_symbol": str(asset.get("token_symbol") or ""),
                    "token_name": str(asset.get("token_name") or ""),
                    "status": str(asset.get("status") or ""),
                },
            )
        )

    for asset in extra_verified_assets:
        address = asset.get("address")
        category = str(asset.get("category") or "")
        source = str(asset.get("source") or "")
        reason = str(asset.get("reason") or "")
        if not isinstance(address, str) or not address:
            raise ValueError("verified exclusion row has no address")
        if category not in EXTRA_EXCLUSION_CATEGORIES:
            raise ValueError(
                "verified exclusion row has unsupported category: "
                f"{category!r}"
            )
        if not source:
            raise ValueError("verified exclusion row has no source provenance")
        if not reason:
            raise ValueError("verified exclusion row has no reason")
        metadata = asset.get("metadata")
        if metadata is not None and not isinstance(metadata, Mapping):
            raise ValueError("verified exclusion metadata must be an object")
        rows.append(
            _canonical_entry(
                address=address,
                category=category,
                source=source,
                reason=reason,
                metadata=metadata,
            )
        )

    by_address: dict[str, dict] = {}
    for row in rows:
        address = row["address"]
        previous = by_address.get(address)
        if previous is not None:
            raise ValueError(
                "duplicate deterministic exclusion address: "
                f"{address} ({previous['category']} vs {row['category']})"
            )
        by_address[address] = row

    return [by_address[address] for address in sorted(by_address)]


def build_phase2_exclusion_registry_from_client(
    assets_client: RobinhoodAssetsClient,
    *,
    extra_verified_assets: Iterable[Mapping[str, object]] = (),
) -> list[dict]:
    """Resolve official Robinhood assets, then build the pure registry."""
    return build_phase2_exclusion_registry(
        assets_client.canonical_chain_assets(),
        extra_verified_assets=extra_verified_assets,
    )


def exclusion_map(registry_rows: Iterable[Mapping[str, object]]) -> dict[str, dict]:
    """Return a validated address map for deterministic universe filtering."""
    output: dict[str, dict] = {}
    for raw in registry_rows:
        address = normalize_address(str(raw["address"]))
        if int(raw.get("chain_id", -1)) != ROBINHOOD_CHAIN_ID:
            raise ValueError(f"exclusion row has wrong chain: {address}")
        if address in output:
            raise ValueError(f"duplicate exclusion address: {address}")
        output[address] = dict(raw)
        output[address]["address"] = address
    return output


def classify_excluded_asset(
    address: str,
    registry_rows: Iterable[Mapping[str, object]],
) -> dict | None:
    """Return exclusion provenance for an exact address match, else None."""
    return exclusion_map(registry_rows).get(normalize_address(address))


def apply_phase2_exclusions(
    universe_rows: Iterable[Mapping[str, object]],
    registry_rows: Iterable[Mapping[str, object]],
    *,
    address_field: str = "token",
) -> list[dict]:
    """Annotate threshold evidence with deterministic Phase-2 universe status.

    Existing threshold/price evidence is preserved. Exclusion changes only the
    Phase-2 membership status and adds exact address-level provenance.
    """
    registry = exclusion_map(registry_rows)
    output: list[dict] = []

    for raw in universe_rows:
        if address_field not in raw:
            raise ValueError(
                f"universe row has no address field {address_field!r}"
            )
        address = normalize_address(str(raw[address_field]))
        threshold_status = str(raw.get("eligibility_status") or "")
        if threshold_status not in {"eligible", "ineligible", "unknown"}:
            raise ValueError(
                "universe row has invalid threshold eligibility status: "
                f"{threshold_status!r}"
            )

        row = dict(raw)
        row[address_field] = address
        exclusion = registry.get(address)
        row["excluded"] = exclusion is not None
        if exclusion is None:
            row["phase2_universe_status"] = threshold_status
            row["exclusion_category"] = None
            row["exclusion_source"] = None
            row["exclusion_reason"] = None
        else:
            row["phase2_universe_status"] = "excluded"
            row["exclusion_category"] = exclusion["category"]
            row["exclusion_source"] = exclusion["source"]
            row["exclusion_reason"] = exclusion["reason"]
        output.append(row)

    return output
