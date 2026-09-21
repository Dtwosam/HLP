"""Doppler Airlock launch registry joined to canonical V4 pools."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from hlp.data.types import DopplerLaunch


def build_doppler_v4_registry(
    launches: Iterable[DopplerLaunch],
    initialize_rows: Iterable[dict],
    *,
    supply_raw_by_asset: dict[str, int],
) -> list[dict]:
    """Join Airlock.Create to the V4 Initialize emitted in the same tx.

    poolOrHook is intentionally not used as pool identity because Doppler's
    initializer variants do not give it one stable semantic. The canonical
    PoolManager Initialize and exact asset/numeraire pair are authoritative.
    """
    inits_by_tx: dict[str, list[dict]] = defaultdict(list)
    for row in initialize_rows:
        inits_by_tx[row["transaction_hash"].lower()].append(row)

    output = []
    seen_assets: set[str] = set()
    seen_pools: set[str] = set()
    for launch in launches:
        asset = launch.asset.lower()
        quote = launch.numeraire.lower()
        if asset in seen_assets:
            raise ValueError(f"duplicate Doppler Airlock asset: {asset}")
        candidates = [
            row
            for row in inits_by_tx.get(launch.transaction_hash.lower(), [])
            if {
                row["currency0"].lower(),
                row["currency1"].lower(),
            } == {asset, quote}
        ]
        if len(candidates) != 1:
            raise ValueError(
                f"Doppler launch expected exactly one same-tx V4 Initialize: "
                f"{asset}, found {len(candidates)}"
            )
        init = candidates[0]
        launch_order = (
            int(launch.block_number),
            -1
            if launch.transaction_index is None
            else int(launch.transaction_index),
            int(launch.log_index),
        )
        initialize_order = (
            int(init["block_number"]),
            -1
            if init.get("transaction_index") is None
            else int(init["transaction_index"]),
            int(init["log_index"]),
        )
        if initialize_order <= launch_order:
            raise ValueError(
                f"Doppler V4 Initialize does not follow Airlock Create: {asset}"
            )
        pool_id = init["pool_id"].lower()
        if pool_id in seen_pools:
            raise ValueError(f"duplicate Doppler pool id: {pool_id}")
        supply = supply_raw_by_asset.get(asset)
        if supply is None or supply <= 0:
            raise KeyError(f"missing Doppler supply for {asset}")
        seen_assets.add(asset)
        seen_pools.add(pool_id)
        output.append({
            "source_id": "doppler",
            "venue": "doppler",
            "source_kind": "launchpad",
            "launch_kind": "airlock_v4",
            "token": asset,
            "quote_token": quote,
            "supply_raw": int(supply),
            "supply_seed_semantics": (
                "launch_block_end_total_supply_same_block_as_initialize"
            ),
            "state_block": int(launch.block_number),
            "pool_id": pool_id,
            "currency0": init["currency0"].lower(),
            "currency1": init["currency1"].lower(),
            "fee": int(init["fee"]),
            "tick_spacing": int(init["tick_spacing"]),
            "hooks": init["hooks"].lower(),
            "initializer": launch.initializer.lower(),
            "pool_or_hook": launch.pool_or_hook.lower(),
            "launch_block": launch.block_number,
            "launch_transaction_hash": launch.transaction_hash,
            "launch_transaction_index": launch.transaction_index,
            "launch_log_index": launch.log_index,
            "initialize_block": int(init["block_number"]),
            "initialize_transaction_hash": init["transaction_hash"],
            "initialize_transaction_index": init.get("transaction_index"),
            "initialize_log_index": int(init["log_index"]),
            "initial_sqrt_price_x96": int(init["sqrt_price_x96"]),
            "initial_tick": int(init["tick"]),
        })
    output.sort(key=lambda row: (row["launch_block"], row["token"]))
    return output
