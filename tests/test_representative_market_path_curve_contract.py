from pathlib import Path

from hlp.data.pons_representative_paths import (
    resolve_representative_v2_curve_registry_sha256,
)


CANONICAL_V2_CURVE_RUN_ID = "33936232604"
CANONICAL_V2_REGISTRY_SHA256 = (
    "06dc7d373f79dd43aa3bb4070187b5a8"
    "ee426f0690f3f4f7f8d5cfce3cd3d48f"
)
CANONICAL_V2_CURVE_TAPE_SHA256 = (
    "771c9147ef1a84bd673532842972e16e0"
    "ee12cae1513a41b402f53b5c444c50b"
)
LEGACY_V2_CURVE_SOURCE = "stream_merged_pons_specific_curve_shards"
CANONICAL_V2_CURVE_SOURCE = "manifest_gap_aware_curve_recovery"


def _canonical_recovered_curve_manifest() -> dict:
    return {
        "records": 9_231_724,
        "sha256": CANONICAL_V2_CURVE_TAPE_SHA256,
        "provenance": {
            "source": CANONICAL_V2_CURVE_SOURCE,
            "preserved_run_id": 33_912_593_934,
            "partial_recovery_run_id": 33_925_648_297,
            "prior_gap_run_id": 33_935_705_953,
        },
    }


def test_representative_market_paths_accept_canonical_v2_curve_recovery_provenance() -> None:
    representative = Path(
        ".github/workflows/phase1-pons-representative-evidence-chain.yml"
    ).read_text()
    market_paths = Path(
        ".github/workflows/phase1-pons-representative-market-paths.yml"
    ).read_text()

    assert f'"run_id": {int(CANONICAL_V2_CURVE_RUN_ID):_}' in representative
    assert LEGACY_V2_CURVE_SOURCE in market_paths
    assert CANONICAL_V2_CURVE_SOURCE in market_paths


def test_exact_legacy_recovery_resolves_canonical_registry_identity() -> None:
    observed = resolve_representative_v2_curve_registry_sha256(
        _canonical_recovered_curve_manifest(),
        curve_run_id=int(CANONICAL_V2_CURVE_RUN_ID),
    )
    assert observed == CANONICAL_V2_REGISTRY_SHA256


def test_legacy_recovery_fails_closed_when_tape_identity_changes() -> None:
    manifest = _canonical_recovered_curve_manifest()
    manifest["sha256"] = "00" * 32

    observed = resolve_representative_v2_curve_registry_sha256(
        manifest,
        curve_run_id=int(CANONICAL_V2_CURVE_RUN_ID),
    )
    assert observed is None


def test_legacy_recovery_fails_closed_when_lineage_changes() -> None:
    manifest = _canonical_recovered_curve_manifest()
    manifest["provenance"]["prior_gap_run_id"] += 1

    observed = resolve_representative_v2_curve_registry_sha256(
        manifest,
        curve_run_id=int(CANONICAL_V2_CURVE_RUN_ID),
    )
    assert observed is None


def test_direct_registry_identity_remains_authoritative() -> None:
    manifest = {
        "provenance": {
            "registry_sha256": CANONICAL_V2_REGISTRY_SHA256,
        }
    }
    observed = resolve_representative_v2_curve_registry_sha256(
        manifest,
        curve_run_id=1,
    )
    assert observed == CANONICAL_V2_REGISTRY_SHA256


def test_future_curve_recovery_persists_registry_identity() -> None:
    recovery = Path(
        ".github/workflows/phase1-pons-v2-curve-recover-gaps.yml"
    ).read_text()

    assert "name: phase1-pons-v2-full-registry" in recovery
    assert '"v2_registry_run_id": int(' in recovery
    assert '"registry_sha256": registry_sha256' in recovery



def test_representative_market_paths_filter_full_tapes_fail_closed() -> None:
    market_paths = Path(
        ".github/workflows/phase1-pons-representative-market-paths.yml"
    ).read_text()

    assert "iter_sharded_jsonl_matching_field_values" in market_paths
    assert "iter_validated_jsonl_matching_field_values" in market_paths
    assert 'field="pool"' in market_paths
    assert 'field="curve"' in market_paths
    assert 'field="pool_id"' in market_paths


def test_representative_v2_v4_downloads_nested_legacy_source() -> None:
    market_paths = Path(
        ".github/workflows/phase1-pons-representative-market-paths.yml"
    ).read_text()

    assert "numeric_shard_sources" in market_paths
    assert "legacy_gap_run_id=" in market_paths
    assert "path: v2v4-shards/legacy" in market_paths
    assert "steps.v2v4_sources.outputs.legacy_gap_run_id" in market_paths
