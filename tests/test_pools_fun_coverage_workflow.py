from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-pools-fun-source-coverage.yml"
)


def test_pools_fun_coverage_is_dispatch_only_and_reuses_shared_v3():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "SHARD_COUNT: '128'" in text
    assert "phase2-direct-v3-initialize-merged" in text
    assert "phase2-direct-v3-swap-${{ matrix.shard }}" in text
    assert "phase2-v3-registry-event-filter" in text
    assert "phase2-pools-fun-market-window" in text


def test_pools_fun_coverage_validates_but_does_not_mutate_ledger():
    text = WORKFLOW.read_text()

    assert "apply_phase2_source_coverage_report" in text
    assert '"coverage_status": "complete"' in text
    assert "pools-fun-source-coverage-report.json" in text
    assert "pools-fun-source-coverage-validation.json" in text
    assert "git commit" not in text
    assert "git push" not in text
    assert "phase2-apply-source-coverage" not in text


def test_pools_fun_coverage_requires_fully_priced_complete_population():
    text = WORKFLOW.read_text()

    assert "unpriced_points" in text
    assert "token summary does not cover every registry token" in text
    assert "merged summary contains missing/unpriced history" in text
    assert "merged point accounting drift" in text
    assert '"continuous": True' in text
    assert '"missing_ranges": []' in text
