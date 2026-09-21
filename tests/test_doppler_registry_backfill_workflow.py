from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-doppler-registry-backfill.yml"
)


def test_doppler_registry_backfill_is_dispatch_only_and_sharded():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "v4_initialize_run_id:" in text
    assert "quote_run_id:" in text
    assert "SHARD_COUNT: '256'" in text
    assert "rpc-doppler-launch-window" in text
    assert "phase2-doppler-launch-${{ matrix.shard }}" in text


def test_doppler_registry_reuses_shared_v4_and_canonical_quotes():
    text = WORKFLOW.read_text()

    assert "phase2-direct-v4-initialize-merged" in text
    assert "phase2-direct-quote-registry" in text
    assert "shared V4 Initialize SHA drift" in text
    assert "Doppler numeraires lack canonical quote ownership" in text
    assert "build_doppler_v4_registry" in text
    assert "same-tx invariant failed" in text


def test_doppler_registry_keeps_source_coverage_open():
    text = WORKFLOW.read_text()

    assert '"source_coverage_complete": False' in text
    assert "phase2-doppler-registry-merged" in text
    assert "apply_phase2_source_coverage_report" not in text
    assert "git commit" not in text
    assert "git push" not in text
