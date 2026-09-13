import re
from pathlib import Path


def _workflow(name: str) -> str:
    return (
        Path(__file__).parents[1] / ".github" / "workflows" / name
    ).read_text()


def test_oracle_promotion_extends_canonical_chainlink_coverage():
    promotion = _workflow("phase1-pons-cbbtc-oracle-promote.yml")
    launcher = _workflow("phase1-pons-stock-oracle-promote-v2-delta-one-shot.yml")

    assert "CHAINLINK_PRICED_STATUSES" in promotion
    assert "priced_chainlink_crypto_token" in promotion
    assert "0xcec185eb182c47d1ba1efc84e6959e18cd620be4" in promotion
    assert "max-parallel: 2" in promotion
    assert "phase1-pons-stock-oracle-full" in promotion
    assert '33974681334' in launcher
    assert 'resume-generation: 4' in launcher
    assert "phase1-pons-cbbtc-oracle-promote.yml" in launcher


def test_cbbtc_oracle_shards_respect_proven_100k_ceiling():
    promotion = _workflow("phase1-pons-cbbtc-oracle-promote.yml")

    count_match = re.search(r"SHARD_COUNT: '(\d+)'", promotion)
    matrix_match = re.search(r"shard:\s*\[([^\]]+)\]", promotion)
    assert count_match is not None
    assert matrix_match is not None

    shard_count = int(count_match.group(1))
    shards = [int(value.strip()) for value in matrix_match.group(1).split(",")]
    total_blocks = 54_486_035 - 48_515_552 + 1
    largest_shard = (total_blocks + shard_count - 1) // shard_count

    assert largest_shard <= 100_000
    assert shards == list(range(shard_count))
    assert f"assert len(state_files) == {shard_count}" in promotion
    assert f"assert len(update_files) == {shard_count}" in promotion


def test_v2_quote_ownership_treats_native_eth_as_anchor_owned():
    eligibility = _workflow("phase1-pons-v2-lifecycle-eligibility.yml")

    assert 'ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"' in eligibility
    assert "covered = oracle_tokens | fallback_tokens | {WETH, USDG, ZERO_ADDRESS}" in eligibility
