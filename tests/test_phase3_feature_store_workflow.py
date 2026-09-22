from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3-feature-store.yml")


def test_feature_store_workflow_requires_exact_staging_and_coverage():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "phase3-feature-staging" in text
    assert "phase3-feature-coverage" in text
    assert "materialize_phase3_feature_store" in text
    assert "build_phase3_feature_store_handoff" in text
    assert "build_phase3_feature_staging_handoff" in text
    assert "build_phase3_feature_coverage_handoff" in text


def test_feature_store_workflow_claims_only_after_full_acceptance():
    text = WORKFLOW.read_text()

    assert "all_registered_families_included: true" in text
    assert "all_registered_features_included: true" in text
    assert "matched_subject_coverage_equal: true" in text
    assert "outcome_rows_consumed: false" in text
    assert "outcome_fields_exposed: false" in text
    assert "future_state_allowed: false" in text
    assert "checkpoint_name: hlp-v1-phase3-feature-store" in text
    assert "final_checkpoint_claimed: true" in text
    assert "git push" not in text
    assert "contents: write" not in text
