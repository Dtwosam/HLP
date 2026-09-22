from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3-pons-trade-coverage.yml")


def test_pons_trade_coverage_is_dispatch_only_for_both_versions():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "- pons_v1" in text
    assert "- pons_v2" in text
    assert "phase2-research-materialized-" in text


def test_pons_trade_coverage_reuses_accepted_research_evidence():
    text = WORKFLOW.read_text()

    assert "iter_normalized_pons_trades" in text
    assert "iter_adapt_pons_trades_to_phase3" in text
    assert "accepted_lifecycle_replay_equivalent" in text
    assert "full_inputs_validated" in text
    assert "canonical_market_shards" in text
    assert "source_normalized_initiator" in text


def test_pons_trade_coverage_streams_and_matches_canonical_assembler_contract():
    text = WORKFLOW.read_text()

    assert "heapq.merge" in text
    assert "normalized_trade_tape_sha256" in text
    assert "build_phase3_trade_source_coverage" in text
    assert "phase3-{source_id}-canonical-trades.jsonl" in text
    assert "phase3-{source_id}-trade-coverage.jsonl" in text
    assert "trade_coverage_complete: true" in text
    assert "phase2-outcome-labels" not in text
    assert "git push" not in text
    assert "contents: write" not in text
