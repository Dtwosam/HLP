from pathlib import Path


WORKFLOW = Path(".github/workflows/phase4-interactions.yml")


def test_phase4_interactions_is_manual_and_read_only():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "actions: read" in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "git push" not in text


def test_phase4_interactions_consumes_only_discovery_split():
    text = WORKFLOW.read_text()

    assert "chronological_split_handoff_json:" in text
    assert "phase4-discovery-train.jsonl" in text
    assert "build_phase4_chronological_split_handoff" in text
    assert "build_phase4_interaction_report" in text
    assert "build_phase4_interaction_handoff" in text
    assert "Phase-4 interaction artifact exposes validation rows" in text
    assert "Phase-4 interaction artifact exposes final-test rows" in text


def test_phase4_interactions_never_ranks_or_promotes_pairs():
    text = WORKFLOW.read_text()

    assert "pairwise_interactions_examined: true" in text
    assert "interaction_pairs_ranked: false" in text
    assert "validation_rows_consumed: false" in text
    assert "final_test_rows_consumed: false" in text
    assert "signal_promoted: false" in text
    assert "phase4_discovery_checkpoint_claimed: false" in text
