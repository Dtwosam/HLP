"""Frozen Phase-2 launch/trading source inventory.

This inventory separates source identity from historical coverage readiness.
Knowing a contract address or decoder is not equivalent to having a complete
lifecycle dataset.
"""

from __future__ import annotations

from hlp.config import (
    DOPPLER_AIRLOCK,
    FLAP_PORTAL,
    HOOD_FUN_CURRENT,
    HOOD_FUN_PREVIOUS,
    NOXA_LAUNCH_FACTORY,
    PONS_V1_FACTORIES,
    PONS_V2_FACTORY,
    POOLS_FUN_FACTORY,
    POOLS_TRADE_LAUNCHER_CURRENT,
    POOLS_TRADE_LAUNCHER_ORIGINAL,
    SUSHISWAP_V3_FACTORY,
    TRENCH_MANAGER,
    UNISWAP_V3_FACTORY,
    UNISWAP_V4_POOL_MANAGER,
    normalize_address,
)
from hlp.protocols.pools_trade_lbp import POOLS_TRADE_LBP_STRATEGY


PHASE2_SOURCE_INVENTORY_VERSION = "phase2-sources-v1"
READINESS_STATES = frozenset(
    {
        "phase1_proven",
        "adapter_ready",
        "decoder_ready",
        "discovery_pending",
    }
)


def _addresses(*values: str) -> list[str]:
    return [normalize_address(value) for value in values]


def build_phase2_source_inventory() -> list[dict]:
    """Return deterministic known launch/trading sources and readiness.

    phase1_proven means the source has same-snapshot lifecycle evidence from
    the accepted Phase-1 Pons path. adapter_ready means launch and native
    price-path adapters exist but chain-wide historical coverage is not yet
    frozen. decoder_ready means identity/event decoding exists but registry
    or lifecycle assembly remains. discovery_pending means the DEX is a
    material chain-wide trading venue whose direct-launch population still
    needs deterministic discovery.
    """
    rows = [
        {
            "source_id": "pons_v1",
            "venue": "pons",
            "source_kind": "launchpad",
            "launch_contracts": _addresses(*PONS_V1_FACTORIES),
            "trading_contracts": _addresses(UNISWAP_V3_FACTORY),
            "market_phases": ["uniswap_v3"],
            "readiness": "phase1_proven",
            "implementation_evidence": [
                "hlp.data.pons_v1",
                "hlp.data.universe",
            ],
        },
        {
            "source_id": "pons_v2",
            "venue": "pons",
            "source_kind": "launchpad",
            "launch_contracts": _addresses(PONS_V2_FACTORY),
            "trading_contracts": _addresses(UNISWAP_V4_POOL_MANAGER),
            "market_phases": ["bonding_curve", "uniswap_v4"],
            "readiness": "phase1_proven",
            "implementation_evidence": [
                "hlp.data.pons_v2",
                "hlp.data.v2_curve",
                "hlp.data.pons_v2_v4_artifacts",
            ],
        },
        {
            "source_id": "pools_fun",
            "venue": "pools.fun",
            "source_kind": "launchpad",
            "launch_contracts": _addresses(POOLS_FUN_FACTORY),
            "trading_contracts": _addresses(SUSHISWAP_V3_FACTORY),
            "market_phases": ["sushiswap_v3"],
            "readiness": "adapter_ready",
            "implementation_evidence": [
                "hlp.data.pools_fun_registry",
                "hlp.data.v3_launchpad",
            ],
        },
        {
            "source_id": "pools_trade_instant",
            "venue": "pools.trade",
            "source_kind": "launchpad",
            "launch_contracts": _addresses(
                POOLS_TRADE_LAUNCHER_ORIGINAL,
                POOLS_TRADE_LAUNCHER_CURRENT,
            ),
            "trading_contracts": _addresses(UNISWAP_V4_POOL_MANAGER),
            "market_phases": ["uniswap_v4"],
            "readiness": "adapter_ready",
            "implementation_evidence": [
                "hlp.data.pools_trade_registry",
                "hlp.data.pools_trade_v4",
            ],
        },
        {
            "source_id": "pools_trade_lbp",
            "venue": "pools.trade",
            "source_kind": "launchpad",
            "launch_contracts": _addresses(POOLS_TRADE_LBP_STRATEGY),
            "trading_contracts": _addresses(UNISWAP_V4_POOL_MANAGER),
            "market_phases": ["lbp", "uniswap_v4"],
            "readiness": "decoder_ready",
            "implementation_evidence": [
                "hlp.protocols.pools_trade_lbp",
            ],
            "blocking_gap": "persistent LBP registry and lifecycle assembly",
        },
        {
            "source_id": "doppler",
            "venue": "doppler",
            "source_kind": "launchpad",
            "launch_contracts": _addresses(DOPPLER_AIRLOCK),
            "trading_contracts": _addresses(UNISWAP_V4_POOL_MANAGER),
            "market_phases": ["uniswap_v4"],
            "readiness": "adapter_ready",
            "implementation_evidence": [
                "hlp.data.doppler_registry",
                "hlp.data.v4_launchpad",
            ],
        },
        {
            "source_id": "flap",
            "venue": "flap",
            "source_kind": "launchpad",
            "launch_contracts": _addresses(FLAP_PORTAL),
            "trading_contracts": [],
            "market_phases": ["bonding_curve"],
            "readiness": "adapter_ready",
            "implementation_evidence": [
                "hlp.data.flap_registry",
                "hlp.data.flap_curve",
            ],
        },
        {
            "source_id": "trench_today",
            "venue": "trench.today",
            "source_kind": "launchpad",
            "launch_contracts": _addresses(TRENCH_MANAGER),
            "trading_contracts": [],
            "market_phases": ["bonding_curve"],
            "readiness": "adapter_ready",
            "implementation_evidence": [
                "hlp.data.trench_registry",
                "hlp.data.trench_curve",
            ],
        },
        {
            "source_id": "hood_fun_current",
            "venue": "hood.fun",
            "source_kind": "launchpad",
            "launch_contracts": _addresses(HOOD_FUN_CURRENT),
            "trading_contracts": [],
            "market_phases": ["bonding_curve"],
            "readiness": "adapter_ready",
            "implementation_evidence": [
                "hlp.data.hood_fun_registry",
                "hlp.data.hood_fun_curve",
            ],
        },
        {
            "source_id": "hood_fun_previous",
            "venue": "hood.fun",
            "source_kind": "launchpad",
            "launch_contracts": _addresses(HOOD_FUN_PREVIOUS),
            "trading_contracts": [],
            "market_phases": ["unknown_legacy_curve"],
            "readiness": "discovery_pending",
            "implementation_evidence": [],
            "blocking_gap": "legacy contract ABI and historical lifecycle adapter",
        },
        {
            "source_id": "noxa",
            "venue": "noxa",
            "source_kind": "launchpad",
            "launch_contracts": _addresses(NOXA_LAUNCH_FACTORY),
            "trading_contracts": _addresses(UNISWAP_V3_FACTORY),
            "market_phases": ["uniswap_v3"],
            "readiness": "decoder_ready",
            "implementation_evidence": [
                "hlp.protocols.noxa",
                "hlp.protocols.noxa_state",
                "hlp.data.v3_launchpad",
            ],
            "blocking_gap": "persistent historical launch registry assembly",
        },
        {
            "source_id": "direct_uniswap_v3",
            "venue": "uniswap_v3",
            "source_kind": "direct_dex",
            "launch_contracts": [],
            "trading_contracts": _addresses(UNISWAP_V3_FACTORY),
            "market_phases": ["uniswap_v3"],
            "readiness": "discovery_pending",
            "implementation_evidence": ["hlp.data.v3_launchpad"],
            "blocking_gap": "deterministic direct-launch discovery rule",
        },
        {
            "source_id": "direct_uniswap_v4",
            "venue": "uniswap_v4",
            "source_kind": "direct_dex",
            "launch_contracts": [],
            "trading_contracts": _addresses(UNISWAP_V4_POOL_MANAGER),
            "market_phases": ["uniswap_v4"],
            "readiness": "discovery_pending",
            "implementation_evidence": ["hlp.data.v4_launchpad"],
            "blocking_gap": "deterministic direct-launch discovery rule",
        },
        {
            "source_id": "direct_sushiswap_v3",
            "venue": "sushiswap_v3",
            "source_kind": "direct_dex",
            "launch_contracts": [],
            "trading_contracts": _addresses(SUSHISWAP_V3_FACTORY),
            "market_phases": ["sushiswap_v3"],
            "readiness": "discovery_pending",
            "implementation_evidence": ["hlp.data.v3_launchpad"],
            "blocking_gap": "deterministic direct-launch discovery rule",
        },
    ]
    validate_phase2_source_inventory(rows)
    return rows


def validate_phase2_source_inventory(rows: list[dict]) -> dict:
    """Fail closed on source identity/readiness drift."""
    source_ids = [str(row.get("source_id") or "") for row in rows]
    if not rows or any(not source_id for source_id in source_ids):
        raise ValueError("Phase-2 source inventory contains an empty source id")
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Phase-2 source inventory repeats a source id")

    for row in rows:
        readiness = str(row.get("readiness") or "")
        if readiness not in READINESS_STATES:
            raise ValueError(
                f"unsupported Phase-2 source readiness: {readiness!r}"
            )
        if row.get("source_kind") not in {"launchpad", "direct_dex"}:
            raise ValueError(
                f"unsupported Phase-2 source kind: {row.get('source_kind')!r}"
            )
        for field in ("launch_contracts", "trading_contracts"):
            values = list(row.get(field) or [])
            normalized = [normalize_address(str(value)) for value in values]
            if normalized != values:
                raise ValueError(
                    f"{row['source_id']} {field} are not normalized"
                )
            if len(values) != len(set(values)):
                raise ValueError(
                    f"{row['source_id']} {field} contain duplicates"
                )
        if not list(row.get("market_phases") or []):
            raise ValueError(
                f"{row['source_id']} has no market phase classification"
            )

    counts = {
        state: sum(row["readiness"] == state for row in rows)
        for state in sorted(READINESS_STATES)
    }
    return {
        "version": PHASE2_SOURCE_INVENTORY_VERSION,
        "sources": len(rows),
        "readiness_counts": counts,
        "source_ids": source_ids,
    }
