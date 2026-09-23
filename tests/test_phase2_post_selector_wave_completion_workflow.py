from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-post-selector-wave-completion.yml"
)


def test_post_selector_completion_is_manual_and_non_mutating():
    text = WORKFLOW.read_text()
    assert "workflow_dispatch:" in text
    assert "confirm_completion_refresh:" in text
    assert "default: false" in text
    assert "confirm_completion_refresh=true" in text
    assert "actions: write" in text
    assert "contents: write" not in text


def test_post_selector_completion_requires_exact_launch_receipt():
    text = WORKFLOW.read_text()
    assert "post_selector_wave_launch_run_id:" in text
    assert "expected_wave_artifact_digest:" in text
    assert "validate_phase2_post_selector_wave_launch_receipt" in text
    assert "post-selector wave artifact digest drift" in text


def test_post_selector_completion_requires_two_real_targets():
    text = WORKFLOW.read_text()
    assert "PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS" in text
    assert "post-selector target not completed" in text
    assert "post-selector target failed" in text


def test_post_selector_completion_carries_selector_and_37_dispatch_receipts():
    text = WORKFLOW.read_text()
    assert "validate_phase2_selector_approved_freeze_receipt" in text
    assert "exactly 37 unique" in text
    assert '"shared:direct_selector_freeze"' in text
    assert "node_dispatch_run_ids_json" in text
    assert "validate_phase2_post_selector_wave_completion" in text


def test_post_selector_completion_exposes_three_direct_coverages():
    text = WORKFLOW.read_text()
    assert "direct-coverage planner" in text
    assert "auto_node_ids" in text
    assert "pools_fun_promotion_held_for_operator" in text
    assert '"coverage_promotion_performed": False' in text
