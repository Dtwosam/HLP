from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-trench-source-coverage.yml"
)


def test_trench_source_coverage_is_dispatch_only_and_exactly_bound():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "expected_curve_artifact_digest:" in text
    assert "expected_curve_report_sha256:" in text
    assert "expected_handoff_artifact_digest:" in text
    assert "expected_handoff_report_sha256:" in text
    assert "direct_registry_run_id:" in text
    assert "trench handoff direct registry run drift" in text
    assert "trench direct registry SHA drift" in text


def test_trench_source_coverage_reuses_shared_surfaces():
    text = WORKFLOW.read_text()

    assert "phase2-direct-v3-initialize-merged" in text
    assert "phase2-direct-v4-initialize-merged" in text
    assert "phase2-direct-v3-swap-${{ matrix.shard }}" in text
    assert "phase2-direct-v4-swap-${{ matrix.shard }}" in text
    assert "phase2-direct-supply-delta-manifest" in text
    assert "pattern: phase2-direct-supply-delta-*" in text
    assert "iter_sharded_jsonl_matching_field_values" in text
    assert "filtered_shared_supply_deltas_for_trench" in text


def test_trench_source_coverage_requires_frozen_complete_lifecycle():
    text = WORKFLOW.read_text()

    assert "phase2-trench-handoff-market-registry" in text
    assert "phase2-v3-registry-event-filter" in text
    assert "phase2-v4-registry-event-filter" in text
    assert "phase2-trench-v3-market-window" in text
    assert "phase2-trench-v4-market-window" in text
    assert "summarize_trench_post_limit_market_caps" in text
    assert "merge_trench_lifecycle_market_cap_summaries" in text
    assert "validate_trench_source_coverage_report" in text
    assert "full coverage lacks curve points for every launch" in text
    assert "post-limit population does not match LimitReach" in text


def test_trench_source_coverage_validates_but_never_mutates_ledger():
    text = WORKFLOW.read_text()

    assert "apply_phase2_source_coverage_report" in text
    assert '"coverage_status": "complete"' in text
    assert "trench-source-coverage.proposed.json" in text
    assert "trench-source-coverage-report.json" in text
    assert "expected_source_id: trench_today" in text
    assert "git commit" not in text
    assert "git push" not in text
    assert "contents: write" not in text
