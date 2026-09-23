from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-pools-trade-instant-ledger-approved.yml"
)


def test_instant_ledger_approval_requires_explicit_human_boolean():
    text = WORKFLOW.read_text()
    assert "apply_pools_trade_instant_ledger:" in text
    assert "default: false" in text
    assert "apply_pools_trade_instant_ledger=true" in text
    assert "actions: write" in text


def test_instant_ledger_approval_requires_exact_proposal_and_prior_handoff():
    text = WORKFLOW.read_text()
    assert "validate_phase2_pools_trade_instant_promotion_proposal_receipt" in text
    assert "validate_phase2_pools_trade_instant_promotion_review_receipt" in text
    assert "validate_phase2_pools_fun_ledger_approved_receipt" in text
    assert "proposal base-ledger SHA drift" in text


def test_instant_ledger_approval_consumes_42_dispatcher_receipts():
    text = WORKFLOW.read_text()
    assert "42 unique dispatcher control runs" in text
    assert "node_dispatch_run_ids_json" in text
    assert '"shared:direct_selector_freeze"' in text


def test_instant_ledger_approval_verifies_exact_writer_and_4_of_14_frontier():
    text = WORKFLOW.read_text()
    assert "phase2-source-coverage-ledger-commit.yml" in text
    assert '"apply_proposed_ledger": True' in text
    assert "validate_phase2_pools_trade_instant_ledger_commit_receipt" in text
    assert "validate_phase2_pools_trade_instant_post_commit_frontier" in text
    assert "canonical_complete_sources: 4/14" in text
    assert "next_promotion_node_id: promote:pools_trade_lbp" in text
