from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-direct-origin-pons-attribution.yml"
)


def test_direct_pons_origin_attribution_is_dispatch_only_and_inconclusive():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "phase2-direct-origin-attribution" in text
    assert '"launch_source_coverage_complete": False' in text
    assert '"absence_from_launch_registries_is_conclusive": False' in text
    assert '"source_coverage_complete": False' in text


def test_direct_pons_origin_attribution_uses_accepted_descriptor_artifacts():
    text = WORKFLOW.read_text()

    assert ".github/phase2-pons-source-coverage.json" in text
    assert "artifact_id" in text
    assert "artifact_digest" in text
    assert "artifact_run_id" in text
    assert "lifecycle_sha256" in text
    assert "pons-v1-lifecycle-eligibility.jsonl" in text
    assert "pons-v2-lifecycle-eligibility.jsonl" in text


def test_direct_pons_origin_attribution_publishes_per_source_registries():
    text = WORKFLOW.read_text()

    for source in (
        "direct_uniswap_v3",
        "direct_sushiswap_v3",
        "direct_uniswap_v4",
    ):
        assert f"{source}-attributed.jsonl" in text

    assert "direct-market-pons-attribution-handoff.json" in text
