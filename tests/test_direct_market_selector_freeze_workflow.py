from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-direct-market-selector-freeze.yml"
)


def test_direct_selector_freeze_is_dispatch_only_and_explicit():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "freeze_active_quote_liquidity_causal_v1:" in text
    assert "selector freeze requires explicit approval" in text
    assert "evidence_run_id:" in text
    assert "expected_artifact_digest:" in text
    assert "expected_handoff_sha256:" in text


def test_direct_selector_freeze_binds_exact_v2_evidence():
    text = WORKFLOW.read_text()

    assert "phase2-direct-market-quality-evidence-v2" in text
    assert "selector evidence artifact digest drift" in text
    assert "selector evidence handoff SHA drift" in text
    assert "selector evidence final file SHA drift" in text
    assert "direct-market-quality-trace.jsonl" in text
    assert "direct-market-candidate-series.jsonl" in text
    assert "direct-market-quality-report.json" in text
    assert "build_direct_selector_freeze" in text


def test_direct_selector_freeze_does_not_claim_source_coverage():
    text = WORKFLOW.read_text()

    assert "selection_rule_frozen: true" in text
    assert "source_coverage_complete: false" in text
    assert "selector freeze cannot close direct source coverage" in text
    assert "git commit" not in text
    assert "git push" not in text
    assert "contents: write" not in text
