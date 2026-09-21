from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-direct-launch-population.yml"
)


def test_direct_launch_population_workflow_is_dispatch_only_and_sha_bound():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "attribution_run_id:" in text
    assert "attribution_artifact_name:" in text
    assert "expected_artifact_digest:" in text
    assert "expected_attributed_registry_sha256:" in text
    assert "expected_attribution_report_sha256:" in text
    assert "attribution artifact digest drift" in text
    assert "attributed registry SHA drift" in text
    assert "attribution report SHA drift" in text


def test_direct_launch_population_workflow_is_conclusive_but_nonfreezing():
    text = WORKFLOW.read_text()

    assert "phase2-direct-launch-population" in text
    assert "direct_launch_population_conclusive" in text
    assert "launch_source_coverage_complete" in text
    assert "absence_from_launch_registries_is_conclusive" in text
    assert "direct launch population cannot freeze selector" in text
    assert "direct launch population cannot close source coverage" in text
    assert '"selector_freeze_ready": False' in text
    assert '"source_coverage_complete": False' in text
    assert "git commit" not in text
    assert "git push" not in text
    assert "contents: write" not in text


def test_direct_launch_population_workflow_publishes_provenance_handoff():
    text = WORKFLOW.read_text()

    assert "direct-launch-population-handoff.json" in text
    assert "steps.upload.outputs.artifact-digest" in text
    assert "direct_launch_population_sha256" in text
    assert "attributed_registry_sha256" in text
    assert "attribution_report_sha256" in text
