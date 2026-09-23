from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-hoodfun-legacy-curve-semantics.yml"
)


def test_legacy_hood_semantics_is_bounded_and_dispatch_only():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "validate_hood_fun_legacy_compatibility" in text
    assert 'compatibility_raw["first_samples"]["token_created"]' in text
    assert 'int(current["first_code_block"]) - 1' in text
    assert "SOLIDRPC_PUBLIC_FILTERED_LOG_BLOCK_CAP" in text


def test_legacy_hood_semantics_proves_supply_and_reserve_conservation():
    text = WORKFLOW.read_text()

    assert "read_erc20_static" in text
    assert "legacy hood.fun supply mismatch" in text
    assert "legacy hood.fun 80/20 split failed" in text
    assert "audit_hood_fun_curve_semantics" in text
    assert '"semantic_proof_complete": True' in text
    assert "coverage_status" not in text
    assert "apply_phase2_source_coverage_report" not in text


def test_legacy_hood_semantics_publishes_exact_handoff():
    text = WORKFLOW.read_text()

    assert "id: proof" in text
    assert "report_sha256=" in text
    assert "id: upload" in text
    assert "steps.upload.outputs.artifact-digest" in text
    assert "semantics_run_id: ${GITHUB_RUN_ID}" in text
    assert (
        "semantics_artifact_name: "
        "phase2-hoodfun-legacy-curve-semantics"
        in text
    )
    assert (
        "expected_semantics_report_sha256: ${REPORT_SHA256}"
        in text
    )

