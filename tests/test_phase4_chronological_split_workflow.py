from pathlib import Path


WORKFLOW = Path(".github/workflows/phase4-chronological-split.yml")


def test_phase4_split_is_manual_and_read_only():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "actions: read" in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "git push" not in text


def test_phase4_split_requires_explicit_block_boundaries():
    text = WORKFLOW.read_text()

    assert "discovery_entry_handoff_json:" in text
    assert "discovery_end_block:" in text
    assert "validation_end_block:" in text
    assert "materialize_phase4_chronological_split" in text
    assert "build_phase4_chronological_split_handoff" in text


def test_phase4_split_keeps_assignment_label_and_feature_blind():
    text = WORKFLOW.read_text()

    assert "split_assignment_uses_feature_values: false" in text
    assert "split_assignment_uses_outcome_values: false" in text
    assert "random_shuffle_used: false" in text
    assert "final_test_separated: true" in text
    assert "phase4_split_frozen: true" in text
    assert "phase4_discovery_checkpoint_claimed: false" in text
