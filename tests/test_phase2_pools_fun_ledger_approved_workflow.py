from pathlib import Path


WORKFLOW = Path(".github/workflows/phase2-pools-fun-ledger-approved.yml")


def test_pools_fun_ledger_approval_is_manual_and_explicit():
    text = WORKFLOW.read_text()
    assert "workflow_dispatch:" in text
    assert "apply_pools_fun_ledger:" in text
    assert "default: false" in text
    assert "apply_pools_fun_ledger=true" in text
    assert "actions: write" in text


def test_pools_fun_ledger_approval_requires_exact_validated_proposal():
    text = WORKFLOW.read_text()
    assert "promotion_proposal_run_id:" in text
    assert "expected_proposal_artifact_digest:" in text
    assert "validate_phase2_pools_fun_promotion_proposal_receipt" in text
    assert "pools.fun proposal artifact digest drift" in text
    assert "pools.fun proposal base-ledger SHA drift" in text


def test_pools_fun_ledger_approval_recovers_40_plus_promotion_receipts():
    text = WORKFLOW.read_text()
    assert "validate_phase2_pools_fun_promotion_review_receipt" in text
    assert "validate_phase2_direct_coverage_wave_completion_receipt" in text
    assert "exactly 41 unique" in text
    assert "node_dispatch_run_ids_json" in text


def test_pools_fun_ledger_approval_dispatches_existing_writer_only_after_approval():
    text = WORKFLOW.read_text()
    assert "phase2-source-coverage-ledger-commit.yml" in text
    assert '"apply_proposed_ledger": True' in text
    assert "validate_phase2_pools_fun_ledger_commit_receipt" in text
    assert "canonical commit is not current branch HEAD" in text


def test_pools_fun_ledger_approval_refreshes_exact_3_of_14_frontier():
    text = WORKFLOW.read_text()
    assert "validate_phase2_pools_fun_post_commit_frontier" in text
    assert "pools.fun post-commit planner HEAD linkage drift" in text
    assert "canonical_complete_sources: 3/14" in text
    assert "next_promotion_node_id: promote:pools_trade_instant" in text
