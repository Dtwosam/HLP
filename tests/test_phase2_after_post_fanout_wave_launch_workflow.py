from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-after-post-fanout-wave-launch.yml"
)


def test_after_post_fanout_launcher_is_manual_and_holds_promotion():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "confirm_after_post_fanout_wave:" in text
    assert "default: false" in text
    assert "confirm_after_post_fanout_wave=true" in text
    assert "actions: write" in text
    assert "contents: write" not in text
    assert "pools_fun_promotion_held_for_operator" in text


def test_after_post_fanout_launcher_requires_exact_completion_handoff():
    text = WORKFLOW.read_text()

    assert "post_fanout_wave_completion_run_id:" in text
    assert "expected_completion_artifact_digest:" in text
    assert "validate_phase2_post_fanout_wave_completion_receipt" in text
    assert "post-fan-out completion artifact digest drift" in text
    assert "after-post-fan-out completion/planner ready-node drift" in text


def test_after_post_fanout_launcher_dispatches_only_seven_auto_nodes():
    text = WORKFLOW.read_text()

    assert "PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS" in text
    assert "validate_phase2_post_fanout_wave_completion" in text
    assert '"manual_inputs_json": "{}"' in text
    assert "after-post-fan-out dispatcher generated-input drift" in text
    assert "manual_promotion_node_ids" in text
    assert "promote:pools_fun" not in text


def test_after_post_fanout_launcher_reconciles_paired_dispatch_evidence():
    text = WORKFLOW.read_text()

    assert "phase2-execution-node-dispatch-attempt.json" in text
    assert "phase2-execution-node-dispatch.json" in text
    assert "validate_phase2_node_dispatch_evidence" in text
    assert "attempt_file_sha256=attempt_sha" in text


def test_after_post_fanout_launcher_stops_before_target_completion():
    text = WORKFLOW.read_text()

    assert '"target_runs_waited_for_completion": False' in text
    assert '"coverage_promotion_performed": False' in text
    assert '"selector_approval_performed": False' in text
    assert '"canonical_coverage_ledger_mutated": False' in text
    assert "phase2-source-coverage-promotion.yml" not in text
