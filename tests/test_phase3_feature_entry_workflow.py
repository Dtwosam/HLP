from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3-feature-entry.yml")


def test_phase3_entry_is_dispatch_only_and_never_downloads_outcome_rows():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "phase2-universe-outcome-dataset-handoff" in text
    assert "phase2-universe-outcome-dataset\n" not in text
    assert "phase2-outcome-labels.jsonl" not in text
    assert "materialize_phase3_feature_subjects" in text
    assert "outcome_rows_consumed: false" in text


def test_phase3_entry_hardens_feature_cutoff_and_future_state_boundary():
    text = WORKFLOW.read_text()

    assert "snapshot_kind: first_major_dump_confirmation" in text
    assert "outcome_fields_exposed: false" in text
    assert "future_state_allowed: false" in text
    assert "phase3_feature_values_computed: false" in text
    assert "phase3_feature_entry_ready: true" in text
    assert "git push" not in text
    assert "contents: write" not in text
