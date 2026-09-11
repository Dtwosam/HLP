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
