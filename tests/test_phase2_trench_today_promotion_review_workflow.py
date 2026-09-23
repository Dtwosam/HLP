from pathlib import Path

WORKFLOW = Path(".github/workflows/phase2-trench-today-promotion-review.yml")


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
    assert "flap_ledger_approval_run_id:" in text
    assert "validate_phase2_flap_ledger_approved_receipt" in text
    assert "validate_phase2_flap_post_commit_frontier" in text
    assert '"promote:trench_today"' in text


def test_trench_review_uses_exact_coverage_artifact():
    text = WORKFLOW.read_text()
    assert "phase2-trench-source-coverage.yml" in text
    assert "phase2-trench-source-coverage" in text
    assert "trench-source-coverage-report.json" in text
    assert "build_phase2_trench_today_promotion_review_handoff" in text


def test_trench_review_never_dispatches_or_mutates():
    text = WORKFLOW.read_text()
    assert "promotion_dispatched: false" in text
    assert "proposal_created: false" in text
    assert "canonical_coverage_ledger_mutated: false" in text
    assert "/dispatches" not in text
