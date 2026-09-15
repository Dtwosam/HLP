from pathlib import Path


ROOT = Path(__file__).parents[1]
FULL = ROOT / ".github/workflows/phase1-pons-v4-quote-fallback-full.yml"
RECOVERY = ROOT / ".github/workflows/phase1-pons-v4-quote-fallback-recover-gaps.yml"
OFFICIAL = "https://rpc.mainnet.chain.robinhood.com"


def test_v4_quote_full_uses_verified_official_rpc_for_tape_acquisition():
    content = FULL.read_text()
    assert f"ROBINHOOD_ARCHIVE_RPC_URL: {OFFICIAL}" in content


def test_v4_quote_recovery_uses_same_verified_official_rpc():
    content = RECOVERY.read_text()
    assert f"ROBINHOOD_ARCHIVE_RPC_URL: {OFFICIAL}" in content


def test_v4_quote_full_uses_verified_50k_chunks_on_official_rpc():
    content = FULL.read_text()
    assert "CHUNK=50000" in content
    assert "CHUNK=2000" not in content


def test_v4_quote_recovery_uses_verified_50k_chunks_on_official_rpc():
    content = RECOVERY.read_text()
    assert "CHUNK=50000" in content
    assert "CHUNK=2000" not in content
