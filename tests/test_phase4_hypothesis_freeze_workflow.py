from pathlib import Path


WORKFLOW = Path(".github/workflows/phase4-hypothesis-freeze.yml")


def test_phase4_hypothesis_freeze_is_manual_and_read_only():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "actions: read" in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "git push" not in text


def test_phase4_hypothesis_freeze_requires_explicit_plan():
    text = WORKFLOW.read_text()

    assert "univariate_handoff_json:" in text
    assert "chronological_split_handoff_json:" in text
    assert "hypothesis_plan_json:" in text
    assert "build_phase4_univariate_handoff" in text
    assert "build_phase4_chronological_split_handoff" in text
    assert "build_phase4_hypothesis_freeze" in text
    assert "build_phase4_hypothesis_freeze_handoff" in text


def test_phase4_hypothesis_freeze_never_opens_unseen_rows():
    text = WORKFLOW.read_text()

    assert "phase4-validation.jsonl" in text
    assert "phase4-final-test.jsonl" in text
    assert "validation_rows_consumed: false" in text
    assert "final_test_rows_consumed: false" in text
    assert "selection_manual: true" in text
    assert "automatic_feature_ranking_used: false" in text
    assert "multiple_testing_plan_frozen: true" in text
    assert "signal_promoted: false" in text
    assert "phase4_discovery_checkpoint_claimed: false" in text
    assert "phase4_discovery_checkpoint_claimed: true" not in text
