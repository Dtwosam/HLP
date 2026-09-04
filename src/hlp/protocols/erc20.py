"""Minimal point-in-time ERC-20 state reads."""

from __future__ import annotations

from dataclasses import dataclass

from hlp.config import normalize_address
from hlp.data.rpc import RpcClient
from hlp.protocols.evm import data_words, function_selector, word_address


DECIMALS_SELECTOR = function_selector("decimals()")
TOTAL_SUPPLY_SELECTOR = function_selector("totalSupply()")


@dataclass(frozen=True, slots=True)
class Erc20StaticState:
    token: str
    block_number: int | str
    decimals: int
    total_supply: int


def _single_word(result: str) -> int:
    words = data_words(result)
    if len(words) != 1:
        raise ValueError("expected exactly one ABI return word")
    return words[0]


def read_erc20_static(
    rpc: RpcClient,
    token: str,
    *,
    block: int | str = "latest",
) -> Erc20StaticState:
    token = normalize_address(token)
    decimals = _single_word(rpc.eth_call(token, DECIMALS_SELECTOR, block))
    total_supply = _single_word(rpc.eth_call(token, TOTAL_SUPPLY_SELECTOR, block))
    if decimals > 255:
        raise ValueError(f"invalid ERC-20 decimals: {decimals}")
    return Erc20StaticState(
        token=token,
        block_number=block,
        decimals=decimals,
        total_supply=total_supply,
    )
