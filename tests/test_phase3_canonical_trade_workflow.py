from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3-canonical-trade-tape.yml")


def test_canonical_trade_workflow_uses_single_bounded_source_descriptor():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "source_artifacts_json:" in text
    assert "source artifact descriptor count drift" in text
    assert "build_phase2_source_inventory" in text
    assert "set(by_source) != inventory_ids" in text


def test_canonical_trade_workflow_requires_exact_entry_universe_and_sources():
    text = WORKFLOW.read_text()

    assert "phase3-feature-entry" in text
    assert "phase2-universe-freeze" in text
    assert "EXPECTED_FEATURE_ENTRY_HANDOFF_SHA256" in text
    assert "EXPECTED_UNIVERSE_HANDOFF_SHA256" in text
    assert "select_equivalent_artifact_retry" in text
    assert "canonical_trade_rows_sha256" in text
    assert "trade_coverage_complete" in text


def test_canonical_trade_workflow_materializes_expected_downstream_artifact():
    text = WORKFLOW.read_text()

    assert "materialize_phase3_canonical_trade_tape" in text
    assert "build_phase3_canonical_trade_handoff" in text
    assert "phase3-canonical-trade-tape" in text
    assert "phase3-canonical-trades.jsonl" in text
    assert "phase3-canonical-trade-handoff.json" in text
    assert "phase2-outcome-labels" not in text
    assert "git push" not in text
    assert "contents: write" not in text
