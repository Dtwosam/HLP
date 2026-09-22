from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3-canonical-transfer-tape.yml")


def test_transfer_workflow_binds_universe_deployment_and_transfer_coverage():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "phase3-feature-entry" in text
    assert "phase2-universe-freeze" in text
    assert "discover_phase3_token_deployments" in text
    assert "plan_phase3_transfer_batches" in text
    assert "build_phase3_transfer_token_coverage" in text
    assert "materialize_phase3_canonical_transfer_tape" in text
    assert "phase3-canonical-transfer-tape" in text


def test_transfer_workflow_requires_authenticated_logs_not_keyless_full_scan():
    text = WORKFLOW.read_text()

    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" in text
    assert "requires_authenticated_archive_logs" in text
    assert "200-block filtered-log cap" in text
    assert "SOLIDRPC_AUTH_RPC_URL" in text
    assert "chunk_size=50_000" in text


def test_transfer_workflow_preserves_leakage_and_repo_guards():
    text = WORKFLOW.read_text()

    assert "phase2-outcome-labels" not in text
    assert "outcome_rows_consumed: false" in text
    assert "future_state_allowed" in text
    assert "initial_mint_coverage_complete: true" in text
    assert "transfer_coverage_complete: true" in text
    assert "git push" not in text
    assert "contents: write" not in text
