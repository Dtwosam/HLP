from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-flap-curve-coverage.yml"
)


def test_flap_curve_coverage_is_dispatch_only_and_reuses_registry_shards():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "registry_run_id:" in text
    assert "quote_run_id:" in text
    assert "SHARD_COUNT: '256'" in text
    assert "phase2-flap-registry-merged" in text
    assert "phase2-flap-events-${{ matrix.shard }}" in text
    assert "rpc-flap-curve-market-cap-window" in text


def test_flap_curve_coverage_requires_causal_quote_ownership_and_full_pricing():
    text = WORKFLOW.read_text()

    assert "quote_history" in text
    assert "Flap historical quotes lack canonical USD feeds" in text
    assert "--quote-feeds inputs/setup/direct-quote-feeds.jsonl" in text
    assert "Flap curve shard has unpriced points" in text
    assert "Flap merged curve has unpriced points" in text
    assert "validate_flap_curve_coverage_report" in text


def test_flap_curve_coverage_stays_nonfinal_until_dex_lifecycle_merge():
    text = WORKFLOW.read_text()

    assert '"coverage_segment": "bonding_curve"' in text
    assert '"source_coverage_complete": False' in text
    assert "post_graduation_dex_lifecycle_not_yet_merged" in text
    assert "phase2-flap-curve-coverage" in text
    assert "source_coverage_complete: false" in text
    assert "apply_phase2_source_coverage_report" not in text
    assert "git commit" not in text
    assert "git push" not in text
