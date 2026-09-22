from pathlib import Path


WORKFLOW = Path(".github/workflows/phase2-post-selector-wave-launch.yml")


def test_post_selector_launcher_is_manual_and_non_mutating():
    text = WORKFLOW.read_text()
    assert "workflow_dispatch:" in text
    assert "confirm_post_selector_wave:" in text
    assert "default: false" in text
    assert "confirm_post_selector_wave=true" in text
    assert "actions: write" in text
    assert "contents: write" not in text


def test_post_selector_launcher_requires_exact_approved_freeze():
    text = WORKFLOW.read_text()
    assert "approved_freeze_run_id:" in text
    assert "expected_freeze_artifact_digest:" in text
    assert "validate_phase2_selector_approved_freeze_receipt" in text
    assert "approved selector freeze artifact digest drift" in text


def test_post_selector_launcher_dispatches_exact_two_auto_nodes():
    text = WORKFLOW.read_text()
    assert "PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS" in text
    assert "validate_phase2_selector_freeze_completion" in text
    assert '"manual_inputs_json": "{}"' in text
    assert "post-selector dispatcher generated-input drift" in text


def test_post_selector_launcher_reconciles_paired_dispatch_evidence():
    text = WORKFLOW.read_text()
    assert "phase2-execution-node-dispatch-attempt.json" in text
    assert "phase2-execution-node-dispatch.json" in text
    assert "validate_phase2_node_dispatch_evidence" in text
    assert "attempt_file_sha256=attempt_sha" in text


def test_post_selector_launcher_stops_before_targets_finish():
    text = WORKFLOW.read_text()
    assert '"target_runs_waited_for_completion": False' in text
    assert '"selector_approval_performed": True' in text
    assert '"coverage_promotion_performed": False' in text
    assert '"canonical_coverage_ledger_mutated": False' in text
