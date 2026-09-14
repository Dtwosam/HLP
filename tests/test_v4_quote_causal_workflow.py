from pathlib import Path

import pytest

import hlp.data.quote_causality as qc


WORKFLOW = (
    Path(__file__).parents[1]
    / ".github"
    / "workflows"
    / "phase1-pons-v4-quote-fallback-full.yml"
)
MERGE_WORKFLOW = (
    Path(__file__).parents[1]
    / ".github"
    / "workflows"
    / "phase1-pons-quote-fallback-full.yml"
)

SKHY = "0x84cab63bc87912e71ad199ff14a0ba45de68fef8"
OTHER = "0x" + "11" * 20
OTHER_V4 = "0x" + "22" * 20


def _content() -> str:
    return WORKFLOW.read_text()


def test_v4_quote_full_revalidates_ttwu_causal_witness():
    content = _content()
    assert "validate_v4_usdg_causal_swap_witness" in content
    assert "0xaf313f02e31e8adbc5aabbdfa5b02377" in content
    assert "bfa794089b06c60404a63d1a54b042fa" in content
    assert "witness_block=35_389_234" in content
    assert "SOLIDRPC_PUBLIC_RPC_URL" in content


def test_v4_quote_full_promotes_skhy_from_causal_point_state():
    content = _content()
    assert "select_v4_usdg_causal_state_witness" in content
    assert "0x4c4a74bd3b9a224b06379c60af2843c" in content
    assert "2238156446c8003e3796456a3192f5e6b" in content
    assert '"initialize_block": 33_534_851' in content
    assert '"fee": 33_000' in content
    assert '"tick_spacing": 330' in content
    assert "SKHY causal V4 point state" in content
    assert "RIVN must remain delayed" in content


def test_skhy_point_state_uses_verified_public_rpc_path():
    plan = _content().split("\n  shard:", 1)[0]
    assert "solidrpc_public_skhy_causal_point_state" in plan
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in plan
    assert "SOLIDRPC_AUTH_RPC_URL" not in plan


def test_v4_quote_full_derives_scan_start_from_selected_routes():
    content = _content()
    assert "FIRST_V4_FALLBACK_SWAP" not in content
    expected = 'min(int(row["activation_block"]) for row in routes)'
    assert content.count(expected) >= 3
    assert 'Path("routes/pons-v4-quote-routes.jsonl")' in content


def test_delayed_v3_skhy_can_be_superseded_only_by_causal_v4():
    result = qc.supersede_delayed_v3_quote_ownership(
        v3_routes=[
            {
                "quote_token": SKHY,
                "route_type": "uniswap_v3_direct_weth_delayed",
            },
            {
                "quote_token": OTHER,
                "route_type": "uniswap_v3_direct_usdg",
            },
        ],
        v3_initial=[{"quote_token": OTHER, "usd_price": "1"}],
        v3_updates=[
            {"quote_token": SKHY, "block_number": 200},
            {"quote_token": OTHER, "block_number": 201},
        ],
        v4_routes=[
            {
                "quote_token": SKHY,
                "route_type": "uniswap_v4_direct_usdg_point_state",
                "causal_state_block": 99,
            },
            {
                "quote_token": OTHER_V4,
                "route_type": "uniswap_v4_direct_usdg_delayed",
                "causal_state_block": None,
            },
        ],
        token=SKHY,
    )
    assert [row["quote_token"] for row in result["v3_routes"]] == [OTHER]
    assert [row["quote_token"] for row in result["v3_initial"]] == [OTHER]
    assert [row["quote_token"] for row in result["v3_updates"]] == [OTHER]
    assert result["superseded_tokens"] == [SKHY]


def test_delayed_v3_skhy_is_not_dropped_for_delayed_v4():
    with pytest.raises(ValueError, match="causal V4"):
        qc.supersede_delayed_v3_quote_ownership(
            v3_routes=[{
                "quote_token": SKHY,
                "route_type": "uniswap_v3_direct_weth_delayed",
            }],
            v3_initial=[],
            v3_updates=[{"quote_token": SKHY, "block_number": 200}],
            v4_routes=[{
                "quote_token": SKHY,
                "route_type": "uniswap_v4_direct_usdg_delayed",
                "causal_state_block": None,
            }],
            token=SKHY,
        )


def test_causal_v3_state_is_never_silently_superseded():
    with pytest.raises(ValueError, match="causal V3 state"):
        qc.supersede_delayed_v3_quote_ownership(
            v3_routes=[{
                "quote_token": SKHY,
                "route_type": "uniswap_v3_direct_weth_delayed",
            }],
            v3_initial=[{"quote_token": SKHY, "usd_price": "1"}],
            v3_updates=[],
            v4_routes=[{
                "quote_token": SKHY,
                "route_type": "uniswap_v4_direct_usdg_point_state",
                "causal_state_block": 99,
            }],
            token=SKHY,
        )


def test_generic_merge_uses_explicit_skhy_ownership_supersession():
    content = MERGE_WORKFLOW.read_text()
    assert "supersede_delayed_v3_quote_ownership" in content
    assert "effective-v3" in content
    assert "skhy_v3_superseded_by_causal_v4" in content
