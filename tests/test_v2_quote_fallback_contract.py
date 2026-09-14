from pathlib import Path


WORKFLOW = (
    Path(__file__).parents[1]
    / ".github"
    / "workflows"
    / "phase1-pons-v2-lifecycle-eligibility.yml"
)


def test_v2_lifecycle_requires_five_causal_v4_fallback_routes():
    content = WORKFLOW.read_text()
    block = content.split("expected_fallback = {", 1)[1].split("}", 1)[0]
    assert '"owned_quote_assets": 30' in block
    assert '"v3_routes": 25' in block
    assert '"v4_routes": 5' in block
    assert '"v4_causal_initial_assets": 5' in block
    assert '"v3_v4_overlap_assets": 0' in block
