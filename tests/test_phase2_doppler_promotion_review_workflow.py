from pathlib import Path

WORKFLOW = Path(".github/workflows/phase2-doppler-promotion-review.yml")


def test_doppler_review_is_manual_and_read_only():
    text = WORKFLOW.read_text()
    assert "workflow_dispatch:" in text
    assert "confirm_prepare_review:" in text
    assert "default: false" in text
    assert "actions: read" in text
    assert "actions: write" not in text
    assert "contents: write" not in text


def test_doppler_review_requires_approved_5_of_14_handoff():
    text = WORKFLOW.read_text()
    assert "pools_trade_lbp_ledger_approval_run_id:" in text
    assert "validate_phase2_pools_trade_lbp_ledger_approved_receipt" in text
    assert "validate_phase2_pools_trade_lbp_post_commit_frontier" in text
    assert '"promote:doppler"' in text


def test_doppler_review_uses_exact_coverage_artifact():
    text = WORKFLOW.read_text()
    assert "phase2-doppler-source-coverage.yml" in text
    assert "phase2-doppler-source-coverage" in text
    assert "doppler-source-coverage-report.json" in text
    assert "build_phase2_doppler_promotion_review_handoff" in text


def test_doppler_review_never_dispatches_or_mutates():
    text = WORKFLOW.read_text()
    assert "promotion_dispatched: false" in text
    assert "proposal_created: false" in text
    assert "canonical_coverage_ledger_mutated: false" in text
    assert "/dispatches" not in text
