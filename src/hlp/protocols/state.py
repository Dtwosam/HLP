"""Point-in-time Uniswap V3 pool state reads."""

from __future__ import annotations

from dataclasses import dataclass

from hlp.config import normalize_address
from hlp.data.rpc import RpcClient
from hlp.protocols.evm import data_words, function_selector, signed_word, word_address


TOKEN0_SELECTOR = function_selector("token0()")
TOKEN1_SELECTOR = function_selector("token1()")
SLOT0_SELECTOR = function_selector("slot0()")
LIQUIDITY_SELECTOR = function_selector("liquidity()")
GET_POOL_SELECTOR = function_selector("getPool(address,address,uint24)")


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



def read_v3_liquidity(
    rpc: RpcClient,
    pool: str,
    *,
    block: int | str = "latest",
) -> int:
    """Return active Uniswap V3 liquidity at an exact historical block."""
    words = data_words(
        rpc.eth_call(normalize_address(pool), LIQUIDITY_SELECTOR, block)
    )
    if len(words) != 1:
        raise ValueError("unexpected V3 liquidity ABI result")
    value = int(words[0])
    if value < 0 or value >= 1 << 128:
        raise ValueError("invalid V3 uint128 liquidity")
    return value


def read_v3_factory_pool(
    rpc: RpcClient,
    factory: str,
    *,
    token_a: str,
    token_b: str,
    fee: int,
    block: int | str = "latest",
) -> str | None:
    """Resolve a Uniswap V3 pool from factory state visible at a block."""
    if fee < 0 or fee >= 1 << 24:
        raise ValueError("V3 fee must fit uint24")
    token_a = normalize_address(token_a)
    token_b = normalize_address(token_b)
    if token_a == token_b:
        raise ValueError("V3 pool assets must differ")
    token0, token1 = sorted((token_a, token_b), key=lambda value: int(value, 16))
    calldata = (
        GET_POOL_SELECTOR
        + token0.removeprefix("0x").rjust(64, "0")
        + token1.removeprefix("0x").rjust(64, "0")
        + f"{fee:064x}"
    )
    words = data_words(
        rpc.eth_call(normalize_address(factory), calldata, block)
    )
    if len(words) != 1:
        raise ValueError("unexpected V3 getPool ABI result")
    if words[0] == 0:
        return None
    return word_address(words[0])
