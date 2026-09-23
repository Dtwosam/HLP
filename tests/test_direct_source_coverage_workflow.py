from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-direct-source-coverage.yml"
)


def test_direct_source_coverage_is_dispatch_only_and_source_parameterized():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    for source in (
        "direct_uniswap_v3",
        "direct_sushiswap_v3",
        "direct_uniswap_v4",
    ):
        assert source in text
    assert "SHARD_COUNT: '128'" in text
    assert "phase2-direct-v3-market-window" in text
    assert "phase2-direct-v4-market-window" in text


def test_direct_source_coverage_binds_conclusive_population_and_shared_tapes():
    text = WORKFLOW.read_text()

    assert "expected_population_artifact_digest:" in text
    assert "expected_population_handoff_sha256:" in text
    assert "direct source population handoff SHA drift" in text
    assert "phase2-direct-source-population-handoff-v1" in text
    assert "canonical_market_selection_applied" in text
    assert "direct-source-initializes.jsonl" in text
    assert "direct-source-supply-deltas.jsonl" in text
    assert "shared Swap aggregate SHA drift" in text
    assert "shared supply-delta aggregate SHA drift" in text
    assert "direct quote artifact SHA drift" in text


def test_direct_source_coverage_keeps_all_markets_and_requires_full_pricing():
    text = WORKFLOW.read_text()

    assert "audit_direct_source_market_points" in text
    assert "selector_rule_applied_to_coverage_points" in text
    assert "direct coverage replay unexpectedly applied selector" in text
    assert "direct coverage shard contains unpriced points" in text
    assert "direct source coverage did not validate as complete" in text
    assert "apply_phase2_source_coverage_report" in text
    assert '"coverage_status": "complete"' not in text


def test_direct_source_coverage_publishes_nonmutating_promotion_handoff():
    text = WORKFLOW.read_text()

    assert "direct-source-coverage-report.json" in text
    assert "direct-source-coverage-proposed-ledger.json" in text
    assert "steps.upload.outputs.artifact-digest" in text
    assert "expected_report_sha256" in text
    assert "expected_source_id" in text
    assert "git commit" not in text
    assert "git push" not in text
    assert "contents: write" not in text
