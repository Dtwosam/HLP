from pathlib import Path


WORKFLOW = Path(".github/workflows/phase2-direct-coverage-wave-launch.yml")


def test_direct_coverage_launcher_is_manual_and_non_mutating():
    text = WORKFLOW.read_text()
    assert "workflow_dispatch:" in text
    assert "confirm_direct_coverage_wave:" in text
    assert "default: false" in text
    assert "confirm_direct_coverage_wave=true" in text
    assert "actions: write" in text
    assert "contents: write" not in text


def test_direct_coverage_launcher_requires_post_selector_handoff():
    text = WORKFLOW.read_text()
    assert "post_selector_completion_run_id:" in text
    assert "expected_completion_artifact_digest:" in text
    assert "validate_phase2_post_selector_wave_completion_receipt" in text
    assert "post-selector completion artifact digest drift" in text


def test_direct_coverage_launcher_dispatches_exact_three_nodes():
    text = WORKFLOW.read_text()
    assert "PHASE2_AFTER_POST_SELECTOR_AUTO_NODE_IDS" in text
    assert "validate_phase2_post_selector_wave_completion" in text
    assert '"manual_inputs_json": "{}"' in text
    assert "direct-coverage dispatcher generated-input drift" in text


def test_direct_coverage_launcher_stops_before_target_completion():
    text = WORKFLOW.read_text()
    assert '"target_runs_waited_for_completion": False' in text
    assert '"coverage_promotion_performed": False' in text
    assert '"canonical_coverage_ledger_mutated": False' in text
