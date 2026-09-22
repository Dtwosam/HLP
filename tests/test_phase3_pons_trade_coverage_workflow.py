from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3-pons-trade-coverage.yml")


def test_pons_trade_coverage_is_dispatch_only_and_binds_phase2_research():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "phase2-research-materialized-" in text
    assert "phase3-feature-entry" in text
    assert "phase2-universe-freeze" in text
    assert "PONS_RESEARCH_ARTIFACTS_JSON" in text


def test_pons_trade_coverage_streams_normalized_and_canonical_tapes():
    text = WORKFLOW.read_text()

    assert "iter_normalized_pons_trades" in text
    assert "iter_adapt_pons_trades_to_phase3" in text
    assert "build_phase3_trade_source_coverage" in text
    assert "phase3-pons_v1-canonical-trades.jsonl" not in text
    assert 'f"artifacts/phase3-{source_id}-canonical-trades.jsonl"' in text
    assert "source_normalized_initiator" in text


def test_pons_trade_coverage_emits_two_canonical_source_descriptors():
    text = WORKFLOW.read_text()

    assert '"complete_sources": 2' in text
    assert '"trade_coverage_complete": True' in text
    assert '"outcome_rows_consumed": False' in text
    assert '"future_state_allowed": False' in text
    assert "phase3-pons-trade-coverage" in text
    assert "git push" not in text
    assert "contents: write" not in text
