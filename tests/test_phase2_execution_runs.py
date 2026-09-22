import pytest

from hlp.data.phase2_execution_runs import (
    PHASE2_ALLOWED_POST_RUN_DRIFT_PATHS,
    PHASE2_EXECUTION_RUN_RECEIPTS_VERSION,
    validate_phase2_execution_run_receipts,
)


REPO = "Dtwosam/HLP"
BRANCH = "phase1/data-acquisition-spike"
RUN_SHA = "ab" * 20
CURRENT_SHA = "cd" * 20


def receipt(
    node_id="shared:quote_registry",
    workflow="phase2-direct-quote-registry.yml",
    run_id=123,
    *,
    head_sha=RUN_SHA,
    lineage_status="ahead",
    changed_paths=None,
):
    return {
        "node_id": node_id,
        "run_id": run_id,
        "workflow_path": f".github/workflows/{workflow}",
        "event": "workflow_dispatch",
        "status": "completed",
        "conclusion": "success",
        "head_branch": BRANCH,
        "head_sha": head_sha,
        "lineage_status": lineage_status,
        "changed_paths_since_run": (
            list(PHASE2_ALLOWED_POST_RUN_DRIFT_PATHS)
            if changed_paths is None
            else changed_paths
        ),
        "run_attempt": 1,
        "repository_full_name": REPO,
        "head_repository_full_name": REPO,
    }


def validate(rows, *, current_head_sha=CURRENT_SHA):
    return validate_phase2_execution_run_receipts(
        rows,
        repository_full_name=REPO,
        branch=BRANCH,
        current_head_sha=current_head_sha,
    )


def test_execution_run_receipts_accept_ledger_only_ancestor_runs():
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
    assert report["all_runs_current_or_ledger_only_ancestors"] is True
    assert report["ledger_commit_runs_accepted"] is False


def test_execution_run_receipts_accept_current_head_runs():
    row = receipt(
        head_sha=CURRENT_SHA,
        lineage_status="identical",
        changed_paths=[],
    )
    report = validate([row])

    assert report["receipts"][0]["lineage_status"] == "identical"
    assert report["receipts"][0]["changed_paths_since_run"] == []


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


def test_execution_run_receipts_reject_diverged_or_behind_run():
    row = receipt()
    row["lineage_status"] = "diverged"
    with pytest.raises(ValueError, match="not an ancestor"):
        validate([row])


def test_execution_run_receipts_reject_non_ledger_branch_drift():
    row = receipt(
        changed_paths=[
            ".github/phase2-source-coverage.json",
            "src/hlp/data/phase2_coverage.py",
        ]
    )
    with pytest.raises(ValueError, match="run is stale"):
        validate([row])


def test_execution_run_receipts_reject_invalid_identical_lineage():
    row = receipt(
        lineage_status="identical",
        changed_paths=[],
    )
    with pytest.raises(ValueError, match="head SHA drift"):
        validate([row])

    row = receipt(
        head_sha=CURRENT_SHA,
        lineage_status="identical",
        changed_paths=[".github/phase2-source-coverage.json"],
    )
    with pytest.raises(ValueError, match="unexpectedly changed paths"):
        validate([row])
