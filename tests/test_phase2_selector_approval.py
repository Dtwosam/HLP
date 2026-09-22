import pytest

from hlp.data.market_quality import MARKET_SELECTION_CANDIDATE_VERSION
from hlp.data.phase2_selector_approval import (
    PHASE2_SELECTOR_APPROVAL_HANDOFF_VERSION,
    build_phase2_selector_approval_handoff,
)


SHA = "ab" * 32


def evidence():
    return {
        "version": "phase2-direct-market-quality-evidence-v2",
        "chain_id": 4663,
        "snapshot_head_block": 54486035,
        "sample_tokens": 4,
        "sample_markets": 9,
        "sampling_rule": "chronological_even_spacing_v1",
        "window_blocks": 100000,
        "quote_run_id": 1,
        "registry_run_id": 2,
        "cohort_run_id": 3,
        "v3_initialize_run_id": 4,
        "v3_swap_run_id": 5,
        "v4_initialize_run_id": 6,
        "v4_swap_run_id": 7,
        "supply_delta_run_id": 8,
        "plan_sha256": SHA,
        "quote_registry_sha256": SHA,
        "quote_decimals_sha256": SHA,
        "quote_feed_specs_sha256": SHA,
        "point_sha256": {
            "direct_uniswap_v3": SHA,
            "direct_sushiswap_v3": SHA,
            "direct_uniswap_v4": SHA,
        },
        "trace_sha256": SHA,
        "candidate_series_sha256": SHA,
        "market_quality_report_sha256": SHA,
        "market_quality_report": {
            "selection_rule_frozen": False,
            "causal_trace": {
                "multi_market_snapshots": 12,
                "tokens": 4,
            },
            "candidate_canonical_series": {
                "selection_policy_candidate_version": (
                    MARKET_SELECTION_CANDIDATE_VERSION
                ),
                "selection_rule_frozen": False,
                "cross_pool_volume_double_counting_allowed": False,
                "points": 15,
            },
        },
        "selector_freeze_ready": False,
        "source_coverage_complete": False,
        "remaining_steps": [
            "review real-market liquidity leadership stability",
            "freeze selector only in an explicit versioned decision",
        ],
    }


def file_shas():
    return {
        "direct-market-quality-trace.jsonl": SHA,
        "direct-market-candidate-series.jsonl": SHA,
        "direct-market-quality-report.json": SHA,
    }


def build(row=None, files=None):
    return build_phase2_selector_approval_handoff(
        evidence() if row is None else row,
        evidence_run_id=123,
        evidence_artifact_digest="sha256:" + "cd" * 32,
        evidence_handoff_sha256="ef" * 32,
        final_file_sha256=file_shas() if files is None else files,
    )


def test_selector_approval_handoff_is_read_only_and_explicit():
    report = build()

    assert report["version"] == PHASE2_SELECTOR_APPROVAL_HANDOFF_VERSION
    assert report["evidence_run_id"] == 123
    assert report["approval_required"] is True
    assert report["selector_freeze_ready_from_evidence"] is False
    assert report["selector_freeze_approval_value_supplied"] is False
    assert report["selector_approval_performed"] is False
    assert report["selector_workflow_dispatched"] is False
    assert report["canonical_coverage_ledger_mutated"] is False
    assert report["selector_freeze_generated_inputs"] == {
        "evidence_run_id": "123",
        "expected_artifact_digest": "sha256:" + "cd" * 32,
        "expected_handoff_sha256": "ef" * 32,
    }


def test_selector_approval_handoff_rejects_file_sha_drift():
    files = file_shas()
    files["direct-market-quality-report.json"] = "cd" * 32
    with pytest.raises(ValueError, match="final evidence file SHA drift"):
        build(files=files)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("selector_freeze_ready", True, "freeze readiness"),
        ("source_coverage_complete", True, "closes coverage"),
        ("sample_tokens", 0, "competing-market coverage"),
    ],
)
def test_selector_approval_handoff_rejects_evidence_state_drift(
    field,
    value,
    match,
):
    row = evidence()
    row[field] = value
    with pytest.raises(ValueError, match=match):
        build(row=row)


def test_selector_approval_handoff_rejects_already_frozen_report():
    row = evidence()
    row["market_quality_report"]["selection_rule_frozen"] = True
    with pytest.raises(ValueError, match="already freezes"):
        build(row=row)


def test_selector_approval_handoff_requires_explicit_freeze_step():
    row = evidence()
    row["remaining_steps"] = ["complete direct source historical coverage"]
    with pytest.raises(ValueError, match="explicit freeze review"):
        build(row=row)
