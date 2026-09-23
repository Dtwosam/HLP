from pathlib import Path

WORKFLOW = Path(".github/workflows/phase2-trench-today-ledger-approved.yml")


def test_trench_ledger_approval_requires_explicit_human_boolean():
    text = WORKFLOW.read_text()
    assert "apply_trench_today_ledger:" in text
    assert "default: false" in text
    assert "apply_trench_today_ledger=true" in text
    assert "actions: write" in text


def test_trench_ledger_approval_requires_exact_proposal_and_flap_handoff():
    text = WORKFLOW.read_text()
    assert "validate_phase2_trench_today_promotion_proposal_receipt" in text
    assert "validate_phase2_trench_today_promotion_review_receipt" in text
    assert "validate_phase2_flap_ledger_approved_receipt" in text
    assert "proposal base-ledger SHA drift" in text


def test_trench_ledger_approval_consumes_46_dispatcher_receipts():
    text = WORKFLOW.read_text()
    assert "46 unique dispatcher control runs" in text
    assert "node_dispatch_run_ids_json" in text
    assert '"shared:direct_selector_freeze"' in text


def test_trench_ledger_approval_verifies_exact_8_of_14_frontier():
    text = WORKFLOW.read_text()
    assert "phase2-source-coverage-ledger-commit.yml" in text
    assert '"apply_proposed_ledger": True' in text
    assert "validate_phase2_trench_today_ledger_commit_receipt" in text
    assert "validate_phase2_trench_today_post_commit_frontier" in text
    assert "canonical_complete_sources: 8/14" in text
    assert "next_promotion_node_id: promote:hood_fun_current" in text
