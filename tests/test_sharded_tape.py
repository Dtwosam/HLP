import hashlib
import json

import pytest

from hlp.data.sharded_tape import (
    canonical_jsonl_bytes,
    iter_sharded_jsonl,
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
