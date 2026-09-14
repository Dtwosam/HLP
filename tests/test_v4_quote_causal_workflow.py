from pathlib import Path

import pytest

import hlp.data.quote_causality as qc
from hlp.data.quote_v4_causal_candidates import (
    EXHAUSTIVE_CAUSAL_POINT_STATE_CANDIDATES,
    POOL_MANAGER_DEPLOYMENT_BLOCK,
    RESIDUAL_CAUSAL_HISTORY_SCAN_RUN_ID,
)


WORKFLOW = (
    Path(__file__).parents[1]
    / ".github"
    / "workflows"
    / "phase1-pons-v4-quote-fallback-full.yml"
)
RECOVERY_WORKFLOW = (
    Path(__file__).parents[1]
    / ".github"
    / "workflows"
    / "phase1-pons-v4-quote-fallback-recover-gaps.yml"
)
MERGE_WORKFLOW = (
    Path(__file__).parents[1]
    / ".github"
    / "workflows"
    / "phase1-pons-quote-fallback-full.yml"
)

SKHY = "0x84cab63bc87912e71ad199ff14a0ba45de68fef8"
RIVN = "0xb1bf26c1d20ff267a4f93550d1e0d06ac40a114b"
FIG = "0x41f4267525a8aff329540ef24fd83d9044758b33"
BULL = "0xcef9027c7d6985b85f0ba431125073529a947a68"
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


def test_skhy_point_state_uses_verified_public_rpc_path():
    plan = _content().split("\n  shard:", 1)[0]
    assert "solidrpc_public_skhy_causal_point_state" in plan
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in plan
    assert "SOLIDRPC_AUTH_RPC_URL" not in plan


def test_exhaustive_residual_candidates_are_frozen_from_completed_scan():
    assert RESIDUAL_CAUSAL_HISTORY_SCAN_RUN_ID == 34883018674
    assert POOL_MANAGER_DEPLOYMENT_BLOCK == 9_070
    expected = {
        RIVN: {
            "pool_id": "0xbc98f7458578286c304a6ced4aa33a562f37805f95c26ad391cf02da46dab99e",
            "coverage_to_block": 36_002_594,
            "initialize_events": 7,
            "causal_point_states": 6,
            "activation_liquidity": 25_970_859_276_841,
        },
        FIG: {
            "pool_id": "0x8d7e57e6fca7c6ed5744549b19f35be72c8004ab6b3d12c9dd972e31994c4ba1",
            "coverage_to_block": 52_956_725,
            "initialize_events": 40,
            "causal_point_states": 13,
            "activation_liquidity": 962_439_577_120_207_465,
        },
        BULL: {
            "pool_id": "0x1bda41eb5701e01bb4ff3659e9e614cd92260efa25731ce3d6ee18e1e25e2cd6",
            "coverage_to_block": 54_419_646,
            "initialize_events": 41,
            "causal_point_states": 9,
            "activation_liquidity": 404_061_919_866_128_484,
        },
    }
    assert set(EXHAUSTIVE_CAUSAL_POINT_STATE_CANDIDATES) == set(expected)
    for token, values in expected.items():
        evidence = EXHAUSTIVE_CAUSAL_POINT_STATE_CANDIDATES[token]
        assert evidence["coverage_from_block"] == 9_070
        assert evidence["coverage_complete"] is True
        assert evidence["selection_rule"] == "highest_active_liquidity_then_pool_id"
        for key, value in values.items():
            if key == "pool_id":
                assert evidence["candidate"][key] == value
            else:
                assert evidence[key] == value


def test_v4_quote_full_promotes_all_exhaustively_proven_point_states():
    content = _content()
    assert "EXHAUSTIVE_CAUSAL_POINT_STATE_CANDIDATES" in content
    assert "RIVN must remain delayed" not in content
    for token in (RIVN, FIG, BULL):
        assert token in content
    assert "all five V4 residual routes must be causal at first use" in content
    assert "residual_causal_history_scan_run_id" in content


def test_generic_merge_requires_all_30_causal_initial_states():
    content = MERGE_WORKFLOW.read_text()
    assert "exactly 30 causal initial" in content
    assert "after all five V4 residual promotions" in content
    assert "exactly 27 causal initial" not in content


def test_v4_quote_full_derives_scan_start_from_selected_routes():
    content = _content()
    assert "FIRST_V4_FALLBACK_SWAP" not in content
    expected = 'min(int(row["activation_block"]) for row in routes)'
    assert content.count(expected) >= 3
    assert 'Path("routes/pons-v4-quote-routes.jsonl")' in content


def test_v4_quote_gap_recovery_derives_start_from_frozen_routes():
    content = RECOVERY_WORKFLOW.read_text()
    assert "FIRST_V4_FALLBACK_SWAP" not in content
    expected = 'min(int(row["activation_block"]) for row in routes)'
    assert content.count(expected) >= 2
    assert "routes/pons-v4-quote-routes.jsonl" in content


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
