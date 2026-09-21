from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-flap-registry-backfill.yml"
)


def test_flap_registry_backfill_is_dispatch_only_and_sharded():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "REQUIRED_START_BLOCK: '4180724'" in text
    assert "SNAPSHOT_HEAD: '54486035'" in text
    assert "SHARD_COUNT: '256'" in text
    assert "rpc-flap-tape" in text
    assert "phase2-flap-events-${{ matrix.shard }}" in text


def test_flap_registry_backfill_builds_one_global_event_sourced_registry():
    text = WORKFLOW.read_text()

    assert "validate_shard_block_coverage" in text
    assert "build_flap_launch_registry_ordered" in text
    assert "iter_sharded_jsonl" in text
    assert "global chronological event-sourced configuration" in text
    assert "flap-event-shards.manifest.json" in text
    assert "flap-registry.jsonl" in text
    assert "flap-registry-summary.json" in text
    assert '"source_coverage_complete": False' in text
