from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-source-coverage-promotion.yml"
)


def test_source_coverage_promotion_is_dispatch_only_and_sha_bound():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "coverage_run_id:" in text
    assert "coverage_artifact_name:" in text
    assert "expected_artifact_digest:" in text
    assert "coverage_report_path:" in text
    assert "expected_report_sha256:" in text
    assert "expected_source_id:" in text
    assert "artifact digest drift" in text
    assert "coverage report SHA drift" in text


def test_source_coverage_promotion_is_complete_only_and_non_mutating():
    text = WORKFLOW.read_text()

    assert "apply_phase2_source_coverage_report" in text
    assert "promotion only accepts coverage_status=complete" in text
    assert "phase2-source-coverage.proposed.json" in text
    assert "canonical coverage ledger changed during proposal build" in text
    assert "promotion regressed an already-complete source" in text
    assert "git commit" not in text
    assert "git push" not in text
    assert "contents: write" not in text
