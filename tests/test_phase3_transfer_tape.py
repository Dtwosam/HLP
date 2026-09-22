from hlp.data.phase3_transfer_tape import (
    PHASE3_CANONICAL_TRANSFER_TAPE_VERSION,
    PHASE3_TRANSFER_TOKEN_COVERAGE_VERSION,
    adapt_erc20_transfers_to_phase3,
    build_phase3_canonical_transfer_handoff,
    build_phase3_transfer_token_coverage,
    materialize_phase3_canonical_transfer_tape,
)


SHA = "ab" * 32
TOKEN = "0x" + "11" * 20
A = "0x" + "aa" * 20
B = "0x" + "bb" * 20
ZERO = "0x" + "00" * 20


def decoded(block, from_address, to_address, value):
    return {
        "token": TOKEN,
        "from_address": from_address,
        "to_address": to_address,
        "value_raw": value,
        "block_number": block,
        "transaction_hash": "0x" + f"{block:064x}",
        "transaction_index": 0,
        "log_index": 0,
    }


def entry():
    return {
        "version": "phase3-feature-entry-handoff-v1",
        "snapshot_head_block": 100,
        "eligible_universe_sha256": SHA,
        "universe_tokens": 1,
        "outcome_rows_consumed": False,
        "future_state_allowed": False,
        "phase3_feature_entry_ready": True,
    }


def test_transfer_adapter_and_token_coverage_require_initial_mint():
    rows = adapt_erc20_transfers_to_phase3([
        decoded(1, ZERO, A, 1000),
        decoded(2, A, B, 200),
    ])
    coverage = build_phase3_transfer_token_coverage(
        TOKEN,
        rows,
        snapshot_head_block=100,
        search_from_block=1,
        raw_transfer_tape_sha256=SHA,
        historical_event_scan_complete=True,
    )
    assert coverage["version"] == PHASE3_TRANSFER_TOKEN_COVERAGE_VERSION
    assert coverage["canonical_transfer_rows"] == 2
    assert coverage["initial_mint_coverage_complete"] is True
    assert coverage["transfer_coverage_complete"] is True


def test_transfer_coverage_rejects_history_starting_after_mint():
    import pytest

    rows = adapt_erc20_transfers_to_phase3([
        decoded(2, A, B, 200),
    ])
    with pytest.raises(ValueError, match="lacks initial mint"):
        build_phase3_transfer_token_coverage(
            TOKEN,
            rows,
            snapshot_head_block=100,
            search_from_block=2,
            raw_transfer_tape_sha256=SHA,
            historical_event_scan_complete=True,
        )


def test_canonical_transfer_tape_requires_exact_universe_coverage(tmp_path):
    rows = adapt_erc20_transfers_to_phase3([
        decoded(1, ZERO, A, 1000),
        decoded(2, A, B, 200),
    ])
    coverage = build_phase3_transfer_token_coverage(
        TOKEN,
        rows,
        snapshot_head_block=100,
        search_from_block=1,
        raw_transfer_tape_sha256=SHA,
        historical_event_scan_complete=True,
    )
    manifest, summary = materialize_phase3_canonical_transfer_tape(
        [{
            "token": TOKEN,
            "universe_status": "eligible",
        }],
        {TOKEN: rows},
        [coverage],
        feature_entry_handoff=entry(),
        output=tmp_path / "transfers.jsonl",
    )
    assert manifest["records"] == 2
    assert summary["version"] == PHASE3_CANONICAL_TRANSFER_TAPE_VERSION
    assert summary["covered_tokens"] == 1
    assert summary["transfer_coverage_complete"] is True
    assert summary["phase3_canonical_transfer_tape_ready"] is True


def test_canonical_transfer_handoff_is_holder_compatible():
    summary = {
        "version": PHASE3_CANONICAL_TRANSFER_TAPE_VERSION,
        "snapshot_head_block": 100,
        "eligible_universe_sha256": SHA,
        "universe_tokens": 1,
        "token_coverage_sha256": SHA,
        "transfer_rows": 2,
        "canonical_transfer_rows_sha256": SHA,
        "historical_event_scan_complete": True,
        "initial_mint_coverage_complete": True,
        "transfer_coverage_complete": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "phase3_canonical_transfer_tape_ready": True,
    }
    handoff = build_phase3_canonical_transfer_handoff(
        summary,
        tape_summary_sha256=SHA,
        feature_entry_handoff_sha256=SHA,
    )
    assert handoff["version"] == "phase3-canonical-transfer-handoff-v1"
    assert handoff["initial_mint_coverage_complete"] is True
    assert handoff["transfer_coverage_complete"] is True
