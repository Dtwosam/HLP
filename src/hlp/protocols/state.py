"""Point-in-time Uniswap V3 pool state reads."""

from __future__ import annotations

from dataclasses import dataclass

from hlp.config import normalize_address
from hlp.data.rpc import RpcClient
from hlp.protocols.evm import data_words, function_selector, signed_word, word_address


TOKEN0_SELECTOR = function_selector("token0()")
TOKEN1_SELECTOR = function_selector("token1()")
SLOT0_SELECTOR = function_selector("slot0()")


@dataclass(frozen=True, slots=True)
class V3PoolStaticState:
    pool: str
    token0: str
    token1: str


@dataclass(frozen=True, slots=True)
class V3Slot0:
    sqrt_price_x96: int
    tick: int


def read_v3_pool_static(
    rpc: RpcClient,
    pool: str,
    *,
    block: int | str = "latest",
) -> V3PoolStaticState:
    pool = normalize_address(pool)
    token0_words = data_words(rpc.eth_call(pool, TOKEN0_SELECTOR, block))
    token1_words = data_words(rpc.eth_call(pool, TOKEN1_SELECTOR, block))
    if len(token0_words) != 1 or len(token1_words) != 1:
        raise ValueError("unexpected V3 token0/token1 ABI result")
    return V3PoolStaticState(
        pool=pool,
        token0=word_address(token0_words[0]),
        token1=word_address(token1_words[0]),
    )


def read_v3_slot0(
    rpc: RpcClient,
    pool: str,
    *,
    block: int | str = "latest",
) -> V3Slot0:
    words = data_words(rpc.eth_call(normalize_address(pool), SLOT0_SELECTOR, block))
    if len(words) < 2:
        raise ValueError("unexpected V3 slot0 ABI result")
    return V3Slot0(
        sqrt_price_x96=words[0],
        tick=signed_word(words[1]),
    )
