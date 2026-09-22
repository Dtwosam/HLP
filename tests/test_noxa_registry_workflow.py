from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-noxa-registry-backfill.yml"
)


def test_noxa_registry_backfill_is_dispatch_only_and_full_range():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "REQUIRED_START_BLOCK: '61688'" in text
    assert "SNAPSHOT_HEAD: '54486035'" in text
    assert "SHARD_COUNT: '256'" in text
    assert "rpc-noxa-registry-window" in text
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY is required" in text
    assert "CHUNK=50000" in text
    assert "CHUNK=200" not in text


def test_noxa_registry_backfill_validates_state_and_continuity():
    text = WORKFLOW.read_text()

    assert "validate_shard_block_coverage" in text
    assert "noxa_launch_factory_and_launch_block_state" in text
    assert "NOXA state block drift" in text
    assert "duplicate NOXA token across shards" in text
    assert "duplicate NOXA pool across shards" in text
    assert "merged NOXA registry bytes changed" in text
    assert '"continuous_registry_scan": True' in text
    assert '"missing_ranges": []' in text
    assert '"source_coverage_complete": False' in text


def test_noxa_registry_backfill_does_not_promote_coverage():
    text = WORKFLOW.read_text()

    assert "apply_phase2_source_coverage_report" not in text
    assert "git commit" not in text
    assert "git push" not in text
