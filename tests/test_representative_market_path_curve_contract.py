from pathlib import Path


CANONICAL_V2_CURVE_RUN_ID = "33936232604"
LEGACY_V2_CURVE_SOURCE = "stream_merged_pons_specific_curve_shards"
CANONICAL_V2_CURVE_SOURCE = "manifest_gap_aware_curve_recovery"


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
