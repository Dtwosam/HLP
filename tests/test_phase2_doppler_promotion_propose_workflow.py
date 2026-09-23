from pathlib import Path

WORKFLOW = Path(".github/workflows/phase2-doppler-promotion-propose.yml")


def test_doppler_proposal_requires_explicit_creation_boolean():
    text = WORKFLOW.read_text()
    assert "confirm_create_proposal:" in text
    assert "default: false" in text
    assert "confirm_create_proposal=true" in text
    assert "actions: write" in text
    assert "contents: write" not in text


def test_doppler_proposal_requires_review_and_uses_dispatcher():
    text = WORKFLOW.read_text()
    assert "phase2-doppler-promotion-review.yml" in text
    assert "validate_phase2_doppler_promotion_review_receipt" in text
    assert "phase2-execution-node-dispatch.yml" in text
    assert '"promote:doppler"' in text


def test_doppler_proposal_is_proposal_only():
    text = WORKFLOW.read_text()
    assert "expected_source_id: doppler" in text
    assert "ledger_commit_approval_value_supplied" in text
    assert '"canonical_coverage_ledger_mutated": False' in text
    assert '"ledger_commit_authorized": False' in text
