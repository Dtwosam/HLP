from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-pools-trade-instant-promotion-review.yml"
)


def test_pools_trade_instant_review_is_manual_and_read_only():
    text = WORKFLOW.read_text()
    assert "workflow_dispatch:" in text
    assert "confirm_prepare_review:" in text
    assert "default: false" in text
    assert "confirm_prepare_review=true" in text
    assert "actions: read" in text
    assert "actions: write" not in text
    assert "contents: write" not in text


def test_pools_trade_instant_review_requires_approved_3_of_14_handoff():
    text = WORKFLOW.read_text()
    assert "pools_fun_ledger_approval_run_id:" in text
    assert "expected_approval_artifact_digest:" in text
    assert "validate_phase2_pools_fun_ledger_approved_receipt" in text
    assert "canonical commit is not review HEAD" in text
    assert "validate_phase2_pools_fun_post_commit_frontier" in text


def test_pools_trade_instant_review_uses_planner_verified_coverage_run():
    text = WORKFLOW.read_text()
    assert '"promote:pools_trade_instant"' in text
    assert 'run_inputs["coverage_run_id"]' in text
    assert "phase2-pools-trade-instant-source-coverage.yml" in text
    assert "phase2-pools-trade-instant-source-coverage" in text
    assert "pools-trade-instant-source-coverage-report.json" in text


def test_pools_trade_instant_review_never_dispatches_or_mutates():
    text = WORKFLOW.read_text()
    assert "build_phase2_pools_trade_instant_promotion_review_handoff" in text
    assert "promotion_dispatched: false" in text
    assert "proposal_created: false" in text
    assert "canonical_coverage_ledger_mutated: false" in text
    assert "/dispatches" not in text
