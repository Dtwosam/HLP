import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


def _workflow(name: str) -> str:
    return (ROOT / ".github" / "workflows" / name).read_text()


def test_recovered_completion_config_carries_repaired_pricing_sources():
    config = json.loads(
        (ROOT / ".github" / "phase1-pons-recovered-completion.json").read_text()
    )
    assert config["repaired_v2_lifecycle_run_id"] == 0
    assert config["repaired_v4_fallback_run_id"] == 0
    assert config["validation_generation"] == 8


def test_recovered_completion_one_shot_wires_repaired_pricing_mode_fail_closed():
    content = _workflow("phase1-pons-recovered-completion-one-shot.yml")
    required = (
        "repaired_v2_lifecycle_run_id",
        "repaired_v4_fallback_run_id",
        "REPAIRED_V2_LIFECYCLE_RUN_ID",
        "REPAIRED_V4_FALLBACK_RUN_ID",
        "repaired pricing run IDs must be supplied together",
        "repaired pricing cannot be combined with pricing_run_id",
        "validation_generation != 8",
    )
    for needle in required:
        assert needle in content, needle


def test_recovered_completion_chain_promotes_exact_repaired_pricing_evidence():
    content = _workflow("phase1-pons-recovered-completion-chain.yml")
    required = (
        "repaired_v2_lifecycle_run_id",
        "repaired_v4_fallback_run_id",
        "promote_repaired_pricing:",
        "34900105493",
        "34894335995",
        "279d8016b1f62aef01167650be3cc70e0ca72f6c",
        "09c788e6321b958d1fb78f00e3330605e86435e9",
        "phase1-pons-v1-lifecycle-eligibility",
        "phase1-pons-v2-lifecycle-eligibility",
        "phase1-pons-v3-quote-fallback-full",
        "phase1-pons-v4-quote-fallback-full",
        "phase1-pons-quote-fallback-full",
        '"owned_quote_assets": 30',
        '"v3_routes": 25',
        '"v4_routes": 5',
        '"v4_causal_initial_assets": 5',
        '"v3_v4_overlap_assets": 0',
        '"eligibility_unknown_tokens": 0',
        "repaired pricing run IDs must be supplied together",
        "repaired pricing cannot be combined with pricing_run_id",
    )
    for needle in required:
        assert needle in content, needle

    pricing_job = content.split("\n  pricing:\n", 1)[1].split("\n  ", 1)[0]
    assert "repaired_v2_lifecycle_run_id" in pricing_job
    assert "repaired_v4_fallback_run_id" in pricing_job
    assert "== ''" in pricing_job

    assert "source_eligibility_run_id: ${{ github.run_id }}" in content
    assert "needs.promote_repaired_pricing.result == 'success'" in content
