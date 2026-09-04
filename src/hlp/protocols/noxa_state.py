"""NOXA point-in-time launch-factory state reads."""

from __future__ import annotations

from hlp.config import NOXA_LAUNCH_FACTORY, normalize_address
from hlp.data.rpc import RpcClient
from hlp.data.types import NoxaLaunchConfig
from hlp.protocols.evm import data_words, function_selector, signed_word, word_address


GET_LAUNCH_CONFIG_SELECTOR = function_selector("getLaunchConfig(uint256)")


def _uint_arg(value: int) -> str:
    if value < 0 or value >= 1 << 256:
        raise ValueError("uint256 argument out of range")
    return f"{value:064x}"


def read_noxa_launch_config(
    rpc: RpcClient,
    config_id: int,
    *,
    block: int,
) -> NoxaLaunchConfig:
    words = data_words(
        rpc.eth_call(
            normalize_address(NOXA_LAUNCH_FACTORY),
            GET_LAUNCH_CONFIG_SELECTOR + _uint_arg(config_id),
            block,
        )
    )
    if len(words) != 9:
        raise ValueError(
            f"unexpected NOXA getLaunchConfig result length: {len(words)}"
        )
    return NoxaLaunchConfig(
        config_id=config_id,
        pair_token=word_address(words[0]),
        dex_id=words[1],
        initial_tick=signed_word(words[2], bits=24),
        supply=words[3],
        max_wallet_bps=words[4],
        max_tx_bps=words[5],
        restriction_blocks=words[6],
        buy_pair_hop_fee=words[7],
        enabled=bool(words[8]),
        block_number=block,
    )
