from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-research-rehydration-plan.yml"
)


def test_research_rehydration_plan_is_dispatch_only_and_unmaterialized():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "phase2-universe-freeze" in text
    assert "build_phase2_research_rehydration_seed" in text
    assert "build_phase2_research_rehydration_plan" in text
    assert "resolve_launchpad_rehydration_binding" in text
    assert "resolve_direct_rehydration_binding" in text
    assert "research_price_paths_materialized: false" in text
    assert "dump_threshold_frozen: false" in text
    assert "outcome_labels_computed: false" in text


def test_research_rehydration_plan_binds_exact_artifacts_without_shard_downloads():
    text = WORKFLOW.read_text()

    assert "artifact digest drift" in text
    assert "current coverage ledger differs from frozen universe" in text
    assert "handoff summary SHA drift" in text
    assert "direct handoff SHA drift" in text
    assert "phase2-research-rehydration-plan.json" in text
    assert "phase2-*-price-*" not in text
    assert "git push" not in text
    assert "contents: write" not in text
