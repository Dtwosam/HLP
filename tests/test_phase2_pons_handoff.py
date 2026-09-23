import json
from pathlib import Path

import pytest

from hlp.data.phase2_pons_handoff import (
    PONS_HANDOFF_VERSION,
    validate_pons_eligible_rows,
    validate_pons_handoff_artifact,
    validate_pons_handoff_descriptor,
)


TOKEN1 = "0x" + "11" * 20
TOKEN2 = "0x" + "22" * 20


def row(token, version, maximum="150000"):
    return {
        "token": token,
        "version": version,
        "crossed_100k": True,
        "eligibility_status": "eligible",
        "pricing_complete": True,
        "price_points": 2,
        "priced_points": 2,
        "unpriced_points": 0,
        "max_market_cap_proxy_usd": maximum,
        "launch_block": 10,
        "max_market_cap_block": 20,
    }


def descriptor(universe_sha):
    return {
        "version": PONS_HANDOFF_VERSION,
        "evidence_run_id": 1,
        "artifact_id": 2,
        "artifact_name": "phase1-pons-eligible-universe",
        "artifact_digest": "sha256:" + "ab" * 32,
        "accepted_finalizer_run_id": 3,
        "snapshot_head_block": 100,
        "universe_filename": "universe.jsonl",
        "manifest_filename": "universe.manifest.json",
        "summary_filename": "summary.json",
        "universe_sha256": universe_sha,
        "eligible_tokens": 2,
        "eligible_v1": 1,
        "eligible_v2": 1,
        "all_pons_launches": 10,
        "unknown_tokens": 0,
    }


def test_eligible_rows_preserve_phase1_threshold_contract():
    report = validate_pons_eligible_rows(
        [row(TOKEN1, "v1"), row(TOKEN2, "v2")],
        expected_records=2,
        expected_v1=1,
        expected_v2=1,
    )
    assert report["records"] == 2
    assert report["all_rows_complete"] is True


def test_eligible_rows_fail_if_maximum_drops_below_threshold():
    with pytest.raises(ValueError, match="below threshold"):
        validate_pons_eligible_rows(
            [row(TOKEN1, "v1", maximum="99999")],
            expected_records=1,
            expected_v1=1,
            expected_v2=0,
        )


def test_handoff_artifact_validates_raw_jsonl_hash_and_provenance():
    payload = (
        json.dumps(row(TOKEN1, "v1"), separators=(",", ":"))
        + "\n"
        + json.dumps(row(TOKEN2, "v2"), separators=(",", ":"))
        + "\n"
    ).encode()
    import hashlib

    sha = hashlib.sha256(payload).hexdigest()
    spec = descriptor(sha)
    manifest = {
        "schema_version": 1,
        "records": 2,
        "sha256": sha,
        "provenance": {
            "chain_id": 4663,
            "snapshot_head_block": 100,
            "eligibility_threshold_usd": "100000",
            "source": "complete_v1_plus_v2_lifecycle_eligibility",
        },
    }
    summary = {
        "eligible_tokens": 2,
        "eligible_v1": 1,
        "eligible_v2": 1,
        "unknown_tokens": 0,
        "snapshot_head_block": 100,
        "universe_sha256": sha,
    }

    report = validate_pons_handoff_artifact(
        descriptor=spec,
        manifest=manifest,
        summary=summary,
        universe_bytes=payload,
    )
    assert report["phase2_primary_population_handoff_valid"] is True
    assert report["unique_tokens"] == 2


def test_handoff_descriptor_rejects_version_count_drift():
    spec = descriptor("cd" * 32)
    spec["eligible_v2"] = 2
    with pytest.raises(ValueError, match="do not sum"):
        validate_pons_handoff_descriptor(spec)



def test_repository_pons_handoff_descriptor_is_frozen():
    spec = validate_pons_handoff_descriptor(
        json.loads(
            Path(".github/phase2-pons-eligible-handoff.json").read_text()
        )
    )

    assert spec["evidence_run_id"] == 35_576_917_452
    assert spec["artifact_id"] == 10_628_353_314
    assert spec["accepted_finalizer_run_id"] == 35_601_191_874
    assert spec["snapshot_head_block"] == 54_486_035
    assert spec["eligible_tokens"] == 6_972
    assert spec["eligible_v1"] == 5_161
    assert spec["eligible_v2"] == 1_811
    assert spec["unknown_tokens"] == 0
    assert spec["universe_sha256"] == (
        "d5eb4ff0551eb2a0e12834b4d823dec4"
        "299d59b88eb73cefc4aa33ad2d8b2e8d"
    )
