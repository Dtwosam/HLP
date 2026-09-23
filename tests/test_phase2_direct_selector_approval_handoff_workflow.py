from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-direct-selector-approval-handoff.yml"
)


def test_selector_approval_handoff_is_manual_and_read_only():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "confirm_prepare_review:" in text
    assert "default: false" in text
    assert "confirm_prepare_review=true" in text
    assert "actions: read" in text
    assert "actions: write" not in text
    assert "contents: read" in text
    assert "contents: write" not in text


def test_selector_approval_handoff_requires_exact_pre_selector_receipt():
    text = WORKFLOW.read_text()

    assert "pre_selector_completion_run_id:" in text
    assert "expected_completion_artifact_digest:" in text
    assert "validate_phase2_pre_selector_wave_completion_receipt" in text
    assert "pre-selector completion artifact digest drift" in text
    assert "pre_selector_completion_control_run_id" in text


def test_selector_approval_handoff_follows_exact_planner_gate():
    text = WORKFLOW.read_text()

    assert "awaiting_explicit_approval_node_ids" in text
    assert "shared:direct_selector_freeze" in text
    assert "requires_explicit_approval" in text
    assert "selector-freeze evidence-run binding drift" in text
    assert "selector-freeze manual-input contract drift" in text


def test_selector_approval_handoff_validates_exact_quality_evidence():
    text = WORKFLOW.read_text()

    assert "phase2-direct-market-quality-evidence.yml" in text
    assert "phase2-direct-market-quality-evidence" in text
    assert "direct-market-quality-evidence-handoff.json" in text
    assert "direct-market-quality-trace.jsonl" in text
    assert "direct-market-candidate-series.jsonl" in text
    assert "direct-market-quality-report.json" in text
    assert "build_phase2_selector_approval_handoff" in text


def test_selector_approval_handoff_never_approves_or_dispatches():
    text = WORKFLOW.read_text()

    assert "freeze_active_quote_liquidity_causal_v1: NOT SET" in text
    assert "approval_required: true" in text
    assert "selector_approval_performed: false" in text
    assert "selector_workflow_dispatched: false" in text
    assert "canonical_coverage_ledger_mutated: false" in text
    assert "/dispatches" not in text



def test_selector_approval_handoff_artifact_binds_control_run_identity():
    text = WORKFLOW.read_text()

    assert '"approval_handoff_control_run_id": int(' in text
    assert 'os.environ["GITHUB_RUN_ID"]' in text
