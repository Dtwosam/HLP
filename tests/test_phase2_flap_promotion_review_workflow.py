from pathlib import Path

WORKFLOW = Path(".github/workflows/phase2-flap-promotion-review.yml")


def test_flap_review_is_manual_and_read_only():
    text = WORKFLOW.read_text()
    assert "workflow_dispatch:" in text
    assert "confirm_prepare_review:" in text
    assert "default: false" in text
    assert "actions: read" in text
    assert "actions: write" not in text
    assert "contents: write" not in text


def test_flap_review_requires_approved_6_of_14_handoff():
    text = WORKFLOW.read_text()
    assert "doppler_ledger_approval_run_id:" in text
    assert "validate_phase2_doppler_ledger_approved_receipt" in text
    assert "validate_phase2_doppler_post_commit_frontier" in text
    assert '"promote:flap"' in text


def test_flap_review_uses_exact_coverage_artifact():
    text = WORKFLOW.read_text()
    assert "phase2-flap-source-coverage.yml" in text
    assert "phase2-flap-source-coverage" in text
    assert "flap-source-coverage-report.json" in text
    assert "build_phase2_flap_promotion_review_handoff" in text


def test_flap_review_never_dispatches_or_mutates():
    text = WORKFLOW.read_text()
    assert "promotion_dispatched: false" in text
    assert "proposal_created: false" in text
    assert "canonical_coverage_ledger_mutated: false" in text
    assert "/dispatches" not in text
