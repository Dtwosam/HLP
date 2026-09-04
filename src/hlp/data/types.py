"""Canonical immutable records used at the ingestion boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RawLog:
    chain_id: int
    block_number: int
    block_hash: str | None
    transaction_hash: str
    transaction_index: int | None
    log_index: int
    address: str
    topics: tuple[str, ...]
    data: str
    removed: bool

    @classmethod
    def from_rpc(cls, chain_id: int, payload: dict[str, Any]) -> "RawLog":
        return cls(
            chain_id=chain_id,
            block_number=int(payload["blockNumber"], 16),
            block_hash=payload["blockHash"].lower(),
            transaction_hash=payload["transactionHash"].lower(),
            transaction_index=int(payload["transactionIndex"], 16),
            log_index=int(payload["logIndex"], 16),
            address=payload["address"].lower(),
            topics=tuple(topic.lower() for topic in payload.get("topics", [])),
            data=payload.get("data", "0x").lower(),
            removed=bool(payload.get("removed", False)),
        )


@dataclass(frozen=True, slots=True)
class TrenchTokenInfo:
    token: str
    curve: str
    creator: str
    quote_token: str
    real_quote_reserves_raw: int
    real_token_reserves_raw: int
    virtual_quote_raw: int
    virtual_token_raw: int
    is_migrating: bool
    is_migrated: bool
    block_number: int


@dataclass(frozen=True, slots=True)
class TrenchEvent:
    event_type: str
    token: str
    actor: str | None
    curve: str | None
    quote_token: str | None
    amount_raw: int | None
    quote_amount_raw: int | None
    protocol_fee_raw: int | None
    extra_fee_raw: int | None
    extra_fee_receiver: str | None
    extra_fee_rate: int | None
    real_quote_reserves_raw: int | None
    real_token_reserves_raw: int | None
    virtual_quote_raw: int | None
    virtual_token_raw: int | None
    name: str | None
    symbol: str | None
    token_uri: str | None
    timestamp: int | None
    block_number: int
    transaction_hash: str
    transaction_index: int | None
    log_index: int


@dataclass(frozen=True, slots=True)
class FlapTokenState:
    token: str
    status: int
    reserve_raw: int
    circulating_supply_raw: int
    price_raw: int
    token_version: int
    r: int
    h: int
    k: int
    dex_supply_thresh_raw: int
    quote_token: str
    native_to_quote_swap_enabled: bool
    extension_id: str
    buy_tax_rate: int
    sell_tax_rate: int
    pool: str
    progress: int
    lp_fee_profile: int
    dex_id: int
    block_number: int


@dataclass(frozen=True, slots=True)
class FlapEvent:
    event_type: str
    token: str
    actor: str | None
    amount_raw: int | None
    quote_amount_raw: int | None
    fee_raw: int | None
    post_price_raw: int | None
    value_raw: int | None
    value2_raw: int | None
    pool: str | None
    name: str | None
    symbol: str | None
    meta: str | None
    block_number: int
    transaction_hash: str
    transaction_index: int | None
    log_index: int


@dataclass(frozen=True, slots=True)
class InstantV3Launch:
    venue: str
    factory: str
    token: str
    deployer: str
    dex_factory: str
    pair_token: str
    pool: str
    dex_id: int
    launch_config_id: int
    position_id: int
    restrictions_end_block: int
    initial_buy_amount: int
    block_number: int
    transaction_hash: str
    transaction_index: int | None
    log_index: int


@dataclass(frozen=True, slots=True)
class PonsLaunch:
    version: str
    token: str
    deployer: str
    pair_token: str
    block_number: int
    transaction_hash: str
    transaction_index: int | None
    log_index: int
    curve: str | None = None
    pool: str | None = None
    launch_config_id: int | None = None
    graduation_threshold: int | None = None
    dex_factory: str | None = None
    dex_id: int | None = None
    position_id: int | None = None
    restrictions_end_block: int | None = None
    initial_buy_amount: int | None = None


@dataclass(frozen=True, slots=True)
class NoxaLaunchConfig:
    config_id: int
    pair_token: str
    dex_id: int
    initial_tick: int
    supply: int
    max_wallet_bps: int
    max_tx_bps: int
    restriction_blocks: int
    buy_pair_hop_fee: int
    enabled: bool
    extension_words: tuple[int, ...]
    block_number: int


@dataclass(frozen=True, slots=True)
class NoxaLaunchedToken:
    token: str
    deployer: str
    paired_token: str
    position_manager: str
    position_id: int
    dex_id: int
    launch_config_id: int
    restrictions_end_block: int
    supply: int
    block_number: int


@dataclass(frozen=True, slots=True)
class PonsV1LaunchConfig:
    action: str
    config_id: int
    pair_token: str
    graduation_threshold: int
    initial_tick: int
    supply: int
    max_wallet_bps: int
    max_tx_bps: int
    restriction_blocks: int
    reserved_fee: int
    enabled: bool
    router_requires_deadline: bool
    block_number: int
    transaction_hash: str
    transaction_index: int | None
    log_index: int


@dataclass(frozen=True, slots=True)
class PonsV2LaunchConfig:
    action: str
    config_id: int
    supply: int
    curve_fee_bps: int
    phantom_quote: int
    graduation_threshold: int
    pool_fee: int
    tick_spacing: int
    enabled: bool
    block_number: int
    transaction_hash: str
    transaction_index: int | None
    log_index: int


@dataclass(frozen=True, slots=True)
class PonsV2PairEconomics:
    pair_token: str
    phantom_quote: int
    graduation_threshold: int
    decimals: int
    block_number: int
    transaction_hash: str
    transaction_index: int | None
    log_index: int


@dataclass(frozen=True, slots=True)
class CurveBuyback:
    curve: str
    quote_spent: int
    tokens_locked: int
    block_number: int
    transaction_hash: str
    transaction_index: int | None
    log_index: int


@dataclass(frozen=True, slots=True)
class PonsV2PoolGraduation:
    token: str
    position_id: int
    token_amount: int
    pair_token_amount: int
    block_number: int
    transaction_hash: str
    transaction_index: int | None
    log_index: int


@dataclass(frozen=True, slots=True)
class CurveTrade:
    token: str
    curve: str
    side: str
    actor: str
    recipient: str
    quote_amount: int
    token_amount: int
    fee: int
    tax: int
    block_number: int
    transaction_hash: str
    transaction_index: int | None
    log_index: int


@dataclass(frozen=True, slots=True)
class V3PoolCreated:
    factory: str
    token0: str
    token1: str
    fee: int
    tick_spacing: int
    pool: str
    block_number: int
    transaction_hash: str
    transaction_index: int | None
    log_index: int


@dataclass(frozen=True, slots=True)
class V4PoolInitialized:
    pool_manager: str
    pool_id: str
    currency0: str
    currency1: str
    fee: int
    tick_spacing: int
    hooks: str
    sqrt_price_x96: int
    tick: int
    block_number: int
    transaction_hash: str
    transaction_index: int | None
    log_index: int


@dataclass(frozen=True, slots=True)
class V3Swap:
    pool: str
    sender: str
    recipient: str
    amount0: int
    amount1: int
    sqrt_price_x96: int
    liquidity: int
    tick: int
    block_number: int
    transaction_hash: str
    transaction_index: int | None
    log_index: int


@dataclass(frozen=True, slots=True)
class V4Swap:
    pool_manager: str
    pool_id: str
    sender: str
    amount0: int
    amount1: int
    sqrt_price_x96: int
    liquidity: int
    tick: int
    fee: int
    block_number: int
    transaction_hash: str
    transaction_index: int | None
    log_index: int


@dataclass(frozen=True, slots=True)
class PonsV2PoolRegistration:
    hook: str
    pool_id: str
    token: str
    quote_token: str
    creator: str
    block_number: int
    transaction_hash: str
    transaction_index: int | None
    log_index: int
