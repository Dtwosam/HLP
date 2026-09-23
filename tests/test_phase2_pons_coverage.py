import hashlib
import json
from pathlib import Path

import pytest

from hlp.data.phase2_pons_coverage import (
    PONS_SOURCE_COVERAGE_VERSION,
    validate_pons_lifecycle_artifact,
    validate_pons_source_coverage_descriptor,
)


TOKEN1 = "0x" + "11" * 20
TOKEN2 = "0x" + "22" * 20


def lifecycle_row(token, *, eligible):
    return {
        "token": token,
        "launch_block": 10,
        "eligibility_status": "eligible" if eligible else "ineligible",
        "pricing_complete": True,
        "price_points": 2,
        "priced_points": 2,
        "unpriced_points": 0,
        "last_priced_block": 99,
    }


def source_spec(sha):
    return {
        "source_id": "pons_v1",
        "artifact_run_id": 1,
        "artifact_id": 2,
        "artifact_name": "artifact",
        "artifact_digest": "sha256:" + "ab" * 32,
        "lifecycle_filename": "lifecycle.jsonl",
        "manifest_filename": "lifecycle.jsonl.manifest.json",
        "lifecycle_sha256": sha,
        "records": 2,
        "eligible_tokens": 1,
        "required_start_block": 10,
        "price_points": 4,
    }


def test_descriptor_requires_exact_v1_v2_source_set():
    base = source_spec("cd" * 32)
    v2 = {**base, "source_id": "pons_v2"}
    result = validate_pons_source_coverage_descriptor(
        {
            "version": PONS_SOURCE_COVERAGE_VERSION,
            "snapshot_head_block": 100,
            "sources": [base, v2],
        }
    )
    assert [row["source_id"] for row in result["sources"]] == [
        "pons_v1",
        "pons_v2",
    ]


def test_lifecycle_artifact_requires_full_pricing(tmp_path):
    payload = (
        json.dumps(lifecycle_row(TOKEN1, eligible=True))
        + "\n"
        + json.dumps(lifecycle_row(TOKEN2, eligible=False))
        + "\n"
    ).encode()
    sha = hashlib.sha256(payload).hexdigest()
    spec = source_spec(sha)

    (tmp_path / "lifecycle.jsonl").write_bytes(payload)
    (tmp_path / "lifecycle.jsonl.manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "records": 2,
                "sha256": sha,
                "provenance": {
                    "chain_id": 4663,
                    "snapshot_head_block": 100,
                    "eligibility_threshold_usd": "100000",
                },
            }
        )
    )
    report = validate_pons_lifecycle_artifact(
        source=spec,
        snapshot_head_block=100,
        directory=tmp_path,
    )
    assert report["coverage_status"] == "complete"
    assert report["price_points"] == 4
    assert report["unknown_tokens"] == 0


def test_lifecycle_artifact_rejects_unknown_or_unpriced(tmp_path):
    rows = [
        lifecycle_row(TOKEN1, eligible=True),
        {
            **lifecycle_row(TOKEN2, eligible=False),
            "eligibility_status": "unknown",
            "pricing_complete": False,
            "priced_points": 1,
            "unpriced_points": 1,
        },
    ]
    payload = ("\n".join(json.dumps(row) for row in rows) + "\n").encode()
    sha = hashlib.sha256(payload).hexdigest()
    spec = source_spec(sha)

    (tmp_path / "lifecycle.jsonl").write_bytes(payload)
    (tmp_path / "lifecycle.jsonl.manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "records": 2,
                "sha256": sha,
                "provenance": {
                    "chain_id": 4663,
                    "snapshot_head_block": 100,
                    "eligibility_threshold_usd": "100000",
                },
            }
        )
    )
    with pytest.raises(ValueError, match="not fully priced"):
        validate_pons_lifecycle_artifact(
            source=spec,
            snapshot_head_block=100,
            directory=tmp_path,
        )



def test_repository_pons_source_coverage_descriptor_is_frozen():
    descriptor = validate_pons_source_coverage_descriptor(
        json.loads(
            Path(".github/phase2-pons-source-coverage.json").read_text()
        )
    )
    assert descriptor["snapshot_head_block"] == 54_486_035
    rows = {row["source_id"]: row for row in descriptor["sources"]}

    v1 = rows["pons_v1"]
    assert v1["artifact_run_id"] == 35_518_892_463
    assert v1["artifact_id"] == 10_607_208_490
    assert v1["records"] == 268_688
    assert v1["eligible_tokens"] == 5_161
    assert v1["required_start_block"] == 8_621_658
    assert v1["price_points"] == 63_560_072
    assert v1["lifecycle_sha256"] == (
        "74a43a5401d88d299070b21414e7d2ef"
        "aaa90c8469596d2207ef41a9456ede31"
    )

    v2 = rows["pons_v2"]
    assert v2["artifact_run_id"] == 35_518_892_463
    assert v2["artifact_id"] == 10_607_362_928
    assert v2["records"] == 225_951
    assert v2["eligible_tokens"] == 1_811
    assert v2["required_start_block"] == 27_027_321
    assert v2["price_points"] == 24_319_652
    assert v2["lifecycle_sha256"] == (
        "2e880af79350530d4c30cda8d10778f"
        "ee8156c284ccb523cae226f1a886cc566"
    )
