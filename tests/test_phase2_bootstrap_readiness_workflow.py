from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-bootstrap-workflow-compatibility.yml"
)


def test_bootstrap_compatibility_workflow_is_read_only():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "git push" not in text
    assert "gh workflow run" not in text


def test_bootstrap_compatibility_workflow_checks_narrow_branch():
    text = WORKFLOW.read_text()

    assert "phase2/workflow-dispatch-bootstrap" in text
    assert "required_phase2_manual_workflows" in text
    assert "evaluate_phase2_bootstrap_readiness" in text
    assert "/contents/.github/workflows" in text
    assert "bootstrap_dispatch_surface_ready" in text


def test_bootstrap_compatibility_workflow_fails_closed_on_drift():
    text = WORKFLOW.read_text()

    assert "phase2-bootstrap-workflow-compatibility.json" in text
    assert "if: always()" in text
    assert "Enforce bootstrap compatibility" in text
    assert "surface is stale or incompatible" in text
