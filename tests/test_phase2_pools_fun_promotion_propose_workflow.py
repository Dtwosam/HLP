from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-pools-fun-promotion-propose.yml"
)


def test_pools_fun_proposal_executor_requires_explicit_confirmation():
    text = WORKFLOW.read_text()
    assert "workflow_dispatch:" in text
    assert "confirm_create_proposal:" in text
    assert "default: false" in text
    assert "confirm_create_proposal=true" in text
    assert "actions: write" in text
    assert "contents: write" not in text


def test_pools_fun_proposal_executor_requires_exact_review_handoff():
    text = WORKFLOW.read_text()
    assert "promotion_review_run_id:" in text
    assert "expected_review_artifact_digest:" in text
    assert "validate_phase2_pools_fun_promotion_review_receipt" in text
    assert "pools.fun promotion review artifact digest drift" in text


def test_pools_fun_proposal_executor_uses_duplicate_safe_dispatcher():
    text = WORKFLOW.read_text()
    assert "phase2-execution-node-dispatch.yml" in text
    assert '"node_id": "promote:pools_fun"' in text
    assert "phase2-execution-node-dispatch-attempt.json" in text
    assert "validate_phase2_node_dispatch_evidence" in text
    assert "pools.fun promotion dispatch input schema drift" in text


def test_pools_fun_proposal_executor_validates_proposal_without_commit():
    text = WORKFLOW.read_text()
    assert "validate_phase2_coverage_ledger_commit" in text
    assert "phase2-source-coverage.proposed.json" in text
    assert "phase2-source-coverage-promotion.json" in text
    assert "canonical coverage ledger changed during proposal validation" in text
    assert '"canonical_coverage_ledger_mutated": False' in text
    assert '"ledger_commit_authorized": False' in text


def test_pools_fun_proposal_executor_leaves_ledger_approval_unset():
    text = WORKFLOW.read_text()
    assert '"ledger_commit_approval_input": "apply_proposed_ledger"' in text
    assert '"ledger_commit_approval_value_supplied": False' in text
    assert "apply_proposed_ledger=true" not in text
    assert "phase2-source-coverage-ledger-commit.yml" not in text
