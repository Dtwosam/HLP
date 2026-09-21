from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-trench-limit-market-evidence.yml"
)


def test_trench_limit_market_evidence_is_dispatch_only():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "registry_run_id:" in text
    assert "direct_registry_run_id:" in text
    assert "phase2-trench-registry-merged" in text
    assert "phase2-direct_uniswap_v3-market-registry" in text
    assert "phase2-direct_sushiswap_v3-market-registry" in text
    assert "phase2-direct_uniswap_v4-market-registry" in text


def test_trench_limit_market_evidence_retains_candidates_without_selection():
    text = WORKFLOW.read_text()

    assert "build_trench_limit_market_candidates" in text
    assert "summarize_trench_limit_market_candidates" in text
    assert "all direct V3/V4 candidates retained without selection" in text
    assert "handoff_rule_frozen" in text
    assert "source_coverage_complete" in text
    assert "cannot freeze rule" in text
    assert "cannot close coverage" in text
    assert "apply_phase2_source_coverage_report" not in text
    assert "git commit" not in text
    assert "git push" not in text


def test_trench_limit_market_evidence_is_sha_bound():
    text = WORKFLOW.read_text()

    assert "trench.today registry SHA drift" in text
    assert "direct registry SHA drift" in text
    assert "candidate_manifest_sha256" in text
    assert "steps.upload.outputs.artifact-digest" in text
    assert "report_sha256=" in text
