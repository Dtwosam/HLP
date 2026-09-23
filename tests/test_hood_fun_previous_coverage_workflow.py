from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-hoodfun-previous-coverage.yml"
)


def test_previous_hood_coverage_is_dispatch_only_and_semantic_gated():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "semantics_run_id:" in text
    assert "expected_semantics_artifact_digest:" in text
    assert "expected_semantics_report_sha256:" in text
    assert "verify-semantics:" in text
    assert "semantic artifact digest drift" in text
    assert "semantic report SHA drift" in text
    assert "legacy semantic proof is not complete" in text
    assert "needs: verify-semantics" in text


def test_previous_hood_coverage_binds_semantic_proof_into_pricing():
    text = WORKFLOW.read_text()

    assert "--generation previous" in text
    assert "legacy_semantics_run_id" in text
    assert "legacy_semantics_artifact_digest" in text
    assert "legacy_semantics_report_sha256" in text
    assert "validate_hood_fun_coverage_report" in text
    assert "apply_phase2_source_coverage_report" in text
    assert "expected_source_id: hood_fun_previous" in text
    assert "phase2-hoodfun-previous-coverage" in text
