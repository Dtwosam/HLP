import pytest

from hlp.data.pons_v1_v3_artifacts import (
    resolve_v1_v3_canonical_shard_bindings,
    resolve_v1_v3_shard_artifact,
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


def test_original_v1_v3_shard_binds_to_current_run():
    binding = resolve_v1_v3_shard_artifact(
        _row("v1-v3-events-shard-007.jsonl"),
        current_run_id=123,
        partial_run_id=None,
    )
    assert binding["run_id"] == 123
    assert binding["artifact_name"] == "phase1-pons-v1-v3-7"
    assert binding["kind"] == "shard"


def test_recovered_partial_v1_v3_shard_binds_to_partial_run():
    binding = resolve_v1_v3_shard_artifact(
        _row("v1-v3-events-shard-007.jsonl", source="partial"),
        current_run_id=123,
        partial_run_id=456,
    )
    assert binding["run_id"] == 456
    assert binding["artifact_name"] == "phase1-pons-v1-v3-7"


def test_recursive_prior_v1_v3_gap_binds_to_numeric_source_run():
    binding = resolve_v1_v3_shard_artifact(
        _row("v1-v3-events-gap-060.jsonl", source="34200000000"),
        current_run_id=123,
        partial_run_id=456,
    )
    assert binding["run_id"] == 34_200_000_000
    assert binding["artifact_name"] == "phase1-pons-v1-v3-gap-060"


def test_canonical_v1_v3_bindings_validate_recursive_geometry():
    manifest = {
        "records": 15,
        "provenance": {
            "storage_mode": "sharded_artifacts",
            "partial_run_id": 456,
            "shards": [
                {
                    **_row(
                        "v1-v3-events-shard-007.jsonl",
                        source="partial",
                    ),
                    "from_block": 100,
                    "to_block": 199,
                },
                {
                    **_row(
                        "v1-v3-events-gap-000.jsonl",
                        source="34200000000",
                    ),
                    "from_block": 200,
                    "to_block": 299,
                },
                {
                    **_row(
                        "v1-v3-events-gap-001.jsonl",
                        source="gaps",
                    ),
                    "from_block": 300,
                    "to_block": 399,
                },
            ],
        },
    }
    bindings = resolve_v1_v3_canonical_shard_bindings(
        manifest,
        current_run_id=123,
        expected_start=100,
        expected_end=399,
    )
    assert [row["run_id"] for row in bindings] == [
        456,
        34_200_000_000,
        123,
    ]


def test_canonical_v1_v3_bindings_reject_record_drift():
    manifest = {
        "records": 11,
        "provenance": {
            "storage_mode": "sharded_artifacts",
            "shards": [
                {
                    **_row(
                        "v1-v3-events-gap-000.jsonl",
                        source="gaps",
                    ),
                    "from_block": 100,
                    "to_block": 199,
                },
                {
                    **_row(
                        "v1-v3-events-gap-001.jsonl",
                        source="gaps",
                    ),
                    "from_block": 200,
                    "to_block": 299,
                },
            ],
        },
    }
    with pytest.raises(ValueError, match="do not match aggregate"):
        resolve_v1_v3_canonical_shard_bindings(
            manifest,
            current_run_id=123,
            expected_start=100,
            expected_end=299,
        )


def test_v1_v3_partial_shard_requires_partial_run():
    with pytest.raises(ValueError, match="positive partial run ID"):
        resolve_v1_v3_shard_artifact(
            _row("v1-v3-events-shard-007.jsonl", source="partial"),
            current_run_id=123,
            partial_run_id=None,
        )
