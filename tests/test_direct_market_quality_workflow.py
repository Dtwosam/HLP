from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-direct-market-quality-evidence.yml"
)


def test_direct_market_quality_evidence_is_dispatch_only_and_nonfreezing():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "SAMPLE_SIZE: '20'" in text
    assert "WINDOW_BLOCKS: '100000'" in text
    assert "phase2-market-quality-audit" in text
    assert '"selector_freeze_ready": False' in text
    assert '"source_coverage_complete": False' in text
    assert "phase2-direct-evidence-filter" in text


def test_direct_market_quality_evidence_binds_all_upstream_runs():
    text = WORKFLOW.read_text()

    for name in (
        "quote_run_id",
        "registry_run_id",
        "cohort_run_id",
        "v3_initialize_run_id",
        "v3_swap_run_id",
        "v4_initialize_run_id",
        "v4_swap_run_id",
        "supply_delta_run_id",
    ):
        assert f"{name}:" in text

    assert "direct-v3-swap-sharded.manifest.json" in text
    assert "direct-v4-swap-sharded.manifest.json" in text
    assert "direct-supply-delta-sharded.manifest.json" in text


def test_direct_market_quality_evidence_binds_exact_artifact_hashes():
    text = WORKFLOW.read_text()

    for field in (
        "quote_registry_sha256",
        "quote_decimals_sha256",
        "quote_feed_specs_sha256",
        "plan_sha256",
        "point_sha256",
    ):
        assert field in text

    assert "direct-quote-summary.json" in text
    assert "direct-quotes.jsonl" in text
    assert "direct-quote-decimals.json" in text
    assert "direct-quote-feeds.jsonl" in text
    assert "direct market point SHA drift" in text
    assert "final evidence plan SHA drift" in text
