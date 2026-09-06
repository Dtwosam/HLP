from decimal import Decimal

from hlp.data.pons_v2_economics import (
    intended_graduation_market_cap_quote,
    intended_graduation_market_cap_usd,
    reserved_tokens_at_graduation,
)


def test_reserved_tokens_matches_contract_integer_formula():
    supply = 1_000_000_000 * 10**18
    phantom = 1 * 10**18
    threshold = 4 * 10**18
    reserved = reserved_tokens_at_graduation(
        supply_raw=supply,
        phantom_quote_raw=phantom,
        graduation_threshold_raw=threshold,
    )
    assert reserved == 200_000_000 * 10**18


def test_graduation_fdv_uses_quote_scale_and_integer_reserved_amount():
    supply = 1_000_000_000 * 10**18
    phantom = 1 * 10**18
    threshold = 4 * 10**18
    # 5 ETH reserve / 200m tokens = 25e-9 ETH/token; 1B FDV = 25 ETH.
    mcap_quote = intended_graduation_market_cap_quote(
        supply_raw=supply,
        phantom_quote_raw=phantom,
        graduation_threshold_raw=threshold,
        quote_decimals=18,
    )
    assert mcap_quote == Decimal("25")
    assert intended_graduation_market_cap_usd(
        supply_raw=supply,
        phantom_quote_raw=phantom,
        graduation_threshold_raw=threshold,
        quote_decimals=18,
        quote_usd=Decimal("2000"),
    ) == Decimal("50000")
