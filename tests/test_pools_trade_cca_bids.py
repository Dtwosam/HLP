from hlp.data.pools_trade_cca_bids import (
    PHASE3_CCA_FILL_HANDOFF_VERSION,
    build_phase3_cca_fill_handoff,
    reconcile_cca_bid_fills,
)
from hlp.data.types import CcaBidExited, CcaBidSubmitted


AUCTION = "0x" + "11" * 20
OWNER = "0x" + "22" * 20


def submitted(bid_id=1, amount=1000):
    return CcaBidSubmitted(
        auction=AUCTION,
        bid_id=bid_id,
        owner=OWNER,
        price_q96=10,
        amount_raw=amount,
        block_number=10,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=1,
        log_index=2,
    )


def exited(bid_id=1, tokens=20, refund=250):
    return CcaBidExited(
        auction=AUCTION,
        bid_id=bid_id,
        owner=OWNER,
        tokens_filled_raw=tokens,
        currency_refunded_raw=refund,
        block_number=20,
        transaction_hash="0x" + "bb" * 32,
        transaction_index=1,
        log_index=3,
    )


def test_reconcile_cca_fill_uses_exact_exit_accounting():
    fills, summary = reconcile_cca_bid_fills(
        [submitted()],
        [exited()],
    )
    assert fills[0]["owner"] == OWNER
    assert fills[0]["token_amount_raw"] == 20
    assert fills[0]["quote_amount_raw"] == 750
    assert summary["complete_fill_attribution"] is True
    assert summary["unresolved_bids"] == 0


def test_reconcile_cca_full_refund_is_not_a_trade():
    fills, summary = reconcile_cca_bid_fills(
        [submitted()],
        [exited(tokens=0, refund=1000)],
    )
    assert fills == []
    assert summary["fully_refunded_bids"] == 1
    assert summary["complete_fill_attribution"] is True


def test_reconcile_cca_unresolved_bid_stays_fail_closed():
    fills, summary = reconcile_cca_bid_fills([submitted()], [])
    assert fills == []
    assert summary["unresolved_bids"] == 1
    assert summary["complete_fill_attribution"] is False



def complete_summary():
    sha = "ab" * 32
    return {
        "version": "phase3-pools-trade-cca-fill-backfill-v1",
        "source_id": "pools_trade_lbp",
        "registry_run_id": 123,
        "registry_artifact_digest": "sha256:" + sha,
        "registry_sha256": sha,
        "registered_initializers": 2,
        "required_start_block": 10,
        "snapshot_head_block": 100,
        "submitted_bids": 3,
        "exited_bids": 3,
        "executed_fills": 2,
        "fully_refunded_bids": 1,
        "unresolved_bids": 0,
        "submitted_sharded_sha256": sha,
        "exited_sharded_sha256": sha,
        "finalized_fills_sha256": sha,
        "canonical_trade_rows": 2,
        "canonical_trade_rows_sha256": sha,
        "wallet_identity_kind": "cca_bid_owner",
        "wallet_identity_source": "BidSubmitted.owner",
        "historical_event_scan_complete": True,
        "complete_fill_attribution": True,
        "canonical_trade_adapter_complete": True,
        "source_membership_bound_to_phase2_registry": True,
        "source_coverage_complete": False,
        "outcome_rows_consumed": False,
        "future_state_allowed": False,
        "phase3_cca_fill_backfill_ready": True,
    }


def test_cca_fill_handoff_requires_complete_accounting():
    sha = "ab" * 32
    handoff = build_phase3_cca_fill_handoff(
        complete_summary(),
        summary_sha256=sha,
    )
    assert handoff["version"] == PHASE3_CCA_FILL_HANDOFF_VERSION
    assert handoff["wallet_identity_kind"] == "cca_bid_owner"
    assert handoff["canonical_trade_rows"] == 2
    assert handoff["source_coverage_complete"] is False


def test_cca_fill_handoff_rejects_unresolved_bids():
    row = complete_summary()
    row["unresolved_bids"] = 1
    row["complete_fill_attribution"] = False
    import pytest
    with pytest.raises(ValueError, match="lacks complete_fill_attribution"):
        build_phase3_cca_fill_handoff(
            row,
            summary_sha256="ab" * 32,
        )
