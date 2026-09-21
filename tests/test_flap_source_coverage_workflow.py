from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-flap-source-coverage.yml"
)


def test_flap_source_coverage_is_dispatch_only_and_exactly_bound():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "registry_run_id:" in text
    assert "curve_run_id:" in text
    assert "expected_curve_artifact_digest:" in text
    assert "expected_curve_report_sha256:" in text
    assert "direct_registry_run_id:" in text
    assert "v3_swap_run_id:" in text
    assert "quote_run_id:" in text
    assert "Flap curve artifact digest drift" in text
    assert "Flap curve report SHA drift" in text


def test_flap_source_coverage_requires_every_graduation_to_resolve():
    text = WORKFLOW.read_text()

    assert "phase2-flap-graduation-markets" in text
    assert "phase2-flap-v3-graduation-registry" in text
    assert "unmatched_address_markets" in text
    assert "all_graduations_resolved" in text
    assert "markets_available_at_graduation" in text
    assert "phase2-v3-registry-event-filter" in text
    assert "phase2-flap-v3-market-window" in text
    assert "one causal snapshot per graduation" in text


def test_flap_source_coverage_is_full_population_and_fully_priced():
    text = WORKFLOW.read_text()

    assert "merge_flap_lifecycle_market_cap_summaries" in text
    assert "Flap launch population contains a token with no price point" in text
    assert "Flap final summary contains unpriced history" in text
    assert "Flap graduated token lacks post-graduation V3 history" in text
    assert "validate_flap_source_coverage_report" in text
    assert "apply_phase2_source_coverage_report" in text
    assert '"coverage_status": "complete"' in text
    assert "expected_source_id: flap" in text
    assert "git commit" not in text
    assert "git push" not in text
    assert "contents: write" not in text
