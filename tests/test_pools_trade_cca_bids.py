from hlp.data.pools_trade_cca_bids import reconcile_cca_bid_fills
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
