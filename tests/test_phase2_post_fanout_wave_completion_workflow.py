from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-post-fanout-wave-completion.yml"
)


def test_post_fanout_completion_is_manual_and_non_mutating():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "confirm_completion_refresh:" in text
    assert "default: false" in text
    assert "confirm_completion_refresh=true" in text
    assert "actions: write" in text
    assert "contents: write" not in text
    assert "canonical_coverage_ledger_mutated" in text


def test_post_fanout_completion_requires_exact_wave_receipt():
    text = WORKFLOW.read_text()

    assert "post_fanout_wave_launch_run_id:" in text
    assert "expected_wave_artifact_digest:" in text
    assert "validate_phase2_post_fanout_wave_launch_receipt" in text
    assert "post-fan-out wave artifact digest drift" in text
    assert "post-fan-out receipt/control run identity drift" in text


def test_post_fanout_completion_requires_nine_real_targets_successful():
    text = WORKFLOW.read_text()

    assert "PHASE2_POST_FANOUT_AUTO_NODE_IDS" in text
    assert "post-fan-out target not completed" in text
    assert "post-fan-out target failed" in text
    assert "target_run_ids" in text


def test_post_fanout_completion_reuses_prior_15_plus_new_9_receipts():
    text = WORKFLOW.read_text()

    assert "validate_phase2_archive_fanout_completion_receipt" in text
    assert "exactly 24 unique" in text
    assert "dispatcher control runs" in text
    assert "node_dispatch_run_ids_json" in text
    assert "validate_phase2_post_fanout_wave_completion" in text


def test_post_fanout_completion_holds_pools_fun_promotion():
    text = WORKFLOW.read_text()

    assert "pools_fun_promotion_held_for_operator" in text
    assert '"coverage_promotion_performed": False' in text
    assert '"selector_approval_performed": False' in text
    assert '"canonical_coverage_ledger_mutated": False' in text
    assert "phase2-source-coverage-promotion.yml" not in text
