import hashlib
import json

import pytest

from hlp.data.sharded_tape import (
    canonical_jsonl_bytes,
    iter_sharded_jsonl,
    iter_sharded_jsonl_matching_field_values,
    iter_validated_jsonl_matching_field_values,
    validate_shard_block_coverage,
    write_virtual_jsonl_manifest,
)
from hlp.data.snapshot import write_jsonl_snapshot


def _build_tape(tmp_path):
    rows_a = [
        {"block_number": 10, "value": "a"},
        {"block_number": 11, "value": "b"},
    ]
    rows_b = [{"block_number": 12, "value": "c"}]
    manifests = []
    digest = hashlib.sha256()
    for name, rows, lo, hi in (
        ("events-000.jsonl", rows_a, 10, 11),
        ("events-001.jsonl", rows_b, 12, 12),
    ):
        shard = write_jsonl_snapshot(
            rows,
            output=tmp_path / name,
            provenance={
                "chain_id": 4663,
                "from_block": lo,
                "to_block": hi,
            },
        )
        for row in rows:
            digest.update(canonical_jsonl_bytes(row))
        manifests.append(
            {
                "file": name,
                "sha256": shard["sha256"],
                "records": shard["records"],
                "from_block": lo,
                "to_block": hi,
            }
        )
    aggregate = write_virtual_jsonl_manifest(
        manifest_path=tmp_path / "events-full.jsonl.manifest.json",
        path_name="events-full.jsonl",
        records=3,
        sha256=digest.hexdigest(),
        provenance={
            "source": "test_sharded_tape",
            "chain_id": 4663,
            "storage_mode": "sharded_artifacts",
            "shards": manifests,
        },
    )
    return aggregate


def test_iter_sharded_jsonl_validates_and_streams(tmp_path):
    aggregate = _build_tape(tmp_path)
    rows = list(
        iter_sharded_jsonl(
            tmp_path,
            tmp_path / "events-full.jsonl.manifest.json",
        )
    )
    assert [row["block_number"] for row in rows] == [10, 11, 12]
    assert aggregate["records"] == 3


def test_iter_sharded_jsonl_rejects_corrupted_shard(tmp_path):
    _build_tape(tmp_path)
    with (tmp_path / "events-001.jsonl").open("ab") as handle:
        handle.write(b'{"block_number":13,"value":"tampered"}\n')
    with pytest.raises(ValueError, match="record count|SHA"):
        list(
            iter_sharded_jsonl(
                tmp_path,
                tmp_path / "events-full.jsonl.manifest.json",
            )
        )


def test_iter_sharded_jsonl_rejects_gap(tmp_path):
    _build_tape(tmp_path)
    path = tmp_path / "events-full.jsonl.manifest.json"
    manifest = json.loads(path.read_text())
    manifest["provenance"]["shards"][1]["from_block"] = 13
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="discontinuous"):
        list(iter_sharded_jsonl(tmp_path, path))

def test_iter_sharded_jsonl_resolves_reused_gap_names_by_identity(tmp_path):
    digest = hashlib.sha256()
    shards = []
    for directory, rows, lo, hi in (
        ("prior", [{"block_number": 10, "value": "a"}], 10, 11),
        ("current", [{"block_number": 12, "value": "b"}], 12, 12),
    ):
        output_dir = tmp_path / directory
        output_dir.mkdir()
        name = "events-gap-000.jsonl"
        shard = write_jsonl_snapshot(
            rows,
            output=output_dir / name,
            provenance={
                "chain_id": 4663,
                "from_block": lo,
                "to_block": hi,
            },
        )
        for row in rows:
            digest.update(canonical_jsonl_bytes(row))
        shards.append(
            {
                "file": name,
                "sha256": shard["sha256"],
                "records": shard["records"],
                "from_block": lo,
                "to_block": hi,
            }
        )

    write_virtual_jsonl_manifest(
        manifest_path=tmp_path / "events-full.jsonl.manifest.json",
        path_name="events-full.jsonl",
        records=2,
        sha256=digest.hexdigest(),
        provenance={
            "source": "test_reused_gap_names",
            "chain_id": 4663,
            "storage_mode": "sharded_artifacts",
            "shards": shards,
        },
    )

    rows = list(
        iter_sharded_jsonl(
            tmp_path,
            tmp_path / "events-full.jsonl.manifest.json",
        )
    )
    assert [row["block_number"] for row in rows] == [10, 12]



def test_filtered_sharded_reader_decodes_only_matching_field_values(tmp_path):
    _build_tape(tmp_path)
    rows = list(
        iter_sharded_jsonl_matching_field_values(
            tmp_path,
            tmp_path / "events-full.jsonl.manifest.json",
            field="value",
            values={"b"},
        )
    )
    assert rows == [{"block_number": 11, "value": "b"}]


def test_filtered_sharded_reader_still_validates_unmatched_bytes(tmp_path):
    _build_tape(tmp_path)
    path = tmp_path / "events-000.jsonl"
    path.write_bytes(
        path.read_bytes().replace(
            b'"value":"a"',
            b'"value":"z"',
            1,
        )
    )
    with pytest.raises(ValueError, match="SHA"):
        list(
            iter_sharded_jsonl_matching_field_values(
                tmp_path,
                tmp_path / "events-full.jsonl.manifest.json",
                field="value",
                values={"b"},
            )
        )


def test_filtered_single_file_reader_validates_full_snapshot(tmp_path):
    rows = [
        {"block_number": 10, "pool": "0xaaa"},
        {"block_number": 11, "pool": "0xbbb"},
        {"block_number": 12, "pool": "0xccc"},
    ]
    path = tmp_path / "events.jsonl"
    write_jsonl_snapshot(
        rows,
        output=path,
        provenance={"chain_id": 4663},
    )
    selected = list(
        iter_validated_jsonl_matching_field_values(
            path,
            tmp_path / "events.jsonl.manifest.json",
            field="pool",
            values={"0xbbb"},
        )
    )
    assert selected == [{"block_number": 11, "pool": "0xbbb"}]

    path.write_bytes(
        path.read_bytes().replace(
            b'"pool":"0xaaa"',
            b'"pool":"0xddd"',
            1,
        )
    )
    with pytest.raises(ValueError, match="SHA"):
        list(
            iter_validated_jsonl_matching_field_values(
                path,
                tmp_path / "events.jsonl.manifest.json",
                field="pool",
                values={"0xbbb"},
            )
        )



def test_validate_shard_block_coverage_accepts_exact_unsorted_ranges():
    rows = validate_shard_block_coverage(
        [
            {"from_block": 20, "to_block": 29, "id": "b"},
            {"from_block": 10, "to_block": 19, "id": "a"},
            {"from_block": 30, "to_block": 30, "id": "c"},
        ],
        start_block=10,
        end_block=30,
    )
    assert [row["id"] for row in rows] == ["a", "b", "c"]


def test_validate_shard_block_coverage_rejects_gap():
    with pytest.raises(ValueError, match="gap"):
        validate_shard_block_coverage(
            [
                {"from_block": 10, "to_block": 19},
                {"from_block": 21, "to_block": 30},
            ],
            start_block=10,
            end_block=30,
        )


def test_validate_shard_block_coverage_rejects_overlap():
    with pytest.raises(ValueError, match="overlaps|repeats"):
        validate_shard_block_coverage(
            [
                {"from_block": 10, "to_block": 20},
                {"from_block": 20, "to_block": 30},
            ],
            start_block=10,
            end_block=30,
        )


def test_validate_shard_block_coverage_rejects_end_overshoot():
    with pytest.raises(ValueError, match="exceeds"):
        validate_shard_block_coverage(
            [{"from_block": 10, "to_block": 31}],
            start_block=10,
            end_block=30,
        )



def test_iter_validated_jsonl_streams_all_rows_and_validates_sha(tmp_path):
    from hlp.data.sharded_tape import iter_validated_jsonl
    from hlp.data.snapshot import write_jsonl_snapshot

    path = tmp_path / "all.jsonl"
    write_jsonl_snapshot(
        [{"a": 1}, {"a": 2}],
        output=path,
        provenance={"source": "unit"},
    )
    manifest = path.with_suffix(".jsonl.manifest.json")

    assert list(iter_validated_jsonl(path, manifest)) == [
        {"a": 1},
        {"a": 2},
    ]

    path.write_text('{"a":1}\n{"a":3}\n')
    with pytest.raises(ValueError, match="JSONL SHA changed"):
        list(iter_validated_jsonl(path, manifest))
