import pytest

from hlp.data.phase1_evidence import (
    validate_post_eligibility_evidence_bundle,
)


def _fixtures():
    v1_sha = "1" * 64
    v2_sha = "2" * 64
    universe_sha = "3" * 64
    representative_sha = "4" * 64

    eligible_manifest = {
        "sha256": universe_sha,
        "provenance": {
            "chain_id": 4663,
            "snapshot_head_block": 54_486_035,
            "eligibility_threshold_usd": "100000",
            "v1_eligibility_run_id": 700,
            "v2_eligibility_run_id": 700,
            "v1_v3_run_id": 701,
            "v2_v4_run_id": 702,
            "v1_eligibility_sha256": v1_sha,
            "v2_eligibility_sha256": v2_sha,
        },
    }
    eligible_summary = {
        "snapshot_head_block": 54_486_035,
        "all_pons_launches": 494_639,
        "unknown_tokens": 0,
        "eligible_tokens": 12_345,
        "eligible_v1": 8_000,
        "eligible_v2": 4_345,
        "validated_v1_v3_run_id": 701,
        "validated_v2_v4_run_id": 702,
        "validated_v1_input_sha256": v1_sha,
        "validated_v2_input_sha256": v2_sha,
        "universe_sha256": universe_sha,
    }
    representative_manifest = {
        "sha256": representative_sha,
        "provenance": {
            "chain_id": 4663,
            "snapshot_head_block": 54_486_035,
            "v1_eligibility_run_id": 700,
            "v2_eligibility_run_id": 700,
            "v1_v3_run_id": 701,
            "v2_v4_run_id": 702,
            "fallback_run_id": 700,
            "v1_eligibility_sha256": v1_sha,
            "v2_eligibility_sha256": v2_sha,
        },
    }
    representative_summary = {
        "snapshot_head_block": 54_486_035,
        "tokens": 10,
        "complete_tokens": 10,
        "sample_groups": {"failure": 5, "runner": 5},
        "validation_sha256": representative_sha,
    }
    return {
        "eligible_summary": eligible_summary,
        "eligible_manifest": eligible_manifest,
        "representative_summary": representative_summary,
        "representative_manifest": representative_manifest,
        "expected_lifecycle_run_id": 700,
        "expected_v1_v3_run_id": 701,
        "expected_v2_v4_run_id": 702,
    }


def test_post_eligibility_evidence_bundle_accepts_consistent_provenance():
    report = validate_post_eligibility_evidence_bundle(**_fixtures())

    assert report == {
        "status": "ready",
        "snapshot_head_block": 54_486_035,
        "all_pons_launches": 494_639,
        "eligible_tokens": 12_345,
        "representative_tokens": 10,
        "lifecycle_run_id": 700,
        "v1_v3_run_id": 701,
        "v2_v4_run_id": 702,
        "eligible_universe_sha256": "3" * 64,
        "representative_validation_sha256": "4" * 64,
        "v1_eligibility_sha256": "1" * 64,
        "v2_eligibility_sha256": "2" * 64,
    }


def test_post_eligibility_evidence_bundle_rejects_venue_routing_drift():
    fixtures = _fixtures()
    fixtures["representative_manifest"]["provenance"]["v1_v3_run_id"] = 999

    with pytest.raises(
        ValueError,
        match="representative v1_v3_run_id does not match evidence routing",
    ):
        validate_post_eligibility_evidence_bundle(**fixtures)


def test_post_eligibility_evidence_bundle_rejects_lifecycle_hash_drift():
    fixtures = _fixtures()
    fixtures["representative_manifest"]["provenance"][
        "v2_eligibility_sha256"
    ] = "a" * 64

    with pytest.raises(
        ValueError,
        match="eligible and representative lifecycle SHA disagree",
    ):
        validate_post_eligibility_evidence_bundle(**fixtures)


def test_post_eligibility_evidence_bundle_rejects_fallback_run_drift():
    fixtures = _fixtures()
    fixtures["representative_manifest"]["provenance"]["fallback_run_id"] = 999

    with pytest.raises(
        ValueError,
        match="fallback run does not match lifecycle evidence",
    ):
        validate_post_eligibility_evidence_bundle(**fixtures)


def test_post_eligibility_evidence_bundle_rejects_incomplete_universe():
    fixtures = _fixtures()
    fixtures["eligible_summary"]["unknown_tokens"] = 1

    with pytest.raises(
        ValueError,
        match="eligible universe still contains unknown tokens",
    ):
        validate_post_eligibility_evidence_bundle(**fixtures)


def test_post_eligibility_evidence_bundle_rejects_wrong_sample_groups():
    fixtures = _fixtures()
    fixtures["representative_summary"]["sample_groups"] = {
        "failure": 4,
        "runner": 6,
    }

    with pytest.raises(ValueError, match="representative sample groups changed"):
        validate_post_eligibility_evidence_bundle(**fixtures)


def test_post_eligibility_evidence_bundle_rejects_launch_count_drift():
    fixtures = _fixtures()
    fixtures["eligible_summary"]["all_pons_launches"] = 494_638

    with pytest.raises(
        ValueError,
        match="eligible universe Pons launch count changed",
    ):
        validate_post_eligibility_evidence_bundle(**fixtures)
