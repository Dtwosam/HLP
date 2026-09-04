"""Point-in-time Pons factory state reads."""

from __future__ import annotations

from hlp.config import PONS_V1_FACTORY, normalize_address
from hlp.data.rpc import RpcClient
from hlp.data.types import PonsV1LaunchConfig
from hlp.protocols.evm import data_words, function_selector, signed_word, word_address


GET_V1_LAUNCH_CONFIG_SELECTOR = function_selector("getLaunchConfig(uint256)")


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
