from pathlib import Path


WORKFLOW = Path(".github/workflows/phase4-stability.yml")


def test_phase4_stability_is_manual_and_read_only():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "actions: read" in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "git push" not in text


def test_phase4_stability_uses_frozen_plan_and_discovery_only():
    text = WORKFLOW.read_text()

    assert "chronological_split_handoff_json:" in text
    assert "hypothesis_freeze_handoff_json:" in text
    assert "phase4-discovery-train.jsonl" in text
    assert "build_phase4_hypothesis_freeze_handoff" in text
    assert "build_phase4_stability_report" in text
    assert "build_phase4_stability_handoff" in text
    assert "Phase-4 stability artifact exposes validation rows" in text
    assert "Phase-4 stability artifact exposes final-test rows" in text


def test_phase4_stability_never_invents_a_pass_threshold():
    text = WORKFLOW.read_text()

    assert "repeated_sampling_stability_examined: true" in text
    assert "chronological_stability_examined: true" in text
    assert "stability_pass_fail_threshold_applied: false" in text
    assert "validation_rows_consumed: false" in text
    assert "final_test_rows_consumed: false" in text
    assert "signal_promoted: false" in text
    assert "phase4_discovery_checkpoint_claimed: false" in text
