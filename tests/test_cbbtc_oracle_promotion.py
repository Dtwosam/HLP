from pathlib import Path


def _workflow(name: str) -> str:
    return (
        Path(__file__).parents[1] / ".github" / "workflows" / name
    ).read_text()


def test_oracle_promotion_extends_canonical_chainlink_coverage():
    promotion = _workflow("phase1-pons-stock-oracle-promote-v2-delta.yml")
    launcher = _workflow("phase1-pons-stock-oracle-promote-v2-delta-one-shot.yml")

    assert "CHAINLINK_PRICED_STATUSES" in promotion
    assert 'phase1-pons-stock-oracle-full' in promotion
    assert '33974681334' in launcher
    assert 'resume-generation: 3' in launcher
    assert 'PONS_CBBTC' in promotion


def test_v2_quote_ownership_treats_native_eth_as_anchor_owned():
    eligibility = _workflow("phase1-pons-v2-lifecycle-eligibility.yml")

    assert "ZERO_ADDRESS" in eligibility
    assert "direct_covered" in eligibility
    assert "ZERO_ADDRESS," in eligibility
