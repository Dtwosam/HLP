"""pools.fun persistent instant-V3 launch registry."""

from __future__ import annotations

from typing import Iterable

from hlp.data.types import PoolsFunLaunch


POOLS_FUN_FIXED_SUPPLY_RAW = 1_000_000_000 * 10**18


def build_pools_fun_registry(
    launches: Iterable[PoolsFunLaunch],
) -> list[dict]:
    output = []
    seen_tokens: set[str] = set()
    seen_pools: set[str] = set()
    for launch in launches:
        token = launch.token.lower()
        pool = launch.pool.lower()
        quote = launch.paired_asset.lower()
        if token in seen_tokens:
            raise ValueError(f"duplicate pools.fun token launch: {token}")
        if pool in seen_pools:
            raise ValueError(f"duplicate pools.fun launch pool: {pool}")
        if token == quote:
            raise ValueError(f"pools.fun token equals quote asset: {token}")
        seen_tokens.add(token)
        seen_pools.add(pool)
        output.append(
            {
                "venue": "pools.fun",
                "launch_kind": "instant_sushi_v3",
                "token": token,
                "pool": pool,
                "quote_token": quote,
                "creator": launch.creator.lower(),
                "deployer": launch.deployer.lower(),
                "fee_recipient": launch.fee_recipient.lower(),
                "start_tick": launch.start_tick,
                "metadata_uri": launch.metadata_uri,
                "dev_buy_amount_out": launch.dev_buy_amount_out,
                "supply_raw": POOLS_FUN_FIXED_SUPPLY_RAW,
                "token_decimals": 18,
                "launch_block": launch.block_number,
                "launch_transaction_hash": launch.transaction_hash,
                "launch_transaction_index": launch.transaction_index,
                "launch_log_index": launch.log_index,
            }
        )
    output.sort(key=lambda row: (row["launch_block"], row["token"]))
    return output



def attach_pools_fun_initializations(
    registry_rows: Iterable[dict],
    initialize_rows: Iterable[dict],
) -> list[dict]:
    """Join each pools.fun launch to its exact Sushi V3 Initialize event."""
    registry = [dict(row) for row in registry_rows]
    by_pool: dict[str, dict] = {}
    for row in registry:
        pool = str(row["pool"]).lower()
        if pool in by_pool:
            raise ValueError(f"duplicate pools.fun registry pool: {pool}")
        by_pool[pool] = row

    initializes: dict[str, dict] = {}
    for raw in initialize_rows:
        row = dict(raw)
        pool = str(row["pool"]).lower()
        if pool not in by_pool:
            continue
        if pool in initializes:
            raise ValueError(
                f"multiple V3 Initialize events for pools.fun pool: {pool}"
            )
        initializes[pool] = row

    missing = sorted(set(by_pool) - set(initializes))
    if missing:
        raise ValueError(
            "pools.fun registry pools missing V3 Initialize: "
            + ", ".join(missing[:10])
        )

    output = []
    for row in registry:
        pool = str(row["pool"]).lower()
        init = initializes[pool]
        launch_block = int(row["launch_block"])
        initialize_block = int(init["block_number"])
        if initialize_block < launch_block:
            raise ValueError(
                f"pools.fun Initialize predates launch block: {pool}"
            )
        item = dict(row)
        item.update({
            "initialize_block": initialize_block,
            "initialize_transaction_hash": str(
                init["transaction_hash"]
            ).lower(),
            "initialize_transaction_index": init.get(
                "transaction_index"
            ),
            "initialize_log_index": int(init["log_index"]),
            "initial_sqrt_price_x96": int(init["sqrt_price_x96"]),
            "initial_tick": int(init["tick"]),
        })
        output.append(item)

    output.sort(
        key=lambda row: (
            int(row["launch_block"]),
            row["token"],
        )
    )
    return output
