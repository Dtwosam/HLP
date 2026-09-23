from pathlib import Path


WORKFLOW = Path(".github/workflows/phase4-discovery-checkpoint.yml")


def test_phase4_checkpoint_is_manual_and_read_only():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "actions: read" in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "git push" not in text


def test_phase4_checkpoint_rebuilds_full_research_chain():
    text = WORKFLOW.read_text()

    assert "chronological_split_handoff_json:" in text
    assert "base_rate_handoff_json:" in text
    assert "univariate_handoff_json:" in text
    assert "hypothesis_freeze_handoff_json:" in text
    assert "validation_handoff_json:" in text
    assert "build_phase4_chronological_split_handoff" in text
    assert "build_phase4_base_rate_handoff" in text
    assert "build_phase4_univariate_handoff" in text
    assert "build_phase4_hypothesis_freeze_handoff" in text
    assert "build_phase4_validation_handoff" in text
    assert "build_phase4_discovery_ledger" in text
    assert "build_phase4_discovery_handoff" in text


def test_phase4_checkpoint_closes_discovery_without_opening_final_test():
    text = WORKFLOW.read_text()

    assert "rejected_hypotheses_logged: true" in text
    assert "unseen_slice_validation_complete: true" in text
    assert "multiple_testing_control_applied: true" in text
    assert "final_test_rows_consumed: false" in text
    assert "signal_promoted: false" in text
    assert "phase5_model_started: false" in text
    assert "phase4_discovery_checkpoint_claimed: true" in text
    assert "phase4_discovery_complete: true" in text
    assert "phase4-final-test-slice" not in text



def test_phase4_checkpoint_requires_complete_experiment_suite():
    text = WORKFLOW.read_text()

    assert "magnitude_strata_handoff_json:" in text
    assert "nonlinear_handoff_json:" in text
    assert "interaction_handoff_json:" in text
    assert "simple_model_handoff_json:" in text
    assert "stability_handoff_json:" in text
    assert "build_phase4_magnitude_strata_handoff" in text
    assert "build_phase4_nonlinear_handoff" in text
    assert "build_phase4_interaction_handoff" in text
    assert "build_phase4_simple_model_handoff" in text
    assert "build_phase4_stability_handoff" in text
    assert "magnitude_strata_examined: true" in text
    assert "nonlinear_relationships_examined: true" in text
    assert "pairwise_interactions_examined: true" in text
    assert "transparent_simple_models_examined: true" in text
    assert "repeated_sampling_stability_examined: true" in text
    assert "chronological_stability_examined: true" in text
    assert "optional_cluster_sequence_disposition_recorded: true" in text
    assert "Phase-4 discovery checkpoint remains blocked until" not in text
