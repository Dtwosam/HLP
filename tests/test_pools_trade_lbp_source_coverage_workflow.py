from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-pools-trade-lbp-source-coverage.yml"
)


def test_lbp_source_coverage_is_dispatch_only_and_reuses_frozen_surfaces():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "cca_run_id:" in text
    assert "v4_initialize_run_id:" in text
    assert "v4_swap_run_id:" in text
    assert "phase2-pools-trade-lbp-cca-setup" in text
    assert "phase2-pools-trade-lbp-cca-coverage" in text
    assert "phase2-direct-v4-initialize-merged" in text
    assert "phase2-direct-v4-swap-" in text
    assert "matrix.shard" in text


def test_lbp_source_coverage_requires_conclusive_optional_migration():
    text = WORKFLOW.read_text()

    assert "continuous_event_scan" in text
    assert "phase2-pools-trade-lbp-migrated-registry" in text
    assert '"migration_absence_conclusive": True' in text
    assert "LBP migration population does not reconcile" in text
    assert "LBP V4 summary does not cover migrated population" in text
    assert "LBP V4 Initialize point population drift" in text


def test_lbp_source_coverage_merges_cca_and_v4_fail_closed():
    text = WORKFLOW.read_text()

    assert "merge_pools_trade_lbp_market_cap_summaries" in text
    assert "merge_v4_launchpad_market_cap_summaries" in text
    assert "LBP lifecycle summary does not cover every token" in text
    assert "LBP lifecycle summary has incomplete pricing" in text
    assert "LBP lifecycle phase point accounting drift" in text
    assert "validate_pools_trade_lbp_coverage_report" in text
    assert "apply_phase2_source_coverage_report" in text


def test_lbp_source_coverage_only_proposes_ledger_and_publishes_handoff():
    text = WORKFLOW.read_text()

    assert '"coverage_status": "complete"' in text
    assert "pools-trade-lbp-source-coverage-proposed-ledger.json" in text
    assert "steps.upload.outputs.artifact-digest" in text
    assert "expected_source_id: pools_trade_lbp" in text
    assert "git commit" not in text
    assert "git push" not in text
    assert "contents: write" not in text
