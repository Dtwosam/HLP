from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-pools-fun-promotion-review.yml"
)


def test_pools_fun_promotion_review_is_manual_and_read_only():
    text = WORKFLOW.read_text()
    assert "workflow_dispatch:" in text
    assert "confirm_prepare_review:" in text
    assert "default: false" in text
    assert "confirm_prepare_review=true" in text
    assert "actions: read" in text
    assert "actions: write" not in text
    assert "contents: write" not in text


def test_pools_fun_promotion_review_requires_exact_frontier():
    text = WORKFLOW.read_text()
    assert "promotion_frontier_run_id:" in text
    assert "expected_frontier_artifact_digest:" in text
    assert "validate_phase2_direct_coverage_wave_completion_receipt" in text
    assert "validate_phase2_direct_coverage_completion" in text
    assert "promotion frontier artifact digest drift" in text


def test_pools_fun_promotion_review_derives_coverage_run_from_planner():
    text = WORKFLOW.read_text()
    assert 'frontier["promotion_run_inputs"]' in text
    assert 'set(run_inputs) != {"coverage_run_id"}' in text
    assert "phase2-pools-fun-source-coverage.yml" not in text
    assert "POOLS_FUN_COVERAGE_WORKFLOW" in text


def test_pools_fun_promotion_review_verifies_exact_report_and_inputs():
    text = WORKFLOW.read_text()
    assert "POOLS_FUN_COVERAGE_ARTIFACT" in text
    assert "POOLS_FUN_COVERAGE_REPORT_PATH" in text
    assert "build_phase2_pools_fun_promotion_review_handoff" in text
    assert "coverage_artifact_digest" in text
    assert "coverage_report_sha256" in text
    assert "expected_source_id: pools_fun" in text


def test_pools_fun_promotion_review_never_dispatches_or_mutates():
    text = WORKFLOW.read_text()
    assert "promotion_review_required: true" in text
    assert "promotion_dispatched: false" in text
    assert "proposal_created: false" in text
    assert "canonical_coverage_ledger_mutated: false" in text
    assert "/dispatches" not in text
    assert "phase2-source-coverage-ledger-commit.yml" not in text
