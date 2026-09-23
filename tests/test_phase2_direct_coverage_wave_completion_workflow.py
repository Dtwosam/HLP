from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-direct-coverage-wave-completion.yml"
)


def test_direct_coverage_completion_is_manual_and_non_mutating():
    text = WORKFLOW.read_text()
    assert "workflow_dispatch:" in text
    assert "confirm_completion_refresh:" in text
    assert "default: false" in text
    assert "confirm_completion_refresh=true" in text
    assert "actions: write" in text
    assert "contents: write" not in text


def test_direct_coverage_completion_requires_three_real_targets():
    text = WORKFLOW.read_text()
    assert "PHASE2_AFTER_POST_SELECTOR_AUTO_NODE_IDS" in text
    assert "direct coverage target not completed" in text
    assert "direct coverage target failed" in text


def test_direct_coverage_completion_reconciles_40_receipts_and_selector():
    text = WORKFLOW.read_text()
    assert "validate_phase2_post_selector_wave_completion_receipt" in text
    assert "exactly 40 unique" in text
    assert '"shared:direct_selector_freeze"' in text
    assert "node_dispatch_run_ids_json" in text


def test_direct_coverage_completion_freezes_manual_promotion_frontier():
    text = WORKFLOW.read_text()
    assert "validate_phase2_direct_coverage_completion" in text
    assert "automatic_acquisition_complete" in text
    assert "completed_execution_nodes: 41" in text
    assert "auto_node_ids: []" in text
    assert "manual_promotion_node_ids: [promote:pools_fun]" in text
    assert "canonical_coverage_ledger_mutated: false" in text
