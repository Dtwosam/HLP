"""Point-in-time Pons factory state reads."""

from __future__ import annotations

from hlp.config import PONS_V1_FACTORY, PONS_V2_FACTORY, normalize_address
from hlp.data.rpc import RpcClient
from hlp.data.types import PonsV1LaunchConfig, PonsV2LaunchConfig, PonsV2PairEconomics
from hlp.protocols.evm import data_words, function_selector, signed_word, word_address


GET_V1_LAUNCH_CONFIG_SELECTOR = function_selector("getLaunchConfig(uint256)")
GET_V2_LAUNCH_CONFIG_SELECTOR = GET_V1_LAUNCH_CONFIG_SELECTOR
V2_PAIR_TOKEN_ECONOMICS_SELECTOR = function_selector("pairTokenEconomics(address)")


def _uint_arg(value: int) -> str:
    if value < 0 or value >= 1 << 256:
        raise ValueError("uint256 argument out of range")
    return f"{value:064x}"


def read_v1_launch_config_state(
    rpc: RpcClient,
    config_id: int,
    *,
    block: int,
) -> PonsV1LaunchConfig:
    """Read the V1 launch config as it existed at the end of a historical block."""
    data = GET_V1_LAUNCH_CONFIG_SELECTOR + _uint_arg(config_id)
    words = data_words(
        rpc.eth_call(normalize_address(PONS_V1_FACTORY), data, block)
    )
    if len(words) != 10:
        raise ValueError(
            f"unexpected Pons V1 getLaunchConfig result length: {len(words)}"
        )
    return PonsV1LaunchConfig(
        action="bootstrap",
        config_id=config_id,
        pair_token=word_address(words[0]),
        graduation_threshold=words[1],
        initial_tick=signed_word(words[2], bits=24),
        supply=words[3],
        max_wallet_bps=words[4],
        max_tx_bps=words[5],
        restriction_blocks=words[6],
        reserved_fee=words[7],
        enabled=bool(words[8]),
        router_requires_deadline=bool(words[9]),
        block_number=block,
        transaction_hash="0x" + "00" * 32,
        transaction_index=None,
        log_index=-1,
    )



def _address_arg(address: str) -> str:
    value = normalize_address(address)
    return value.removeprefix("0x").rjust(64, "0")


def read_v2_launch_config_state(
    rpc: RpcClient,
    config_id: int,
    *,
    block: int,
    action: str = "bootstrap",
    transaction_hash: str | None = None,
    transaction_index: int | None = None,
    log_index: int = -1,
) -> PonsV2LaunchConfig:
    data = GET_V2_LAUNCH_CONFIG_SELECTOR + _uint_arg(config_id)
    words = data_words(
        rpc.eth_call(normalize_address(PONS_V2_FACTORY), data, block)
    )
    if len(words) != 7:
        raise ValueError(
            f"unexpected Pons V2 getLaunchConfig result length: {len(words)}"
        )
    return PonsV2LaunchConfig(
        action=action,
        config_id=config_id,
        supply=words[0],
        curve_fee_bps=words[1],
        phantom_quote=words[2],
        graduation_threshold=words[3],
        pool_fee=words[4],
        tick_spacing=signed_word(words[5], bits=24),
        enabled=bool(words[6]),
        block_number=block,
        transaction_hash=transaction_hash or ("0x" + "00" * 32),
        transaction_index=transaction_index,
        log_index=log_index,
    )


def read_v2_pair_token_economics_state(
    rpc: RpcClient,
    pair_token: str,
    *,
    block: int,
) -> PonsV2PairEconomics:
    pair_token = normalize_address(pair_token)
    data = V2_PAIR_TOKEN_ECONOMICS_SELECTOR + _address_arg(pair_token)
    words = data_words(
        rpc.eth_call(normalize_address(PONS_V2_FACTORY), data, block)
    )
    if len(words) != 3:
        raise ValueError(
            f"unexpected Pons V2 pairTokenEconomics result length: {len(words)}"
        )
    if words[2] > 255:
        raise ValueError("invalid Pons V2 pair-token decimals")
    return PonsV2PairEconomics(
        pair_token=pair_token,
        phantom_quote=words[0],
        graduation_threshold=words[1],
        decimals=words[2],
        block_number=block,
        transaction_hash="0x" + "00" * 32,
        transaction_index=None,
        log_index=-1,
    )
