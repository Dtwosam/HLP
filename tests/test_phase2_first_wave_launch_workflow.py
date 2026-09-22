from pathlib import Path


WORKFLOW = Path(".github/workflows/phase2-first-wave-launch.yml")


def test_first_wave_launcher_is_manual_explicit_and_non_mutating():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "confirm_first_wave:" in text
    assert "default: false" in text
    assert "confirm_first_wave=true" in text
    assert "actions: write" in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "canonical_coverage_ledger_mutated" in text
    assert "canonical_ledger_write_authorized" in text


def test_first_wave_launcher_requires_archive_secret_and_exact_contract():
    text = WORKFLOW.read_text()

    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" in text
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY is not configured" in text
    assert "validate_phase2_first_wave_launch" in text
    assert "validate_phase2_first_wave_completion" in text
    assert "verified_runs" in text
    assert "initial first-wave planner unexpectedly credited runs" in text


def test_first_wave_launcher_checks_default_branch_interfaces():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch_interface_sha256" in text
    assert "phase2-coverage-execution-plan.yml" in text
    assert "phase2-execution-node-dispatch.yml" in text
    assert "phase2-archive-rpc-preflight.yml" in text
    assert "phase2-direct-quote-registry.yml" in text
    assert "default-branch dispatch interface drift" in text


def test_first_wave_launcher_uses_returned_run_ids_and_waits_for_targets():
    text = WORKFLOW.read_text()

    assert 'API_VERSION = "2026-03-10"' in text
    assert "X-GitHub-Api-Version:" in text
    assert 'response["workflow_run_id"]' in text
    assert "wait_run(" in text
    assert "node_dispatch_control_run_ids" in text
    assert "target_run_ids" in text
    assert "refreshed_planner_run_id" in text
    assert "phase2-first-wave-launch-receipt.json" in text


def test_first_wave_launcher_stops_before_archive_fanout():
    text = WORKFLOW.read_text()

    assert "archive_fanout_unlocked" in text
    assert "selector_approval_performed" in text
    assert "review the refreshed planner before launching archive fan-out" in text
    assert "phase2-direct-v3-initialize-backfill.yml" not in text



def test_first_wave_launcher_reconciles_dispatch_attempt_and_final_receipt():
    text = WORKFLOW.read_text()

    assert "phase2-execution-node-dispatch-attempt.json" in text
    assert "validate_phase2_node_dispatch_evidence" in text
    assert "attempt_file_sha256=hashlib.sha256(" in text
    assert "lacks attempt/final evidence" in text
