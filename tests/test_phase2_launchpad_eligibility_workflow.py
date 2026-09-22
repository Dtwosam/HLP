from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-launchpad-eligibility-handoff.yml"
)


def test_launchpad_eligibility_workflow_is_dispatch_only_and_complete_set():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    for source in (
        "pons_v1",
        "pons_v2",
        "pools_fun",
        "pools_trade_instant",
        "pools_trade_lbp",
        "doppler",
        "flap",
        "trench_today",
        "hood_fun_current",
        "hood_fun_previous",
        "noxa",
    ):
        assert f"- {source}" in text
    assert "direct_uniswap_v3" not in text
    assert "direct_uniswap_v4" not in text


def test_launchpad_eligibility_binds_coverage_and_full_summary():
    text = WORKFLOW.read_text()

    assert "expected_coverage_artifact_digest:" in text
    assert "expected_coverage_report_sha256:" in text
    assert "expected_eligibility_artifact_digest:" in text
    assert "expected_eligibility_summary_sha256:" in text
    assert "coverage report SHA drift" in text
    assert "coverage_provenance_sha256" in text
    assert "eligibility summary SHA drift" in text
    assert "build_launchpad_eligibility_handoff" in text
    assert "phase2-source-eligibility.jsonl" in text


def test_launchpad_eligibility_remains_pre_universe():
    text = WORKFLOW.read_text()

    assert "canonical_price_series: true" in text
    assert "phase2_universe_source_ready: true" in text
    assert "phase2_universe_frozen: false" in text
    assert "git commit" not in text
    assert "git push" not in text
