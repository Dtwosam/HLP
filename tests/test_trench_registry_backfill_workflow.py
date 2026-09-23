from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-trench-registry-backfill.yml"
)


def test_trench_registry_backfill_is_dispatch_only_and_sharded():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "SHARD_COUNT: '256'" in text
    assert "rpc-trench-registry-window" in text
    assert "--events-out" in text
    assert "phase2-trench-registry-${{ matrix.shard }}" in text


def test_trench_registry_backfill_merges_global_lifecycle_and_state():
    text = WORKFLOW.read_text()

    assert "build_trench_launch_registry_ordered" in text
    assert "attach_trench_launch_static_states" in text
    assert "ERC20 decimals/totalSupply at launch block" in text
    assert "global chronological event-sourced first LimitReach" in text
    assert "trench-event-shards.manifest.json" in text
    assert "limit_reach_tokens" in text
    assert '"source_coverage_complete": False' in text
    assert "git commit" not in text
    assert "git push" not in text
