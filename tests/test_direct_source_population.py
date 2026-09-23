import pytest

from hlp.data.direct_selector import (
    DIRECT_SELECTOR_FREEZE_VERSION,
    DIRECT_SELECTOR_VERSION,
)
from hlp.data.direct_source_population import (
    DIRECT_SOURCE_POPULATION_VERSION,
    build_direct_source_populations,
)


TOKEN = "0x" + "11" * 20
OTHER = "0x" + "22" * 20


def handoff():
    return {
        "version": "phase2-direct-launch-population-handoff-v2",
        "snapshot_head_block": 100,
        "direct_source_ids": [
            "direct_uniswap_v3",
            "direct_sushiswap_v3",
            "direct_uniswap_v4",
        ],
        "direct_launch_candidate_markets": 2,
        "direct_launch_candidate_tokens": 2,
        "direct_launch_population_conclusive": True,
        "selector_freeze_ready": False,
        "source_coverage_complete": False,
    }


def selector():
    return {
        "version": DIRECT_SELECTOR_FREEZE_VERSION,
        "snapshot_head_block": 100,
        "selector_version": DIRECT_SELECTOR_VERSION,
        "selection_rule_frozen": True,
        "source_coverage_complete": False,
    }


def row(source_id, token, market, block):
    result = {
        "source_id": source_id,
        "venue": "uniswap_v3",
        "token": token,
        "initialize_block": block,
        "direct_launch_classification": "conclusive_direct_launch",
        "direct_launch_attribution_complete": True,
        "source_coverage_complete": False,
    }
    if source_id == "direct_uniswap_v4":
        result["pool_id"] = market
    else:
        result["pool"] = market
    return result


def test_build_direct_source_populations_groups_without_selecting_market():
    rows, summary = build_direct_source_populations(
        [
            row(
                "direct_uniswap_v3",
                TOKEN,
                "0x" + "33" * 20,
                10,
            ),
            row(
                "direct_uniswap_v4",
                OTHER,
                "0x" + "44" * 32,
                20,
            ),
        ],
        handoff(),
        selector(),
    )

    assert len(rows["direct_uniswap_v3"]) == 1
    assert len(rows["direct_uniswap_v4"]) == 1
    assert rows["direct_sushiswap_v3"] == []
    assert rows["direct_uniswap_v3"][0][
        "canonical_selector_frozen"
    ] is True
    assert rows["direct_uniswap_v3"][0][
        "canonical_market_selected"
    ] is False
    assert summary["version"] == DIRECT_SOURCE_POPULATION_VERSION
    assert summary["selector_rule_frozen"] is True
    assert summary["canonical_market_selection_applied"] is False
    assert summary["source_coverage_complete"] is False


def test_direct_source_population_requires_frozen_selector():
    frozen = selector()
    frozen["selection_rule_frozen"] = False

    with pytest.raises(ValueError, match="selector is not frozen"):
        build_direct_source_populations(
            [
                row(
                    "direct_uniswap_v3",
                    TOKEN,
                    "0x" + "33" * 20,
                    10,
                )
            ],
            {
                **handoff(),
                "direct_launch_candidate_markets": 1,
                "direct_launch_candidate_tokens": 1,
            },
            frozen,
        )


def test_direct_source_population_rejects_snapshot_mismatch():
    frozen = selector()
    frozen["snapshot_head_block"] = 99

    with pytest.raises(ValueError, match="snapshot mismatch"):
        build_direct_source_populations([], {
            **handoff(),
            "direct_launch_candidate_markets": 0,
            "direct_launch_candidate_tokens": 0,
        }, frozen)
