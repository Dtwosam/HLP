from pathlib import Path


WORKFLOW = Path(".github/workflows/phase2-universe-freeze.yml")


def test_phase2_universe_freeze_is_dispatch_only_and_requires_14_of_14():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "launchpad_handoffs_json:" in text
    assert "Phase-2 universe freeze requires 14/14 complete coverage" in text
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
        "direct_uniswap_v3",
        "direct_sushiswap_v3",
        "direct_uniswap_v4",
    ):
        assert source in text


def test_phase2_universe_freeze_binds_promoted_coverage_and_exclusions():
    text = WORKFLOW.read_text()

    assert "validate_phase2_universe_source_bundle" in text
    assert "coverage_ledger_sha256" in text
    assert "coverage_provenance_sha256" not in text
    assert "phase2-exclusion-registry-summary.json" in text
    assert "exclusion registry SHA drift" in text
    assert "direct eligibility handoff SHA drift" in text
    assert "normalized eligibility SHA drift" in text


def test_phase2_universe_freeze_emits_only_after_canonical_assembly():
    text = WORKFLOW.read_text()

    assert "build_phase2_universe" in text
    assert "phase2-eligible-universe.jsonl" in text
    assert "phase2-universe-rejected.jsonl" in text
    assert "phase2-universe-freeze-handoff.json" in text
    assert '"phase2_universe_coverage_complete": True' in text
    assert '"phase2_universe_frozen": True' in text
    assert "git commit" not in text
    assert "git push" not in text
    assert "contents: write" not in text
