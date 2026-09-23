import pytest

from hlp.data.phase3_transfer_acquisition import (
    PHASE3_TOKEN_DEPLOYMENT_VERSION,
    PHASE3_TRANSFER_BATCH_PLAN_VERSION,
    discover_phase3_token_deployments,
    plan_phase3_transfer_batches,
)


A = "0x" + "11" * 20
B = "0x" + "22" * 20
C = "0x" + "33" * 20


class FakeRpc:
    starts = {A: 10, B: 20, C: 30}

    def find_first_code_block(self, token, *, low, high):
        assert low == 0
        assert high == 100
        return self.starts[token]

    def get_code(self, token, block):
        return (
            "0x6000"
            if block >= self.starts[token]
            else "0x"
        )


def test_deployment_discovery_verifies_exact_code_boundary():
    rows = discover_phase3_token_deployments(
        FakeRpc(),
        [C, A, B, A],
        snapshot_head_block=100,
    )
    assert [row["token"] for row in rows] == [A, B, C]
    assert [row["first_code_block"] for row in rows] == [10, 20, 30]
    assert all(
        row["version"] == PHASE3_TOKEN_DEPLOYMENT_VERSION
        and row["deployment_boundary_verified"] is True
        for row in rows
    )


def test_transfer_batch_plan_uses_earliest_verified_start_in_each_batch():
    deployments = discover_phase3_token_deployments(
        FakeRpc(),
        [A, B, C],
        snapshot_head_block=100,
    )
    batches = plan_phase3_transfer_batches(
        deployments,
        snapshot_head_block=100,
        max_tokens_per_batch=2,
    )
    assert [row["version"] for row in batches] == [
        PHASE3_TRANSFER_BATCH_PLAN_VERSION,
        PHASE3_TRANSFER_BATCH_PLAN_VERSION,
    ]
    assert batches[0]["tokens"] == [A, B]
    assert batches[0]["from_block"] == 10
    assert batches[0]["to_block"] == 100
    assert batches[1]["tokens"] == [C]
    assert batches[1]["from_block"] == 30


def test_transfer_batch_plan_rejects_unverified_deployment():
    rows = [{
        "version": PHASE3_TOKEN_DEPLOYMENT_VERSION,
        "token": A,
        "snapshot_head_block": 100,
        "first_code_block": 10,
        "code_before_empty": False,
        "code_at_boundary_present": True,
        "deployment_boundary_verified": True,
        "outcome_rows_consumed": False,
        "future_state_allowed": False,
    }]
    with pytest.raises(ValueError, match="lacks code_before_empty"):
        plan_phase3_transfer_batches(
            rows,
            snapshot_head_block=100,
        )
