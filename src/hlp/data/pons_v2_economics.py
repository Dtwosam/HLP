"""Pons V2 deterministic graduation economics.

Source: PonsV2BondingCurve.initialize() reserves
    floor(supply * phantomQuote / (phantomQuote + graduationThreshold))
tokens. The contract comments state this is the exact allocation at which the
real quote reserve reaches the graduation threshold.

These helpers do not label winners or define dumps. They are used only to
screen which launches can possibly approach the user's $100k universe before
graduation and to cross-check raw replay.
"""

from __future__ import annotations

from decimal import Decimal, getcontext


def reserved_tokens_at_graduation(
    *,
    supply_raw: int,
    phantom_quote_raw: int,
    graduation_threshold_raw: int,
) -> int:
    if supply_raw <= 0:
        raise ValueError("supply_raw must be positive")
    if phantom_quote_raw <= 0:
        raise ValueError("phantom_quote_raw must be positive")
    if graduation_threshold_raw <= 0:
        raise ValueError("graduation_threshold_raw must be positive")
    reserved = (
        supply_raw * phantom_quote_raw
        // (phantom_quote_raw + graduation_threshold_raw)
    )
    if reserved <= 0 or reserved >= supply_raw:
        raise ValueError("invalid Pons V2 graduation allocation")
    return reserved


def intended_graduation_market_cap_quote(
    *,
    supply_raw: int,
    phantom_quote_raw: int,
    graduation_threshold_raw: int,
    quote_decimals: int,
) -> Decimal:
    """Return spot FDV at Pons's deterministic graduation allocation.

    Uses the actual integer-rounded reserved token amount used by the
    contract. The intended quote reserve at that point is
    phantomQuote + graduationThreshold.
    """
    if quote_decimals < 0 or quote_decimals > 255:
        raise ValueError("invalid quote_decimals")
    getcontext().prec = max(getcontext().prec, 80)
    reserved = reserved_tokens_at_graduation(
        supply_raw=supply_raw,
        phantom_quote_raw=phantom_quote_raw,
        graduation_threshold_raw=graduation_threshold_raw,
    )
    quote_reserve = phantom_quote_raw + graduation_threshold_raw

    # Raw quote/token spot * raw supply; token decimals cancel. Only the quote
    # asset's decimal scale remains.
    return (
        Decimal(quote_reserve)
        * Decimal(supply_raw)
        / Decimal(reserved)
        / (Decimal(10) ** quote_decimals)
    )


def intended_graduation_market_cap_usd(
    *,
    supply_raw: int,
    phantom_quote_raw: int,
    graduation_threshold_raw: int,
    quote_decimals: int,
    quote_usd: Decimal,
) -> Decimal:
    if quote_usd <= 0:
        raise ValueError("quote_usd must be positive")
    return intended_graduation_market_cap_quote(
        supply_raw=supply_raw,
        phantom_quote_raw=phantom_quote_raw,
        graduation_threshold_raw=graduation_threshold_raw,
        quote_decimals=quote_decimals,
    ) * quote_usd
