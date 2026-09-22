from pathlib import Path


WORKFLOW = Path(".github/workflows/phase2-exclusion-registry.yml")


def test_phase2_exclusion_registry_is_dispatch_only():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "RobinhoodAssetsClient" in text
    assert "build_phase2_exclusion_registry" in text


def test_phase2_exclusion_registry_is_address_only_and_sha_bound():
    text = WORKFLOW.read_text()

    assert "exact_normalized_address_only" in text
    assert "official_assets_sha256" in text
    assert "exclusion_registry_sha256" in text
    assert "registry_sha256=" in text
    assert "summary_sha256=" in text
    assert "steps.upload.outputs.artifact-digest" in text
    assert "phase2_universe_frozen: false" in text
    assert "git commit" not in text
    assert "git push" not in text
