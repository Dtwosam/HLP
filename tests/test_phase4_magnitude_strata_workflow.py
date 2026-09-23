from pathlib import Path


WORKFLOW = Path(".github/workflows/phase4-magnitude-strata.yml")


def test_phase4_magnitude_is_manual_and_read_only():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "actions: read" in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "git push" not in text


def test_phase4_magnitude_consumes_only_discovery_split():
    text = WORKFLOW.read_text()

    assert "chronological_split_handoff_json:" in text
    assert "phase4-discovery-train.jsonl" in text
    assert "build_phase4_chronological_split_handoff" in text
    assert "build_phase4_magnitude_strata_report" in text
    assert "build_phase4_magnitude_strata_handoff" in text
    assert "Phase-4 magnitude artifact exposes validation rows" in text
    assert "Phase-4 magnitude artifact exposes final-test rows" in text


def test_phase4_magnitude_never_ranks_or_promotes():
    text = WORKFLOW.read_text()

    assert "ordinary_5x_vs_10x_plus_compared: true" in text
    assert "ordinary_5x_vs_20x_plus_compared: true" in text
    assert "validation_rows_consumed: false" in text
    assert "final_test_rows_consumed: false" in text
    assert "candidate_features_ranked: false" in text
    assert "signal_promoted: false" in text
    assert "phase4_discovery_checkpoint_claimed: false" in text
