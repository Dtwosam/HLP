"""Minimal point-in-time ERC-20 state reads."""

from __future__ import annotations

from dataclasses import dataclass

from hlp.config import normalize_address
from hlp.data.rpc import RpcClient
from hlp.data.types import Erc20Transfer
from hlp.protocols.evm import (
    abi_string_at,
    data_words,
    event_topic,
    function_selector,
    topic_address,
    word_address,
)


DECIMALS_SELECTOR = function_selector("decimals()")
SYMBOL_SELECTOR = function_selector("symbol()")
TOTAL_SUPPLY_SELECTOR = function_selector("totalSupply()")
TRANSFER_SIG = "Transfer(address,address,uint256)"
TRANSFER_TOPIC = event_topic(TRANSFER_SIG)


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



def read_erc20_symbol(
    rpc: RpcClient,
    token: str,
    *,
    block: int | str = "latest",
) -> str:
    """Read ERC-20 symbol(), supporting standard string and legacy bytes32."""
    token = normalize_address(token)
    result = rpc.eth_call(token, SYMBOL_SELECTOR, block)
    try:
        symbol = abi_string_at(result, 0)
    except (ValueError, UnicodeDecodeError):
        raw = result.removeprefix("0x")
        if len(raw) != 64:
            raise ValueError("unexpected ERC-20 symbol() return encoding")
        symbol = bytes.fromhex(raw).rstrip(b"\x00").decode("utf-8")
    symbol = symbol.strip()
    if not symbol:
        raise ValueError("ERC-20 symbol is empty")
    return symbol


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



def decode_erc20_transfer(log) -> Erc20Transfer:
    if not log.topics or log.topics[0] != TRANSFER_TOPIC:
        raise ValueError("not an ERC20 Transfer event")
    if len(log.topics) != 3:
        raise ValueError("unexpected ERC20 Transfer topic count")
    words = data_words(log.data)
    if len(words) != 1:
        raise ValueError("unexpected ERC20 Transfer data length")
    return Erc20Transfer(
        token=log.address,
        from_address=topic_address(log.topics[1]),
        to_address=topic_address(log.topics[2]),
        value_raw=words[0],
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
    )
