"""Point-in-time trench.today manager state reads."""

from __future__ import annotations

from hlp.config import TRENCH_MANAGER, normalize_address
from hlp.data.rpc import RpcClient
from hlp.data.types import TrenchTokenInfo
from hlp.protocols.evm import data_words, function_selector, word_address


TOKEN_INFO_SELECTOR = function_selector("tokenInfo(address)")


def _address_arg(address: str) -> str:
    return normalize_address(address).removeprefix("0x").rjust(64, "0")


def read_trench_token_info(
    rpc: RpcClient,
    token: str,
    *,
    block: int,
) -> TrenchTokenInfo:
    token = normalize_address(token)
    words = data_words(
        rpc.eth_call(
            normalize_address(TRENCH_MANAGER),
            TOKEN_INFO_SELECTOR + _address_arg(token),
            block,
        )
    )
    if len(words) != 9:
        raise ValueError(f"unexpected trench tokenInfo result length: {len(words)}")
    return TrenchTokenInfo(
        token=token,
        curve=word_address(words[0]),
        creator=word_address(words[1]),
        quote_token=word_address(words[2]),
        real_quote_reserves_raw=words[3],
        real_token_reserves_raw=words[4],
        virtual_quote_raw=words[5],
        virtual_token_raw=words[6],
        is_migrating=bool(words[7]),
        is_migrated=bool(words[8]),
        block_number=block,
    )
