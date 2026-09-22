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
    assert "materialize_phase3_pons_trade_coverage" in text


def test_pons_trade_coverage_reuses_accepted_research_evidence():
    text = WORKFLOW.read_text()

    assert "accepted_lifecycle_replay_equivalent" in text
    assert "full_inputs_validated" in text
    assert "eligible_token_coverage_complete" in text
    assert "market_registry_sha256" in text
    assert "snapshot_head_block" in text
    assert "canonical_replay" in text


def test_pons_trade_coverage_is_phase3_canonical_descriptor_ready():
    text = WORKFLOW.read_text()

    assert "phase3-trade-coverage-" in text
    assert "canonical_file:" in text
    assert "coverage_file:" in text
    assert "wallet_identity_kind: source_normalized_initiator" in text
    assert "trade_coverage_complete: true" in text
    assert "phase2-outcome-labels" not in text
    assert "git push" not in text
    assert "contents: write" not in text
