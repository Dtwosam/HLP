import pytest

from hlp.data.pons_v2_v4_artifacts import (
    resolve_v2_v4_shard_artifact,
)


def _row(file, *, source=None):
    row = {
        "file": file,
        "sha256": "a" * 64,
        "records": 5,
        "from_block": 100,
        "to_block": 200,
    }
    if source is not None:
        row["source"] = source
    return row


def test_original_v2_v4_shard_binds_to_current_run():
    binding = resolve_v2_v4_shard_artifact(
        _row("v4-events-shard-007.jsonl"),
        current_run_id=123,
        partial_run_id=None,
    )
    assert binding["run_id"] == 123
    assert binding["artifact_name"] == "phase1-pons-v2-v4-7"
    assert binding["kind"] == "shard"


def test_recovered_partial_shard_binds_to_partial_run():
    binding = resolve_v2_v4_shard_artifact(
        _row("v4-events-shard-007.jsonl", source="partial"),
        current_run_id=123,
        partial_run_id=456,
    )
    assert binding["run_id"] == 456
    assert binding["artifact_name"] == "phase1-pons-v2-v4-7"


def test_current_recovery_gap_binds_to_current_run():
    binding = resolve_v2_v4_shard_artifact(
        _row("v4-events-gap-007.jsonl", source="gaps"),
        current_run_id=123,
        partial_run_id=456,
    )
    assert binding["run_id"] == 123
    assert binding["artifact_name"] == "phase1-pons-v2-v4-gap-007"
    assert binding["kind"] == "gap"


def test_recursive_prior_gap_binds_to_numeric_source_run():
    binding = resolve_v2_v4_shard_artifact(
        _row("v4-events-gap-060.jsonl", source="34234471190"),
        current_run_id=123,
        partial_run_id=456,
    )
    assert binding["run_id"] == 34_234_471_190
    assert binding["artifact_name"] == "phase1-pons-v2-v4-gap-060"


def test_partial_shard_requires_partial_run():
    with pytest.raises(ValueError, match="positive partial run ID"):
        resolve_v2_v4_shard_artifact(
            _row("v4-events-shard-007.jsonl", source="partial"),
            current_run_id=123,
            partial_run_id=None,
        )


def test_shard_rejects_unknown_source_label():
    with pytest.raises(ValueError, match="shard source label changed"):
        resolve_v2_v4_shard_artifact(
            _row("v4-events-shard-007.jsonl", source="123"),
            current_run_id=123,
            partial_run_id=456,
        )


def test_gap_rejects_unknown_source_label():
    with pytest.raises(ValueError, match="gap source label changed"):
        resolve_v2_v4_shard_artifact(
            _row("v4-events-gap-007.jsonl", source="partial"),
            current_run_id=123,
            partial_run_id=456,
        )
