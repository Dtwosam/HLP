from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-pools-trade-lbp-promotion-propose.yml"
)


def test_pools_trade_lbp_proposal_is_manual_and_proposal_only():
    text = WORKFLOW.read_text()
    assert "workflow_dispatch:" in text
    assert "confirm_create_proposal:" in text
    assert "default: false" in text
    assert "confirm_create_proposal=true" in text
    assert "actions: write" in text
    assert "contents: write" not in text


def test_pools_trade_lbp_proposal_requires_exact_review_handoff():
    text = WORKFLOW.read_text()
    assert "phase2-pools-trade-lbp-promotion-review.yml" in text
    assert "validate_phase2_pools_trade_lbp_promotion_review_receipt" in text
    assert "promotion review artifact digest drift" in text
    assert "promotion review canonical-ledger SHA drift" in text


def test_pools_trade_lbp_proposal_uses_duplicate_safe_dispatcher():
    text = WORKFLOW.read_text()
    assert "phase2-execution-node-dispatch.yml" in text
    assert '"node_id": "promote:pools_trade_lbp"' in text
    assert "phase2-execution-node-dispatch-attempt.json" in text
    assert "validate_phase2_node_dispatch_evidence" in text


def test_pools_trade_lbp_proposal_validates_single_source_advance():
    text = WORKFLOW.read_text()
    assert 'expected_source_id="pools_trade_lbp"' in text
    assert "validate_phase2_coverage_ledger_commit" in text
    assert "phase2-source-coverage-promotion-pools_trade_lbp" in text
    assert '"proposal_validated": True' in text


def test_pools_trade_lbp_proposal_never_authorizes_ledger_write():
    text = WORKFLOW.read_text()
    assert '"ledger_commit_approval_value_supplied": False' in text
    assert '"canonical_coverage_ledger_mutated": False' in text
    assert '"ledger_commit_authorized": False' in text
    assert "apply_proposed_ledger" in text
