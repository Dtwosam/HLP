from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-default-branch-dispatch-readiness.yml"
)


def test_default_branch_readiness_workflow_is_read_only():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "git push" not in text
    assert "gh workflow run" not in text


def test_default_branch_readiness_checks_repository_default_branch():
    text = WORKFLOW.read_text()

    assert 'metadata.get("default_branch")' in text
    assert "/contents/.github/workflows" in text
    assert "evaluate_phase2_default_branch_readiness" in text
    assert "phase2_first_wave_dispatch_ready" in text
    assert "phase2_full_coverage_dag_dispatch_ready" in text
    assert "phase2_coverage_state_mutated" in text



def test_default_branch_readiness_hashes_manual_dispatch_interfaces():
    text = WORKFLOW.read_text()

    assert "required_phase2_manual_workflows" in text
    assert "workflow_dispatch_interface_sha256" in text
    assert "expected_dispatch_interface_sha256_by_name" in text
    assert "available_dispatch_interface_sha256_by_name" in text
    assert "incompatible_required_workflows" in text
    assert "first_wave_incompatible_workflow_names" in text
    assert "dispatch_interface_compatibility_checked" in text
