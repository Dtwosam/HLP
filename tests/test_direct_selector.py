import pytest

from hlp.data.direct_selector import (
    DIRECT_SELECTOR_FREEZE_VERSION,
    DIRECT_SELECTOR_VERSION,
    build_direct_selector_freeze,
)
from hlp.data.market_quality import MARKET_SELECTION_CANDIDATE_VERSION


SHA = "ab" * 32


def evidence():
    return {
        "version": "phase2-direct-market-quality-evidence-v2",
        "chain_id": 4663,
        "snapshot_head_block": 100,
        "sample_tokens": 2,
        "sample_markets": 4,
        "plan_sha256": SHA,
        "quote_registry_sha256": SHA,
        "quote_decimals_sha256": SHA,
        "quote_feed_specs_sha256": SHA,
        "trace_sha256": SHA,
        "candidate_series_sha256": SHA,
        "market_quality_report_sha256": SHA,
        "point_sha256": {
            "direct_uniswap_v3": SHA,
            "direct_sushiswap_v3": SHA,
            "direct_uniswap_v4": SHA,
        },
        "market_quality_report": {
            "selection_rule_frozen": False,
            "causal_trace": {
                "tokens": 2,
                "multi_market_snapshots": 8,
            },
            "candidate_canonical_series": {
                "points": 12,
                "selection_policy_candidate_version": (
                    MARKET_SELECTION_CANDIDATE_VERSION
                ),
                "selection_rule_frozen": False,
                "cross_pool_volume_double_counting_allowed": False,
            },
        },
        "selector_freeze_ready": False,
        "source_coverage_complete": False,
    }


def freeze(row=None):
    return build_direct_selector_freeze(
        evidence() if row is None else row,
        evidence_run_id=123,
        evidence_artifact_digest="sha256:" + SHA,
        evidence_handoff_sha256=SHA,
    )


def test_direct_selector_freeze_is_exact_and_noncoverage():
    row = freeze()

    assert row["version"] == DIRECT_SELECTOR_FREEZE_VERSION
    assert row["selector_version"] == DIRECT_SELECTOR_VERSION
    assert row["selection_rule_frozen"] is True
    assert row["selector_freeze_ready"] is True
    assert row["source_coverage_complete"] is False
    assert row["cross_pool_volume_double_counting_allowed"] is False
    assert row["multi_market_snapshots"] == 8


def test_direct_selector_freeze_requires_competing_market_evidence():
    row = evidence()
    row["market_quality_report"]["causal_trace"][
        "multi_market_snapshots"
    ] = 0

    with pytest.raises(ValueError, match="no competing usable"):
        freeze(row)


def test_direct_selector_freeze_rejects_double_counting_candidate():
    row = evidence()
    row["market_quality_report"]["candidate_canonical_series"][
        "cross_pool_volume_double_counting_allowed"
    ] = True

    with pytest.raises(ValueError, match="double counting"):
        freeze(row)


def test_direct_selector_freeze_rejects_wrong_point_source_set():
    row = evidence()
    row["point_sha256"].pop("direct_uniswap_v4")

    with pytest.raises(ValueError, match="point SHA source set"):
        freeze(row)


def test_direct_selector_freeze_rejects_bad_handoff_sha():
    with pytest.raises(ValueError, match="handoff SHA-256"):
        build_direct_selector_freeze(
            evidence(),
            evidence_run_id=123,
            evidence_artifact_digest="sha256:" + SHA,
            evidence_handoff_sha256="bad",
        )
