from pathlib import Path


WORKFLOW = Path(".github/workflows/phase2-archive-fanout-launch.yml")


def test_archive_fanout_launcher_is_manual_explicit_and_non_mutating():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "confirm_archive_fanout:" in text
    assert "default: false" in text
    assert "confirm_archive_fanout=true" in text
    assert "actions: write" in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "canonical_coverage_ledger_mutated" in text


def test_archive_fanout_launcher_requires_exact_first_wave_handoff():
    text = WORKFLOW.read_text()

    assert "first_wave_launch_run_id:" in text
    assert "expected_first_wave_artifact_digest:" in text
    assert "validate_phase2_first_wave_launch_receipt" in text
    assert "first-wave artifact digest drift" in text
    assert "first-wave receipt/control run identity drift" in text
    assert "refreshed_planner_artifact_digest" in text


def test_archive_fanout_launcher_freezes_exact_zero_input_batch():
    text = WORKFLOW.read_text()

    assert "validate_phase2_archive_fanout_launch" in text
    assert "PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS" in text
    assert '"manual_inputs_json": "{}"' in text
    assert "confirm_dispatch" in text
    assert "dispatch_input_names" in text
    assert "unexpectedly used inputs" in text


def test_archive_fanout_launcher_reconciles_paired_dispatch_evidence():
    text = WORKFLOW.read_text()

    assert "phase2-execution-node-dispatch-attempt.json" in text
    assert "phase2-execution-node-dispatch.json" in text
    assert "validate_phase2_node_dispatch_evidence" in text
    assert "attempt_file_sha256=attempt_sha" in text
    assert "archive fan-out dispatcher/control identity drift" in text


def test_archive_fanout_launcher_stops_after_creating_target_runs():
    text = WORKFLOW.read_text()

    assert "target_runs_created" in text
    assert '"target_runs_waited_for_completion": False' in text
    assert '"coverage_promotion_performed": False' in text
    assert '"selector_approval_performed": False' in text
    assert "wait for target workflows, then refresh the planner" in text
    assert "phase2-source-coverage-promotion.yml" not in text
