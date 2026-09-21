from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-hoodfun-current-coverage.yml"
)


def test_hood_current_coverage_is_dispatch_only():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "SHARD_COUNT: '256'" in text
    assert "--generation current" in text


def test_hood_current_coverage_validates_before_promotion():
    text = WORKFLOW.read_text()

    assert "validate_hood_fun_coverage_report" in text
    assert "apply_phase2_source_coverage_report" in text
    assert "hood.fun current coverage did not validate as complete" in text
    assert "hood-current-phase2-validation.json" in text
    assert "hood-current-proposed-ledger.json" in text
    assert "git commit" not in text
    assert "git push" not in text


def test_hood_current_coverage_publishes_exact_promotion_handoff():
    text = WORKFLOW.read_text()

    assert "id: coverage" in text
    assert "report_sha256=" in text
    assert "id: upload" in text
    assert "steps.upload.outputs.artifact-digest" in text
    assert "coverage_run_id: ${GITHUB_RUN_ID}" in text
    assert (
        "coverage_artifact_name: phase2-hoodfun-current-coverage"
        in text
    )
    assert "coverage_report_path: hood-current-coverage.json" in text
    assert "expected_report_sha256: ${REPORT_SHA256}" in text
    assert "expected_source_id: hood_fun_current" in text
