"""pools.trade instant-launch registry assembly."""

from __future__ import annotations

from typing import Iterable

from hlp.data.types import (
    PoolsTradeTokenCreated,
    PoolsTradeTokenDistributed,
    PoolsTradeTokenLaunched,
)


ZERO_ADDRESS = "0x" + "00" * 20


def build_pools_trade_instant_registry(
    created_rows: Iterable[PoolsTradeTokenCreated],
    distributed_rows: Iterable[PoolsTradeTokenDistributed],
    launched_rows: Iterable[PoolsTradeTokenLaunched],
) -> list[dict]:
    """Join the Uniswap launcher, distribution and instant strategy tapes.

    Only completed instant launches are returned. Crowd Launch creations that
    do not emit InstantLaunchStrategy.TokenLaunched remain outside this
    registry and are handled by the auction adapter.
    """
    created = {}
    for row in created_rows:
        token = row.token.lower()
        if token in created:
            raise ValueError(f"duplicate pools.trade TokenCreated: {token}")
        created[token] = row

    launched = {}
    for row in launched_rows:
        token = row.token.lower()
        if token in launched:
            raise ValueError(f"duplicate pools.trade TokenLaunched: {token}")
        if token not in {row.currency0.lower(), row.currency1.lower()}:
            raise ValueError(f"launched token absent from PoolKey: {token}")
        launched[token] = row

    distributions: dict[str, PoolsTradeTokenDistributed] = {}
    for row in distributed_rows:
        token = row.token.lower()
        if token not in created:
            continue
        if token in distributions:
            raise ValueError(f"multiple pools.trade token distributions: {token}")
        distributions[token] = row

    output = []
    for token, launch in launched.items():
        creation = created.get(token)
        distribution = distributions.get(token)
        if creation is None:
            raise ValueError(f"TokenLaunched missing TokenCreated: {token}")
        if distribution is None:
            raise ValueError(f"TokenLaunched missing token distribution: {token}")
        if distribution.strategy.lower() != launch.strategy.lower():
            raise ValueError(
                f"pools.trade distribution/launch strategy mismatch: {token}"
            )
        quote = (
            launch.currency1.lower()
            if launch.currency0.lower() == token
            else launch.currency0.lower()
        )
        output.append(
            {
                "venue": "pools.trade",
                "launch_kind": "instant_v4",
                "token": token,
                "quote_token": quote,
                "supply_raw": distribution.amount_raw,
                "launcher": creation.launcher.lower(),
                "strategy": launch.strategy.lower(),
                "pool_id": launch.pool_id.lower(),
                "currency0": launch.currency0.lower(),
                "currency1": launch.currency1.lower(),
                "fee": launch.fee,
                "tick_spacing": launch.tick_spacing,
                "hooks": launch.hooks.lower(),
                "final_position_recipient": launch.final_position_recipient.lower(),
                "created_block": creation.block_number,
                "created_transaction_hash": creation.transaction_hash,
                "created_transaction_index": creation.transaction_index,
                "created_log_index": creation.log_index,
                "launch_block": launch.block_number,
                "launch_transaction_hash": launch.transaction_hash,
                "launch_transaction_index": launch.transaction_index,
                "launch_log_index": launch.log_index,
            }
        )
    output.sort(key=lambda row: (row["launch_block"], row["token"]))
    return output
