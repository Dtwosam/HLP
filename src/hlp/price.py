"""Deterministic price and market-cap proxy math."""

from __future__ import annotations

from decimal import Decimal, localcontext


Q192 = 1 << 192


def human_amount(raw: int, decimals: int) -> Decimal:
    if raw < 0:
        raise ValueError("token amount cannot be negative")
    if decimals < 0 or decimals > 255:
        raise ValueError("invalid decimals")
    return Decimal(raw) / (Decimal(10) ** decimals)


def sqrt_price_x96_token1_per_token0(
    sqrt_price_x96: int,
    *,
    decimals0: int,
    decimals1: int,
) -> Decimal:
    """Return human token1 units per one human token0 unit."""
    if sqrt_price_x96 <= 0:
        raise ValueError("sqrt_price_x96 must be positive")
    with localcontext() as ctx:
        ctx.prec = 80
        raw_ratio = (Decimal(sqrt_price_x96) ** 2) / Decimal(Q192)
        decimal_adjustment = (Decimal(10) ** decimals0) / (Decimal(10) ** decimals1)
        return +(raw_ratio * decimal_adjustment)


def v3_v4_quote_per_token(
    sqrt_price_x96: int,
    *,
    token_is_token0: bool,
    token_decimals: int,
    quote_decimals: int,
) -> Decimal:
    if token_is_token0:
        return sqrt_price_x96_token1_per_token0(
            sqrt_price_x96,
            decimals0=token_decimals,
            decimals1=quote_decimals,
        )
    token1_per_token0 = sqrt_price_x96_token1_per_token0(
        sqrt_price_x96,
        decimals0=quote_decimals,
        decimals1=token_decimals,
    )
    if token1_per_token0 == 0:
        raise ZeroDivisionError("pool price is zero")
    return Decimal(1) / token1_per_token0


def curve_execution_quote_per_token(
    *,
    quote_raw: int,
    token_raw: int,
    quote_decimals: int,
    token_decimals: int,
) -> Decimal:
    if quote_raw < 0 or token_raw <= 0:
        raise ValueError("invalid curve trade amounts")
    quote = human_amount(quote_raw, quote_decimals)
    token = human_amount(token_raw, token_decimals)
    return quote / token


def market_cap_proxy_usd(
    *,
    token_price_in_quote: Decimal,
    quote_usd: Decimal,
    total_supply_raw: int,
    token_decimals: int,
) -> Decimal:
    """FDV-style chart market-cap proxy used for HLP's $100k universe rule."""
    if token_price_in_quote < 0 or quote_usd < 0:
        raise ValueError("prices cannot be negative")
    supply = human_amount(total_supply_raw, token_decimals)
    return token_price_in_quote * quote_usd * supply



def constant_product_spot_quote_per_token(
    *,
    quote_reserve_raw: int,
    token_reserve_raw: int,
    quote_decimals: int,
    token_decimals: int,
) -> Decimal:
    """Human quote units per human token from constant-product reserves."""
    if quote_reserve_raw <= 0 or token_reserve_raw <= 0:
        raise ValueError("curve reserves must be positive")
    quote = human_amount(quote_reserve_raw, quote_decimals)
    token = human_amount(token_reserve_raw, token_decimals)
    return quote / token
