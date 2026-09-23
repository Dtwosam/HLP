from pathlib import Path

WORKFLOW = Path(".github/workflows/phase2-doppler-ledger-approved.yml")


def test_doppler_ledger_approval_requires_explicit_human_boolean():
    text = WORKFLOW.read_text()
    assert "apply_doppler_ledger:" in text
    assert "default: false" in text
    assert "apply_doppler_ledger=true" in text
    assert "actions: write" in text


def test_doppler_ledger_approval_requires_exact_proposal_and_prior_handoff():
    text = WORKFLOW.read_text()
    assert "validate_phase2_doppler_promotion_proposal_receipt" in text
    assert "validate_phase2_doppler_promotion_review_receipt" in text
    assert "validate_phase2_pools_trade_lbp_ledger_approved_receipt" in text
    assert "proposal base-ledger SHA drift" in text


def test_doppler_ledger_approval_consumes_44_dispatcher_receipts():
    text = WORKFLOW.read_text()
    assert "44 unique dispatcher control runs" in text
    assert "node_dispatch_run_ids_json" in text
    assert '"shared:direct_selector_freeze"' in text


def test_doppler_ledger_approval_verifies_exact_6_of_14_frontier():
    text = WORKFLOW.read_text()
    assert "phase2-source-coverage-ledger-commit.yml" in text
    assert '"apply_proposed_ledger": True' in text
    assert "validate_phase2_doppler_ledger_commit_receipt" in text
    assert "validate_phase2_doppler_post_commit_frontier" in text
    assert "canonical_complete_sources: 6/14" in text
    assert "next_promotion_node_id: promote:flap" in text
