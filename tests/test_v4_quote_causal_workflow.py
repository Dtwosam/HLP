from pathlib import Path


WORKFLOW = (
    Path(__file__).parents[1]
    / ".github"
    / "workflows"
    / "phase1-pons-v4-quote-fallback-full.yml"
)


def _content() -> str:
    return WORKFLOW.read_text()


def test_v4_quote_full_revalidates_ttwu_causal_witness():
    content = _content()
    assert "validate_v4_usdg_causal_swap_witness" in content
    assert "0xaf313f02e31e8adbc5aabbdfa5b02377" in content
    assert "bfa794089b06c60404a63d1a54b042fa" in content
    assert "witness_block=35_389_234" in content
    assert "SOLIDRPC_PUBLIC_RPC_URL" in content


def test_v4_quote_full_derives_scan_start_from_selected_routes():
    content = _content()
    assert "FIRST_V4_FALLBACK_SWAP" not in content
    expected = 'min(int(row["activation_block"]) for row in routes)'
    assert content.count(expected) >= 3
    assert 'Path("routes/pons-v4-quote-routes.jsonl")' in content
