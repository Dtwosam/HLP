import hashlib
import json
from pathlib import Path

import pytest

from hlp.data.phase2_research_materialization import (
    materialize_sharded_jsonl_research_subset,
    materialize_single_jsonl_research_subset,
)
from hlp.data.sharded_tape import write_virtual_jsonl_manifest
from hlp.data.snapshot import write_jsonl_snapshot


TOKEN_A = "0x" + "11" * 20
TOKEN_B = "0x" + "22" * 20
SHA = "ab" * 32


def test_single_research_materialization_validates_full_tape_and_filters_tokens(
    tmp_path: Path,
):
    source = tmp_path / "source.jsonl"
    source_manifest = write_jsonl_snapshot(
        [
            {
                "token": TOKEN_A,
                "block_number": 1,
                "market_cap_proxy_usd": "100000",
            },
            {
                "token": TOKEN_B,
                "block_number": 2,
                "market_cap_proxy_usd": "200000",
            },
        ],
        output=source,
        provenance={"source": "unit"},
    )
    output = tmp_path / "eligible.jsonl"

    report = materialize_single_jsonl_research_subset(
        component_id="unit",
        data_path=source,
        manifest_path=source.with_suffix(
            ".jsonl.manifest.json"
        ),
        eligible_tokens=[TOKEN_B],
        expected_logical_sha256=source_manifest["sha256"],
        output=output,
        source_binding_sha256=SHA,
    )

    rows = [
        json.loads(line)
        for line in output.read_text().splitlines()
        if line.strip()
    ]
    assert [row["token"] for row in rows] == [TOKEN_B]
    assert report["logical_input_records"] == 2
    assert report["materialized_records"] == 1
    assert report["full_input_validated"] is True
    assert report["dump_threshold_frozen"] is False
    assert report["outcome_labels_computed"] is False


def test_single_materialization_does_not_publish_partial_output_on_input_sha_failure(
    tmp_path: Path,
):
    source = tmp_path / "source.jsonl"
    manifest = write_jsonl_snapshot(
        [
            {"token": TOKEN_A, "block_number": 1},
            {"token": TOKEN_B, "block_number": 2},
        ],
        output=source,
        provenance={"source": "unit"},
    )
    source.write_text(
        source.read_text().replace(
            '"block_number":2',
            '"block_number":3',
        )
    )
    output = tmp_path / "eligible.jsonl"

    with pytest.raises(ValueError, match="JSONL SHA changed"):
        materialize_single_jsonl_research_subset(
            component_id="unit",
            data_path=source,
            manifest_path=source.with_suffix(
                ".jsonl.manifest.json"
            ),
            eligible_tokens=[TOKEN_A],
            expected_logical_sha256=manifest["sha256"],
            output=output,
            source_binding_sha256=SHA,
        )

    assert not output.exists()
    assert not output.with_suffix(".jsonl.tmp").exists()


def test_sharded_research_materialization_validates_aggregate_and_filters(
    tmp_path: Path,
):
    root = tmp_path / "shards"
    root.mkdir()
    shard_a = root / "points-000.jsonl"
    shard_b = root / "points-001.jsonl"
    manifest_a = write_jsonl_snapshot(
        [{
            "token": TOKEN_A,
            "block_number": 1,
            "market_cap_proxy_usd": "100000",
        }],
        output=shard_a,
        provenance={"from_block": 1, "to_block": 1},
    )
    manifest_b = write_jsonl_snapshot(
        [{
            "token": TOKEN_B,
            "block_number": 2,
            "market_cap_proxy_usd": "200000",
        }],
        output=shard_b,
        provenance={"from_block": 2, "to_block": 2},
    )
    aggregate_sha = hashlib.sha256(
        shard_a.read_bytes() + shard_b.read_bytes()
    ).hexdigest()
    aggregate_path = tmp_path / "points.manifest.json"
    aggregate = write_virtual_jsonl_manifest(
        manifest_path=aggregate_path,
        path_name="points.jsonl",
        records=2,
        sha256=aggregate_sha,
        provenance={
            "storage_mode": "sharded_artifacts",
            "shards": [
                {
                    "file": shard_a.name,
                    "records": manifest_a["records"],
                    "sha256": manifest_a["sha256"],
                    "from_block": 1,
                    "to_block": 1,
                },
                {
                    "file": shard_b.name,
                    "records": manifest_b["records"],
                    "sha256": manifest_b["sha256"],
                    "from_block": 2,
                    "to_block": 2,
                },
            ],
        },
    )
    output = tmp_path / "eligible.jsonl"

    report = materialize_sharded_jsonl_research_subset(
        component_id="unit-sharded",
        root=root,
        aggregate_manifest_path=aggregate_path,
        eligible_tokens=[TOKEN_A],
        expected_logical_sha256=aggregate["sha256"],
        output=output,
        source_binding_sha256=SHA,
    )

    assert report["logical_input_records"] == 2
    assert report["materialized_records"] == 1
    assert json.loads(output.read_text())["token"] == TOKEN_A


def test_sharded_materialization_rejects_logical_manifest_substitution(
    tmp_path: Path,
):
    aggregate_path = tmp_path / "points.manifest.json"
    write_virtual_jsonl_manifest(
        manifest_path=aggregate_path,
        path_name="points.jsonl",
        records=1,
        sha256="cd" * 32,
        provenance={
            "storage_mode": "sharded_artifacts",
            "shards": [{
                "file": "missing.jsonl",
                "records": 1,
                "sha256": "cd" * 32,
                "from_block": 1,
                "to_block": 1,
            }],
        },
    )

    with pytest.raises(ValueError, match="logical tape SHA drift"):
        materialize_sharded_jsonl_research_subset(
            component_id="unit-sharded",
            root=tmp_path,
            aggregate_manifest_path=aggregate_path,
            eligible_tokens=[TOKEN_A],
            expected_logical_sha256="ef" * 32,
            output=tmp_path / "eligible.jsonl",
            source_binding_sha256=SHA,
        )
