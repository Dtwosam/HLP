import pytest

from hlp.data.pons_v2_v4_artifacts import (
    resolve_v2_v4_canonical_shard_bindings,
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



def test_canonical_v2_v4_bindings_validate_recursive_geometry():
    manifest = {
        "records": 15,
        "provenance": {
            "storage_mode": "sharded_artifacts",
            "partial_run_id": 456,
            "shards": [
                {
                    **_row(
                        "v4-events-shard-007.jsonl",
                        source="partial",
                    ),
                    "from_block": 100,
                    "to_block": 199,
                },
                {
                    **_row(
                        "v4-events-gap-000.jsonl",
                        source="34234471190",
                    ),
                    "from_block": 200,
                    "to_block": 299,
                },
                {
                    **_row(
                        "v4-events-gap-001.jsonl",
                        source="gaps",
                    ),
                    "from_block": 300,
                    "to_block": 399,
                },
            ],
        },
    }

    bindings = resolve_v2_v4_canonical_shard_bindings(
        manifest,
        current_run_id=123,
        expected_start=100,
        expected_end=399,
    )

    assert [row["run_id"] for row in bindings] == [
        456,
        34_234_471_190,
        123,
    ]
    assert [row["artifact_name"] for row in bindings] == [
        "phase1-pons-v2-v4-7",
        "phase1-pons-v2-v4-gap-000",
        "phase1-pons-v2-v4-gap-001",
    ]


def test_canonical_v2_v4_bindings_reject_discontinuous_coverage():
    manifest = {
        "records": 10,
        "provenance": {
            "storage_mode": "sharded_artifacts",
            "shards": [
                {
                    **_row("v4-events-gap-000.jsonl", source="gaps"),
                    "from_block": 100,
                    "to_block": 199,
                },
                {
                    **_row("v4-events-gap-001.jsonl", source="gaps"),
                    "from_block": 201,
                    "to_block": 300,
                },
            ],
        },
    }
    with pytest.raises(ValueError, match="coverage is discontinuous"):
        resolve_v2_v4_canonical_shard_bindings(
            manifest,
            current_run_id=123,
            expected_start=100,
            expected_end=300,
        )


def test_canonical_v2_v4_bindings_reject_record_drift():
    manifest = {
        "records": 11,
        "provenance": {
            "storage_mode": "sharded_artifacts",
            "shards": [
                {
                    **_row("v4-events-gap-000.jsonl", source="gaps"),
                    "from_block": 100,
                    "to_block": 199,
                },
                {
                    **_row("v4-events-gap-001.jsonl", source="gaps"),
                    "from_block": 200,
                    "to_block": 299,
                },
            ],
        },
    }
    with pytest.raises(ValueError, match="do not match aggregate"):
        resolve_v2_v4_canonical_shard_bindings(
            manifest,
            current_run_id=123,
            expected_start=100,
            expected_end=299,
        )


def test_canonical_v2_v4_bindings_reject_duplicate_binding():
    shard = {
        **_row("v4-events-gap-000.jsonl", source="gaps"),
        "from_block": 100,
        "to_block": 199,
    }
    manifest = {
        "records": 10,
        "provenance": {
            "storage_mode": "sharded_artifacts",
            "shards": [shard, dict(shard)],
        },
    }
    with pytest.raises(
        ValueError,
        match="coverage is discontinuous|binding is duplicated",
    ):
        resolve_v2_v4_canonical_shard_bindings(
            manifest,
            current_run_id=123,
            expected_start=100,
            expected_end=199,
        )
