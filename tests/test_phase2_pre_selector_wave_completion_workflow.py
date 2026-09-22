from pathlib import Path


WORKFLOW = Path(".github/workflows/phase2-pre-selector-wave-completion.yml")


def test_pre_selector_completion_is_manual_and_non_mutating():
    text = WORKFLOW.read_text()
    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "confirm_completion_refresh:" in text
    assert "default: false" in text
    assert "confirm_completion_refresh=true" in text
    assert "actions: write" in text
    assert "contents: write" not in text


def test_pre_selector_completion_requires_exact_launch_receipt():
    text = WORKFLOW.read_text()
    assert "pre_selector_wave_launch_run_id:" in text
    assert "expected_wave_artifact_digest:" in text
    assert "validate_phase2_pre_selector_wave_launch_receipt" in text
    assert "pre-selector wave artifact digest drift" in text


def test_pre_selector_completion_requires_four_real_targets():
    text = WORKFLOW.read_text()
    assert "PHASE2_PRE_SELECTOR_AUTO_NODE_IDS" in text
    assert "pre-selector target not completed" in text
    assert "pre-selector target failed" in text


def test_pre_selector_completion_reuses_prior_31_plus_new_4():
    text = WORKFLOW.read_text()
    assert "validate_phase2_after_post_fanout_wave_completion_receipt" in text
    assert "requires exactly 35 unique" in text
    assert "node_dispatch_run_ids_json" in text
    assert "validate_phase2_pre_selector_wave_completion" in text


def test_pre_selector_completion_exposes_selector_approval_without_doing_it():
    text = WORKFLOW.read_text()
    assert "approval_node_ids" in text
    assert "selector_manual_inputs" in text
    assert "pools_fun_promotion_held_for_operator" in text
    assert '"selector_approval_performed": False' in text
    assert '"coverage_promotion_performed": False' in text
    assert '"canonical_coverage_ledger_mutated": False' in text
