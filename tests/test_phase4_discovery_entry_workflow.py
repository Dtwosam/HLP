from pathlib import Path


WORKFLOW = Path(".github/workflows/phase4-discovery-entry.yml")


def test_phase4_discovery_entry_is_manual_and_read_only():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "actions: read" in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "git push" not in text


def test_phase4_discovery_entry_uses_compact_lineage_descriptors():
    text = WORKFLOW.read_text()

    assert "phase2_dataset_handoff_json:" in text
    assert "feature_entry_handoff_json:" in text
    assert "feature_coverage_handoff_json:" in text
    assert "feature_store_handoff_json:" in text
    input_lines = [
        line
        for line in text.splitlines()
        if line.startswith("      ")
        and not line.startswith("        ")
        and line.endswith(":")
    ]
    assert len(input_lines) == 4


def test_phase4_discovery_entry_rebuilds_full_checkpoint_chain():
    text = WORKFLOW.read_text()

    assert "build_phase2_dataset_handoff" in text
    assert "build_phase3_feature_entry_handoff" in text
    assert "build_phase3_feature_coverage_handoff" in text
    assert "build_phase3_feature_store_handoff" in text
    assert "materialize_phase4_discovery_entry" in text
    assert "build_phase4_discovery_entry_handoff" in text
    assert "phase2-universe-outcome-dataset" in text
    assert "phase3-feature-entry" in text
    assert "phase3-feature-coverage" in text
    assert "phase3-feature-store" in text


def test_phase4_discovery_entry_never_claims_discovery_checkpoint():
    text = WORKFLOW.read_text()

    assert "labels_joined_after_feature_freeze: true" in text
    assert "feature_values_mutated: false" in text
    assert "phase4_discovery_entry_ready: true" in text
    assert "phase4_discovery_checkpoint_claimed: false" in text
    assert "phase4_discovery_checkpoint_claimed: true" not in text
