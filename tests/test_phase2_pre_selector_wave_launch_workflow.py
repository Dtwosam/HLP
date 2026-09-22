from pathlib import Path


WORKFLOW = Path(".github/workflows/phase2-pre-selector-wave-launch.yml")


def test_pre_selector_launcher_is_manual_and_holds_promotion():
    text = WORKFLOW.read_text()
    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "confirm_pre_selector_wave:" in text
    assert "default: false" in text
    assert "confirm_pre_selector_wave=true" in text
    assert "actions: write" in text
    assert "contents: write" not in text
    assert "pools_fun_promotion_held_for_operator" in text


def test_pre_selector_launcher_requires_exact_completion_handoff():
    text = WORKFLOW.read_text()
    assert "after_post_fanout_wave_completion_run_id:" in text
    assert "expected_completion_artifact_digest:" in text
    assert "validate_phase2_after_post_fanout_wave_completion_receipt" in text
    assert "seven-node completion artifact digest drift" in text


def test_pre_selector_launcher_dispatches_only_four_auto_nodes():
    text = WORKFLOW.read_text()
    assert "PHASE2_PRE_SELECTOR_AUTO_NODE_IDS" in text
    assert "validate_phase2_after_post_fanout_wave_completion" in text
    assert '"manual_inputs_json": "{}"' in text
    assert "pre-selector dispatcher generated-input drift" in text
    assert "promote:pools_fun" not in text
    assert "shared:direct_selector_freeze" not in text


def test_pre_selector_launcher_reconciles_paired_dispatch_evidence():
    text = WORKFLOW.read_text()
    assert "phase2-execution-node-dispatch-attempt.json" in text
    assert "phase2-execution-node-dispatch.json" in text
    assert "validate_phase2_node_dispatch_evidence" in text


def test_pre_selector_launcher_stops_before_target_completion_or_approval():
    text = WORKFLOW.read_text()
    assert '"target_runs_waited_for_completion": False' in text
    assert '"coverage_promotion_performed": False' in text
    assert '"selector_approval_performed": False' in text
    assert '"canonical_coverage_ledger_mutated": False' in text
