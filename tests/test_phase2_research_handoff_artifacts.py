from pathlib import Path


WORKFLOWS = [
    Path(".github/workflows/phase2-research-materialize-component.yml"),
    Path(".github/workflows/phase2-research-materialize-composite.yml"),
    Path(".github/workflows/phase2-research-materialize-pons.yml"),
]


def test_research_materializers_publish_compact_handoff_artifacts():
    for workflow in WORKFLOWS:
        text = workflow.read_text()
        assert "Upload research component handoff" in text
        assert "phase2-research-handoff-${{ inputs.component_id }}" in text
        assert "artifacts/phase2-research-component-report.json" in text
        assert "artifacts/*.manifest.json" in text
        assert "HANDOFF_ARTIFACT_DIGEST" in text
        assert "handoff_artifact_digest" in text
