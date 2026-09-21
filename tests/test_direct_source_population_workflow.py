from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-direct-source-population-handoff.yml"
)


def test_direct_source_population_handoff_is_dispatch_only_and_exact():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "direct_launch_run_id:" in text
    assert "expected_direct_launch_artifact_digest:" in text
    assert "expected_direct_launch_handoff_sha256:" in text
    assert "selector_run_id:" in text
    assert "expected_selector_artifact_digest:" in text
    assert "expected_selector_descriptor_sha256:" in text
    assert "direct launch handoff SHA drift" in text
    assert "direct selector descriptor SHA drift" in text


def test_direct_source_population_handoff_binds_both_prerequisites():
    text = WORKFLOW.read_text()

    assert "phase2-direct-launch-population-handoff-v2" in text
    assert "direct_launch_population_summary_sha256" in text
    assert "direct-market-selector-freeze.json" in text
    assert "selection_rule_frozen" in text
    assert "build_direct_source_populations" in text
    assert "phase2-direct-source-population-handoff-v1" in text


def test_direct_source_population_handoff_remains_noncoverage():
    text = WORKFLOW.read_text()

    assert "canonical_market_selection_applied: false" in text
    assert "source_coverage_complete: false" in text
    assert "git commit" not in text
    assert "git push" not in text
    assert "contents: write" not in text
