from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-trench-curve-coverage.yml"
)


def test_trench_curve_coverage_is_dispatch_only_and_sharded():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "registry_run_id:" in text
    assert "quote_run_id:" in text
    assert "SHARD_COUNT: '256'" in text
    assert "list(range(int(os.environ[\"SHARD_COUNT\"])))" in text
    assert "phase2-trench-registry-${{ matrix.shard }}" in text
    assert "rpc-trench-curve-market-cap-window" in text


def test_trench_curve_coverage_uses_canonical_quote_inputs():
    text = WORKFLOW.read_text()

    assert "direct-quote-decimals.json" in text
    assert "direct-quote-feeds.jsonl" in text
    assert "trench.today quote assets lack canonical decimals" in text
    assert "trench.today quote assets lack canonical USD feeds" in text
    assert "--quote-decimals inputs/setup/direct-quote-decimals.json" in text
    assert "--quote-feeds inputs/setup/direct-quote-feeds.jsonl" in text
    assert "trench.today shard has unpriced points" in text
    assert "trench.today merged curve has unpriced points" in text


def test_trench_curve_coverage_stays_nonfinal_after_limit_reach():
    text = WORKFLOW.read_text()

    assert "validate_trench_curve_coverage_report" in text
    assert '"coverage_segment": "bonding_curve"' in text
    assert "post_limit_dex_lifecycle_unresolved" in text
    assert '"source_coverage_complete": False' in text
    assert "source_coverage_complete: false" in text
    assert "apply_phase2_source_coverage_report" not in text
    assert "git commit" not in text
    assert "git push" not in text
