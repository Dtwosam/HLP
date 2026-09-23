from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3-participant-type-features.yml")


def test_participant_type_workflow_is_manual_and_archive_backed():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" in text
    assert "SOLIDRPC_AUTH_RPC_URL" in text
    assert "eth_getCode" in text
    assert "start_of_confirmation_block" in text
    assert "same_block_future_state_used" in text


def test_participant_type_workflow_binds_entry_and_canonical_trade_tape():
    text = WORKFLOW.read_text()

    assert "phase3-feature-entry" in text
    assert "phase3-canonical-trade-tape" in text
    assert "build_phase3_feature_entry_handoff" in text
    assert "build_phase3_canonical_trade_handoff" in text
    assert "build_phase3_participant_code_query_plan" in text
    assert "materialize_phase3_participant_type_features" in text
    assert "build_phase3_participant_type_feature_handoff" in text


def test_participant_type_workflow_stays_outcome_blind_and_causal():
    text = WORKFLOW.read_text()

    assert "phase2-outcome-labels" not in text
    assert "outcome_rows_consumed" in text
    assert "future_trade_rows_used" in text
    assert "same_block_future_state_allowed" in text
    assert "git push" not in text
    assert "contents: write" not in text


def test_participant_type_workflow_publishes_code_state_provenance():
    text = WORKFLOW.read_text()

    assert "phase3-participant-code-state.jsonl" in text
    assert "participant_code_rows_sha256" in text
    assert "historical_code_state_complete" in text
    assert "phase3-participant-type-features-handoff" in text
