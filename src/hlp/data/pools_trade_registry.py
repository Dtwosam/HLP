"""pools.trade instant-launch registry assembly."""

from __future__ import annotations

from typing import Iterable

from hlp.data.types import (
    PoolsTradeLbpInitializerCreated,
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



def build_pools_trade_lbp_registry(
    created_rows: Iterable[PoolsTradeTokenCreated],
    distributed_rows: Iterable[PoolsTradeTokenDistributed],
    initializer_rows: Iterable[PoolsTradeLbpInitializerCreated],
) -> list[dict]:
    """Join Crowd Launch creation/distribution to immutable LBP parameters.

    This registry freezes launch identity and supply only. Auction/LBP price
    reconstruction remains a separate adapter and is not inferred here.
    """
    created: dict[str, PoolsTradeTokenCreated] = {}
    for row in created_rows:
        token = row.token.lower()
        if token in created:
            raise ValueError(f"duplicate pools.trade TokenCreated: {token}")
        created[token] = row

    initializers: dict[str, PoolsTradeLbpInitializerCreated] = {}
    for row in initializer_rows:
        token = row.token.lower()
        if token in initializers:
            raise ValueError(
                f"multiple pools.trade LBP initializers for token: {token}"
            )
        if row.currency.lower() == token:
            raise ValueError(
                f"pools.trade LBP token equals quote currency: {token}"
            )
        initializers[token] = row

    distributions: dict[tuple[str, str], PoolsTradeTokenDistributed] = {}
    for row in distributed_rows:
        key = (row.token.lower(), row.strategy.lower())
        if key in distributions:
            raise ValueError(
                "multiple pools.trade distributions for token/strategy: "
                f"{key[0]} {key[1]}"
            )
        distributions[key] = row

    output: list[dict] = []
    for token, init in initializers.items():
        creation = created.get(token)
        if creation is None:
            raise ValueError(
                f"LBP InitializerCreated missing TokenCreated: {token}"
            )
        distribution = distributions.get(
            (token, init.strategy.lower())
        )
        if distribution is None:
            raise ValueError(
                f"LBP InitializerCreated missing matching distribution: {token}"
            )
        supply_raw = int(distribution.amount_raw)
        reserved_raw = int(init.reserved_token_amount_for_lp)
        if supply_raw <= 0:
            raise ValueError(
                f"pools.trade LBP has non-positive token supply: {token}"
            )
        if reserved_raw < 0 or reserved_raw > supply_raw:
            raise ValueError(
                "pools.trade LBP reserved LP allocation exceeds supply: "
                f"{token}"
            )
        if int(init.migration_block) <= int(init.block_number):
            raise ValueError(
                f"pools.trade LBP migration block is not future: {token}"
            )
        if int(init.block_number) < int(creation.block_number):
            raise ValueError(
                f"pools.trade LBP initializer precedes token creation: {token}"
            )
        if int(distribution.block_number) < int(creation.block_number):
            raise ValueError(
                f"pools.trade LBP distribution precedes token creation: {token}"
            )

        output.append(
            {
                "venue": "pools.trade",
                "launch_kind": "crowd_lbp",
                "token": token,
                "quote_token": init.currency.lower(),
                "supply_raw": supply_raw,
                "launcher": creation.launcher.lower(),
                "strategy": init.strategy.lower(),
                "initializer": init.initializer.lower(),
                "migration_block": int(init.migration_block),
                "reserved_token_amount_for_lp": reserved_raw,
                "recipient": init.recipient.lower(),
                "position_recipient": init.position_recipient.lower(),
                "pool_fee": int(init.pool_fee),
                "pool_tick_spacing": int(init.pool_tick_spacing),
                "pool_hook": init.pool_hook.lower(),
                "created_block": int(creation.block_number),
                "created_transaction_hash": creation.transaction_hash.lower(),
                "created_transaction_index": creation.transaction_index,
                "created_log_index": int(creation.log_index),
                "distribution_block": int(distribution.block_number),
                "distribution_transaction_hash": (
                    distribution.transaction_hash.lower()
                ),
                "distribution_transaction_index": (
                    distribution.transaction_index
                ),
                "distribution_log_index": int(distribution.log_index),
                "initializer_block": int(init.block_number),
                "initializer_transaction_hash": (
                    init.transaction_hash.lower()
                ),
                "initializer_transaction_index": init.transaction_index,
                "initializer_log_index": int(init.log_index),
            }
        )

    output.sort(
        key=lambda row: (
            row["initializer_block"],
            row["token"],
        )
    )
    return output
