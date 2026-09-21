import hashlib
import json

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
