from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-universe-outcome-dataset.yml"
)


def test_phase2_dataset_checkpoint_is_dispatch_only_and_lineage_bound():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "phase2-universe-freeze" in text
    assert "phase2-outcome-labels" in text
    assert "materialize_phase2_dataset" in text
    assert "Phase-2 universe/outcome lineage drift" in text
    assert "Phase-2 universe/outcome snapshot drift" in text


def test_phase2_dataset_checkpoint_stays_feature_free():
    text = WORKFLOW.read_text()

    assert "hlp-v1-phase2-universe-labels" in text
    assert "phase2_dataset_ready: true" in text
    assert "phase3_features_attached: false" in text
    assert "git push" not in text
    assert "contents: write" not in text
