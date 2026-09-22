import io
import json
import zipfile
from pathlib import Path

import pytest

from hlp.data.phase2_pons_research_artifacts import (
    discover_artifact_by_manifest,
    materialize_bound_shards,
)


SHA = "ab" * 32


def zip_bytes(files):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
    return out.getvalue()


def test_discover_artifact_by_exact_manifest_identity():
    target_manifest = {
        "records": 2,
        "sha256": SHA,
    }
    artifacts = [
        {
            "id": 1,
            "name": "wrong",
            "digest": "sha256:" + "cd" * 32,
            "expired": False,
        },
        {
            "id": 2,
            "name": "target",
            "digest": "sha256:" + "ef" * 32,
            "expired": False,
        },
    ]
    blobs = {
        1: zip_bytes({
            "pons-quote-registry.jsonl.manifest.json": json.dumps({
                "records": 1,
                "sha256": "cd" * 32,
            }),
        }),
        2: zip_bytes({
            "nested/pons-quote-registry.jsonl.manifest.json": json.dumps(
                target_manifest
            ),
        }),
    }

    found = discover_artifact_by_manifest(
        artifacts,
        lambda row: blobs[row["id"]],
        manifest_filename="pons-quote-registry.jsonl.manifest.json",
        expected_sha256=SHA,
        expected_records=2,
        label="quote",
    )

    assert found["id"] == 2
    assert found["name"] == "target"


def test_materialize_bound_shards_validates_data_sidecar_and_range(tmp_path):
    filename = "events-000.jsonl"
    data = b'{"a":1}\n'
    import hashlib
    sha = hashlib.sha256(data).hexdigest()
    manifest = {
        "path": filename,
        "records": 1,
        "sha256": sha,
        "provenance": {
            "from_block": 1,
            "to_block": 2,
        },
    }
    artifact = {
        "id": 10,
        "name": "shard-000",
        "digest": "sha256:" + SHA,
        "expired": False,
    }
    blob = zip_bytes({
        filename: data,
        filename + ".manifest.json": json.dumps(manifest),
    })
    binding = {
        "run_id": 7,
        "artifact_name": "shard-000",
        "file": filename,
        "records": 1,
        "sha256": sha,
        "from_block": 1,
        "to_block": 2,
    }

    report = materialize_bound_shards(
        [binding],
        artifacts_for_run=lambda run_id: [artifact],
        artifact_zip=lambda row: blob,
        destination=tmp_path,
        label="unit",
    )

    assert report["materialized_shards"] == 1
    assert (tmp_path / "7" / filename).read_bytes() == data
    assert report["shards"][0]["artifact_digest"] == "sha256:" + SHA


def test_materialize_bound_shards_rejects_changed_bytes(tmp_path):
    filename = "events-000.jsonl"
    expected = b'{"a":1}\n'
    actual = b'{"a":2}\n'
    import hashlib
    sha = hashlib.sha256(expected).hexdigest()
    manifest = {
        "path": filename,
        "records": 1,
        "sha256": sha,
        "provenance": {"from_block": 1, "to_block": 1},
    }
    artifact = {
        "id": 10,
        "name": "shard-000",
        "digest": "sha256:" + SHA,
        "expired": False,
    }
    blob = zip_bytes({
        filename: actual,
        filename + ".manifest.json": json.dumps(manifest),
    })

    with pytest.raises(ValueError, match="data SHA changed"):
        materialize_bound_shards(
            [{
                "run_id": 7,
                "artifact_name": "shard-000",
                "file": filename,
                "records": 1,
                "sha256": sha,
                "from_block": 1,
                "to_block": 1,
            }],
            artifacts_for_run=lambda run_id: [artifact],
            artifact_zip=lambda row: blob,
            destination=tmp_path,
            label="unit",
        )
