from pathlib import Path


WORKFLOW = Path(".github/workflows/phase4-simple-models.yml")


def test_phase4_simple_models_is_manual_and_read_only():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "actions: read" in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "git push" not in text


def test_phase4_simple_models_reuse_frozen_discovery_and_validation():
    text = WORKFLOW.read_text()

    assert "chronological_split_bundle_json:" in text
    assert "validation_artifact_digest" in text
    assert "phase4-discovery-train.jsonl" in text
    assert "phase4-validation.jsonl" in text
    assert "build_phase4_chronological_split_handoff" in text
    assert "build_phase4_simple_model_report" in text
    assert "build_phase4_simple_model_handoff" in text


def test_phase4_simple_models_never_download_final_test_or_select_production():
    text = WORKFLOW.read_text()

    assert "--name\", \"phase4-final-test-slice" not in text
    assert "Phase-4 simple-model validation artifact exposes final-test rows" in text
    assert "preprocessing_fit_on_discovery_only: true" in text
    assert "models_fit_on_discovery_only: true" in text
    assert "validation_rows_consumed: true" in text
    assert "final_test_rows_consumed: false" in text
    assert "production_model_selected: false" in text
    assert "signal_threshold_selected: false" in text
    assert "signal_promoted: false" in text
    assert "phase4_discovery_checkpoint_claimed: false" in text
