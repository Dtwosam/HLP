import copy

import pytest

from hlp.data.phase2_execution_runs import (
    PHASE2_EXECUTION_RUN_RECEIPTS_VERSION,
    validate_phase2_execution_run_receipts,
)


REPO = "Dtwosam/HLP"
BRANCH = "phase1/data-acquisition-spike"
SHA = "ab" * 20


def receipt(
    node_id="shared:quote_registry",
    workflow="phase2-direct-quote-registry.yml",
    run_id=123,
):
    return {
        "node_id": node_id,
        "run_id": run_id,
        "workflow_path": f".github/workflows/{workflow}",
        "event": "workflow_dispatch",
        "status": "completed",
        "conclusion": "success",
        "head_branch": BRANCH,
        "head_sha": SHA,
        "run_attempt": 1,
        "repository_full_name": REPO,
        "head_repository_full_name": REPO,
    }


def validate(rows):
    return validate_phase2_execution_run_receipts(
        rows,
        repository_full_name=REPO,
        branch=BRANCH,
    )


def test_execution_run_receipts_accept_exact_successful_runs():
    report = validate([
        receipt(),
        receipt(
            "preflight:archive_authenticated",
            "phase2-archive-rpc-preflight.yml",
            124,
        ),
    ])

    assert report["version"] == PHASE2_EXECUTION_RUN_RECEIPTS_VERSION
    assert report["verified_runs"] == 2
    assert report["completed_node_ids"] == [
        "preflight:archive_authenticated",
        "shared:quote_registry",
    ]
    assert report["all_runs_workflow_dispatch"] is True
    assert report["all_runs_completed_successfully"] is True
    assert report["ledger_commit_runs_accepted"] is False


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("event", "push", "workflow_dispatch"),
        ("status", "in_progress", "not completed"),
        ("conclusion", "failure", "did not succeed"),
        ("head_branch", "main", "branch identity drift"),
        ("repository_full_name", "other/repo", "repository identity drift"),
        (
            "head_repository_full_name",
            "fork/HLP",
            "head-repository identity drift",
        ),
    ],
)
def test_execution_run_receipts_fail_closed_on_run_identity(
    field,
    value,
    match,
):
    row = receipt()
    row[field] = value
    with pytest.raises(ValueError, match=match):
        validate([row])


def test_execution_run_receipts_reject_wrong_workflow_path():
    row = receipt()
    row["workflow_path"] = (
        ".github/workflows/phase2-direct-v3-swap-backfill.yml"
    )
    with pytest.raises(ValueError, match="workflow path drift"):
        validate([row])


def test_execution_run_receipts_reject_duplicate_run_or_node():
    with pytest.raises(ValueError, match="repeats node"):
        validate([receipt(), receipt(run_id=124)])

    second = receipt(
        "preflight:archive_authenticated",
        "phase2-archive-rpc-preflight.yml",
        123,
    )
    with pytest.raises(ValueError, match="reuses run ID"):
        validate([receipt(), second])


def test_execution_run_receipts_never_credit_ledger_commit_run():
    row = receipt(
        "ledger_commit:pools_fun",
        "phase2-source-coverage-ledger-commit.yml",
    )
    with pytest.raises(ValueError, match="canonical coverage ledger"):
        validate([row])


def test_execution_run_receipts_reject_unknown_node():
    row = receipt(node_id="unknown:node")
    with pytest.raises(ValueError, match="unknown Phase-2"):
        validate([row])
