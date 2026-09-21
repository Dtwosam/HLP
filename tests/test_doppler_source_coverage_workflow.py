from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-doppler-source-coverage.yml"
)


def test_doppler_coverage_is_dispatch_only_and_reuses_shared_surfaces():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "registry_run_id:" in text
    assert "v4_swap_run_id:" in text
    assert "supply_delta_run_id:" in text
    assert "quote_run_id:" in text
    assert "phase2-direct-v4-swap-${{ matrix.shard }}" in text
    assert "phase2-direct-supply-delta-manifest" in text
    assert "phase2-doppler-market-window" in text


def test_doppler_coverage_requires_complete_price_and_initialize_population():
    text = WORKFLOW.read_text()

    assert "Doppler shard has unpriced points" in text
    assert "Doppler Initialize point population drift" in text
    assert "Doppler summary does not cover every registry token" in text
    assert "Doppler merged summary has missing/unpriced history" in text
    assert "validate_doppler_coverage_report" in text
    assert '"coverage_status": "complete"' in text


def test_doppler_coverage_validates_but_does_not_mutate_ledger():
    text = WORKFLOW.read_text()

    assert "apply_phase2_source_coverage_report" in text
    assert "doppler-source-coverage-proposed-ledger.json" in text
    assert "Doppler alone must not close Phase-2 source coverage" in text
    assert "git commit" not in text
    assert "git push" not in text


def test_doppler_coverage_publishes_exact_promotion_handoff():
    text = WORKFLOW.read_text()

    assert "steps.upload.outputs.artifact-digest" in text
    assert "report_sha256=" in text
    assert "coverage_run_id: ${GITHUB_RUN_ID}" in text
    assert "coverage_artifact_name: phase2-doppler-source-coverage" in text
    assert (
        "coverage_report_path: doppler-source-coverage-report.json"
        in text
    )
    assert "expected_source_id: doppler" in text
