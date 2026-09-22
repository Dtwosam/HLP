from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-archive-fanout-completion.yml"
)


def test_archive_fanout_completion_is_manual_and_non_mutating():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "confirm_completion_refresh:" in text
    assert "default: false" in text
    assert "confirm_completion_refresh=true" in text
    assert "actions: write" in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "canonical_coverage_ledger_mutated" in text


def test_archive_fanout_completion_requires_exact_launch_receipt():
    text = WORKFLOW.read_text()

    assert "archive_fanout_launch_run_id:" in text
    assert "expected_archive_fanout_artifact_digest:" in text
    assert "validate_phase2_archive_fanout_launch_receipt" in text
    assert "archive fan-out artifact digest drift" in text
    assert "archive fan-out receipt/control run identity drift" in text


def test_archive_fanout_completion_requires_all_real_targets_successful():
    text = WORKFLOW.read_text()

    assert "PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS" in text
    assert "build_phase2_coverage_execution_nodes" in text
    assert "archive fan-out target not completed" in text
    assert "archive fan-out target failed" in text
    assert "target_run_ids" in text


def test_archive_fanout_completion_reuses_all_15_dispatcher_receipts():
    text = WORKFLOW.read_text()

    assert "validate_phase2_first_wave_launch_receipt" in text
    assert "exactly 15 unique dispatcher control runs" in text
    assert "node_dispatch_run_ids_json" in text
    assert "validate_phase2_archive_fanout_completion" in text
    assert "phase2-archive-fanout-completion-receipt.json" in text


def test_archive_fanout_completion_stops_at_next_planner():
    text = WORKFLOW.read_text()

    assert '"coverage_promotion_performed": False' in text
    assert '"selector_approval_performed": False' in text
    assert '"canonical_coverage_ledger_mutated": False' in text
    assert "next_ready_node_ids" in text
    assert "phase2-source-coverage-promotion.yml" not in text
