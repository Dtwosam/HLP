"""Evidence-backed GitHub run receipts for the Phase-2 execution DAG."""

from __future__ import annotations

from typing import Iterable, Mapping

from hlp.data.phase2_coverage_execution import (
    COVERAGE_NODE_BY_SOURCE,
    build_phase2_coverage_execution_nodes,
)


PHASE2_EXECUTION_RUN_RECEIPTS_VERSION = (
    "phase2-execution-run-receipts-v2"
)
PHASE2_ALLOWED_POST_RUN_DRIFT_PATHS = (
    ".github/phase2-source-coverage.json",
)


def _known_workflows() -> dict[str, str]:
    output = {
        str(row["node_id"]): str(row["workflow"])
        for row in build_phase2_coverage_execution_nodes()
    }
    for source_id in COVERAGE_NODE_BY_SOURCE:
        output[f"promote:{source_id}"] = (
            "phase2-source-coverage-promotion.yml"
        )
        output[f"ledger_commit:{source_id}"] = (
            "phase2-source-coverage-ledger-commit.yml"
        )
    return output


def _sha(value: object, *, label: str) -> str:
    text = str(value or "").lower()
    if len(text) != 40:
        raise ValueError(f"{label} must be a 40-char commit SHA")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} is not hexadecimal") from exc
    return text


def validate_phase2_execution_run_receipts(
    receipts: Iterable[Mapping[str, object]],
    *,
    repository_full_name: str,
    branch: str,
    current_head_sha: str,
) -> dict:
    """Validate successful, lineage-safe runs before planner completion credit.

    GitHub API lookup and commit comparison happen outside this pure function.
    A historical run remains valid only while the current branch is identical
    to or ahead of that run and every intervening changed path is an explicitly
    allowed canonical-ledger mutation.
    """

    repo = str(repository_full_name or "").strip()
    expected_branch = str(branch or "").strip()
    current_sha = _sha(
        current_head_sha,
        label="Phase-2 execution current_head_sha",
    )
    if not repo or "/" not in repo:
        raise ValueError("Phase-2 execution receipt repository is invalid")
    if not expected_branch:
        raise ValueError("Phase-2 execution receipt branch is empty")

    workflows = _known_workflows()
    allowed_drift = set(PHASE2_ALLOWED_POST_RUN_DRIFT_PATHS)
    seen_nodes: set[str] = set()
    seen_runs: set[int] = set()
    normalized = []

    for raw in receipts:
        row = dict(raw)
        node_id = str(row.get("node_id") or "")
        if node_id not in workflows:
            raise ValueError(
                f"unknown Phase-2 execution receipt node: {node_id!r}"
            )
        if node_id.startswith("ledger_commit:"):
            raise ValueError(
                "ledger commit completion must be represented by the "
                "canonical coverage ledger, not an execution receipt"
            )
        if node_id in seen_nodes:
            raise ValueError(
                f"Phase-2 execution receipt repeats node: {node_id}"
            )
        seen_nodes.add(node_id)

        try:
            run_id = int(row.get("run_id"))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{node_id} execution run_id is invalid"
            ) from exc
        if run_id <= 0:
            raise ValueError(f"{node_id} execution run_id must be positive")
        if run_id in seen_runs:
            raise ValueError(
                f"Phase-2 execution receipt reuses run ID: {run_id}"
            )
        seen_runs.add(run_id)

        workflow_path = str(row.get("workflow_path") or "")
        expected_path = f".github/workflows/{workflows[node_id]}"
        if workflow_path != expected_path:
            raise ValueError(
                f"{node_id} workflow path drift: "
                f"{workflow_path!r} != {expected_path!r}"
            )

        if str(row.get("repository_full_name") or "") != repo:
            raise ValueError(f"{node_id} repository identity drift")
        if str(row.get("head_repository_full_name") or "") != repo:
            raise ValueError(f"{node_id} head-repository identity drift")
        if str(row.get("head_branch") or "") != expected_branch:
            raise ValueError(f"{node_id} branch identity drift")
        if str(row.get("event") or "") != "workflow_dispatch":
            raise ValueError(
                f"{node_id} completion is not a workflow_dispatch run"
            )
        if str(row.get("status") or "") != "completed":
            raise ValueError(f"{node_id} workflow run is not completed")
        if str(row.get("conclusion") or "") != "success":
            raise ValueError(f"{node_id} workflow run did not succeed")

        try:
            run_attempt = int(row.get("run_attempt", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{node_id} run_attempt is invalid"
            ) from exc
        if run_attempt < 1:
            raise ValueError(f"{node_id} run_attempt must be positive")

        head_sha = _sha(
            row.get("head_sha"),
            label=f"{node_id} head_sha",
        )
        lineage_status = str(row.get("lineage_status") or "")
        if lineage_status not in {"identical", "ahead"}:
            raise ValueError(
                f"{node_id} run head is not an ancestor of current HEAD"
            )

        raw_paths = row.get("changed_paths_since_run")
        if not isinstance(raw_paths, list):
            raise ValueError(
                f"{node_id} changed_paths_since_run must be a list"
            )
        changed_paths = [str(value) for value in raw_paths]
        if len(changed_paths) != len(set(changed_paths)):
            raise ValueError(
                f"{node_id} changed_paths_since_run repeats a path"
            )
        changed_paths = sorted(changed_paths)

        if lineage_status == "identical":
            if head_sha != current_sha:
                raise ValueError(
                    f"{node_id} identical lineage has head SHA drift"
                )
            if changed_paths:
                raise ValueError(
                    f"{node_id} identical lineage unexpectedly changed paths"
                )
        else:
            if head_sha == current_sha:
                raise ValueError(
                    f"{node_id} ahead lineage unexpectedly has identical SHA"
                )

        disallowed = sorted(set(changed_paths) - allowed_drift)
        if disallowed:
            raise ValueError(
                f"{node_id} run is stale; branch changed outside the "
                f"canonical coverage ledger: {disallowed}"
            )

        normalized.append({
            "node_id": node_id,
            "run_id": run_id,
            "workflow_path": workflow_path,
            "event": "workflow_dispatch",
            "status": "completed",
            "conclusion": "success",
            "head_branch": expected_branch,
            "head_sha": head_sha,
            "current_head_sha": current_sha,
            "lineage_status": lineage_status,
            "changed_paths_since_run": changed_paths,
            "run_attempt": run_attempt,
            "repository_full_name": repo,
            "head_repository_full_name": repo,
        })

    normalized.sort(key=lambda row: row["node_id"])
    return {
        "version": PHASE2_EXECUTION_RUN_RECEIPTS_VERSION,
        "repository_full_name": repo,
        "branch": expected_branch,
        "current_head_sha": current_sha,
        "verified_runs": len(normalized),
        "completed_node_ids": [
            row["node_id"] for row in normalized
        ],
        "receipts": normalized,
        "allowed_post_run_drift_paths": sorted(allowed_drift),
        "all_runs_workflow_dispatch": True,
        "all_runs_completed_successfully": True,
        "all_runs_current_or_ledger_only_ancestors": True,
        "ledger_commit_runs_accepted": False,
    }
