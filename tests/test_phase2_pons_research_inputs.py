import pytest

from hlp.data.phase2_pons_research_inputs import (
    PHASE2_PONS_RESEARCH_INPUTS_VERSION,
    V1_REQUIRED_MANIFESTS,
    V2_REQUIRED_MANIFESTS,
    resolve_accepted_pons_replay_inputs,
)


SHA = "ab" * 32


def validation(required):
    return {
        "chain_id": 4663,
        "snapshot_head_block": 100,
        "validated_manifests": [
            {
                "manifest": f"root/{filename}",
                "records": index + 1,
                "sha256": SHA,
            }
            for index, filename in enumerate(required.values())
        ],
        "validated_manifest_count": len(required),
    }


def test_v1_replay_inputs_come_from_accepted_lifecycle_provenance():
    lifecycle = {
        "sha256": SHA,
        "provenance": {
            "chain_id": 4663,
            "snapshot_head_block": 100,
            "source_registry_run_id": 11,
            "v1_v3_run_id": 12,
            "quote_audit_run_id": 13,
            "anchor_run_id": 14,
            "oracle_run_id": 15,
        },
    }

    resolved = resolve_accepted_pons_replay_inputs(
        "pons_v1",
        lifecycle,
        validation(V1_REQUIRED_MANIFESTS),
        snapshot_head_block=100,
    )

    assert resolved["version"] == PHASE2_PONS_RESEARCH_INPUTS_VERSION
    assert resolved["runs"]["market_events"] == 12
    assert resolved["artifacts"]["market_events"]["artifact_name"] == (
        "phase1-pons-v1-v3-full"
    )
    assert resolved["artifacts"]["quote_registry"]["artifact_name"] is None
    assert resolved["artifacts"]["quote_registry"][
        "discover_by_manifest"
    ]["sha256"] == SHA
    assert resolved["canonical_replay_required"] is True
    assert resolved["dump_threshold_frozen"] is False


def test_v2_replay_inputs_bind_all_seven_accepted_upstream_runs():
    lifecycle = {
        "sha256": SHA,
        "provenance": {
            "chain_id": 4663,
            "snapshot_head_block": 100,
            "v2_registry_run_id": 21,
            "curve_run_id": 22,
            "transition_run_id": 23,
            "v4_run_id": 24,
            "anchor_run_id": 25,
            "oracle_run_id": 26,
            "fallback_run_id": 27,
        },
    }

    resolved = resolve_accepted_pons_replay_inputs(
        "pons_v2",
        lifecycle,
        validation(V2_REQUIRED_MANIFESTS),
        snapshot_head_block=100,
    )

    assert set(resolved["runs"]) == {
        "registry",
        "curve",
        "transition",
        "market_events",
        "anchor",
        "oracle",
        "fallback",
    }
    assert resolved["artifacts"]["curve"]["artifact_name"] == (
        "phase1-pons-v2-curve-full"
    )
    assert len(resolved["validated_manifests"]) == len(
        V2_REQUIRED_MANIFESTS
    )


def test_pons_replay_inputs_reject_manifest_set_or_snapshot_drift():
    lifecycle = {
        "sha256": SHA,
        "provenance": {
            "chain_id": 4663,
            "snapshot_head_block": 100,
            "source_registry_run_id": 11,
            "v1_v3_run_id": 12,
            "quote_audit_run_id": 13,
            "anchor_run_id": 14,
            "oracle_run_id": 15,
        },
    }
    report = validation(V1_REQUIRED_MANIFESTS)
    report["validated_manifests"].pop()

    with pytest.raises(ValueError, match="manifest set changed"):
        resolve_accepted_pons_replay_inputs(
            "pons_v1",
            lifecycle,
            report,
            snapshot_head_block=100,
        )

    with pytest.raises(ValueError, match="snapshot changed"):
        resolve_accepted_pons_replay_inputs(
            "pons_v1",
            lifecycle,
            validation(V1_REQUIRED_MANIFESTS),
            snapshot_head_block=101,
        )
