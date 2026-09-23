from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-after-post-fanout-wave-completion.yml"
)


def test_after_post_fanout_completion_is_manual_and_non_mutating():
    text = WORKFLOW.read_text()
    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "confirm_completion_refresh:" in text
    assert "default: false" in text
    assert "confirm_completion_refresh=true" in text
    assert "actions: write" in text
    assert "contents: write" not in text


def test_after_post_fanout_completion_requires_exact_launch_receipt():
    text = WORKFLOW.read_text()
    assert "after_post_fanout_wave_launch_run_id:" in text
    assert "expected_wave_artifact_digest:" in text
    assert "validate_phase2_after_post_fanout_wave_launch_receipt" in text
    assert "after-post-fan-out wave artifact digest drift" in text


def test_after_post_fanout_completion_requires_seven_real_targets():
    text = WORKFLOW.read_text()
    assert "PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS" in text
    assert "after-post-fan-out target not completed" in text
    assert "after-post-fan-out target failed" in text


def test_after_post_fanout_completion_reuses_prior_24_plus_new_7():
    text = WORKFLOW.read_text()
    assert "validate_phase2_post_fanout_wave_completion_receipt" in text
    assert "requires exactly 31 unique" in text
    assert "node_dispatch_run_ids_json" in text
    assert "validate_phase2_after_post_fanout_wave_completion" in text


def test_after_post_fanout_completion_holds_pools_fun_promotion():
    text = WORKFLOW.read_text()
    assert "pools_fun_promotion_held_for_operator" in text
    assert '"coverage_promotion_performed": False' in text
    assert '"selector_approval_performed": False' in text
    assert '"canonical_coverage_ledger_mutated": False' in text
    assert "phase2-source-coverage-promotion.yml" not in text
