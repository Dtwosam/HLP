from pathlib import Path

WORKFLOW = Path(".github/workflows/phase2-hoodfun-current-promotion-review.yml")


def test_trench_review_is_manual_and_read_only():
    text = WORKFLOW.read_text()
    assert "workflow_dispatch:" in text
    assert "confirm_prepare_review:" in text
    assert "default: false" in text
    assert "actions: read" in text
    assert "actions: write" not in text
    assert "contents: write" not in text


def test_trench_review_requires_approved_7_of_14_handoff():
    text = WORKFLOW.read_text()
    assert "trench_today_ledger_approval_run_id:" in text
    assert "validate_phase2_trench_today_ledger_approved_receipt" in text
    assert "validate_phase2_trench_today_post_commit_frontier" in text
    assert '"promote:hood_fun_current"' in text


def test_trench_review_uses_exact_coverage_artifact():
    text = WORKFLOW.read_text()
    assert "phase2-hoodfun-current-coverage.yml" in text
    assert "phase2-hoodfun-current-coverage" in text
    assert "hood-current-coverage.json" in text
    assert "build_phase2_hood_fun_current_promotion_review_handoff" in text


def test_trench_review_never_dispatches_or_mutates():
    text = WORKFLOW.read_text()
    assert "promotion_dispatched: false" in text
    assert "proposal_created: false" in text
    assert "canonical_coverage_ledger_mutated: false" in text
    assert "/dispatches" not in text
