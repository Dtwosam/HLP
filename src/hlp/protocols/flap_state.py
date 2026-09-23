"""Point-in-time Flap Portal token state reads."""

from __future__ import annotations

from hlp.config import FLAP_PORTAL, normalize_address
from hlp.data.rpc import RpcClient
from hlp.data.types import FlapTokenState
from hlp.protocols.evm import data_words, function_selector, word_address


GET_TOKEN_V8_SELECTOR = function_selector("getTokenV8(address)")


def _address_arg(address: str) -> str:
    return normalize_address(address).removeprefix("0x").rjust(64, "0")


def read_flap_token_v8(
    rpc: RpcClient,
    token: str,
    *,
    block: int,
) -> FlapTokenState:
    token = normalize_address(token)
    words = data_words(
        rpc.eth_call(
            normalize_address(FLAP_PORTAL),
            GET_TOKEN_V8_SELECTOR + _address_arg(token),
            block,
        )
    )
    if len(words) != 18:
        raise ValueError(f"unexpected Flap getTokenV8 result length: {len(words)}")
    return FlapTokenState(
        token=token,
        status=words[0],
        reserve_raw=words[1],
        circulating_supply_raw=words[2],
        price_raw=words[3],
        token_version=words[4],
        r=words[5],
        h=words[6],
        k=words[7],
        dex_supply_thresh_raw=words[8],
        quote_token=word_address(words[9]),
        native_to_quote_swap_enabled=bool(words[10]),
        extension_id="0x" + f"{words[11]:064x}",
        buy_tax_rate=words[12],
        sell_tax_rate=words[13],
        pool=word_address(words[14]),
        progress=words[15],
        lp_fee_profile=words[16],
        dex_id=words[17],
        block_number=block,
    )
