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


def test_representative_market_paths_repairs_paginated_shard_downloads() -> None:
    market_paths = Path(
        ".github/workflows/phase1-pons-representative-market-paths.yml"
    ).read_text()

    assert (
        "Repair manifest-required shards omitted by artifact pagination"
        in market_paths
    )
    assert "find_github_actions_run_artifact" in market_paths
    assert "v1-v3-events-shard-" in market_paths
    assert "phase1-pons-v1-v3-" in market_paths
    assert "v4-events-gap-" in market_paths
    assert "phase1-pons-v2-v4-gap-" in market_paths


def test_representative_market_path_replay_is_artifact_only() -> None:
    replay = Path(
        ".github/workflows/"
        "phase1-pons-representative-market-path-replay-one-shot.yml"
    ).read_text()
    config = Path(
        ".github/phase1-pons-representative-market-path-replay.json"
    ).read_text()

    assert "market-path replay generation must increment by one" in replay
    assert '"sample_run_id": 35518892463' in config
    assert (
        "uses: ./.github/workflows/"
        "phase1-pons-representative-market-paths.yml"
    ) in replay
    assert "phase1-pons-representative-transfers-full.yml" not in replay
    assert "rpc-" not in replay
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in replay
    assert (
        "market-path replay frozen inputs changed at launch"
        in replay
    )


def test_representative_priced_path_replay_is_artifact_only() -> None:
    replay = Path(
        ".github/workflows/"
        "phase1-pons-representative-priced-path-replay-one-shot.yml"
    ).read_text()
    config = Path(
        ".github/phase1-pons-representative-priced-path-replay.json"
    ).read_text()

    assert '"market_path_run_id": 35522831005' in config
    assert '"fallback_run_id": 35518892463' in config
    assert (
        "uses: ./.github/workflows/"
        "phase1-pons-representative-priced-paths.yml"
    ) in replay
    assert "phase1-pons-representative-transfers-full.yml" not in replay
    assert "rpc-" not in replay
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in replay
    assert "priced-path replay generation must increment by one" in replay
    assert "priced-path replay frozen inputs changed at launch" in replay


def test_representative_dex_replay_is_bounded() -> None:
    replay = Path(
        ".github/workflows/"
        "phase1-pons-representative-dex-replay-one-shot.yml"
    ).read_text()
    config = Path(
        ".github/phase1-pons-representative-dex-replay.json"
    ).read_text()

    assert '"sample_run_id": 35518892463' in config
    assert '"priced_path_run_id": 35523404472' in config
    assert '"quote_audit_run_id": 33923299711' in config
    assert "quote_audit_run_id" in replay
    assert "phase1-pons-full-quote-audit-current" in replay
    assert (
        "uses: ./.github/workflows/"
        "phase1-pons-representative-dex-crosscheck.yml"
    ) in replay
    assert "phase1-pons-representative-transfers-full.yml" not in replay
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in replay
    assert "DEX replay generation must increment by one" in replay
    assert "DEX replay frozen inputs changed at launch" in replay


def test_representative_dex_crosscheck_uses_execution_quote_evidence() -> None:
    workflow = Path(
        ".github/workflows/"
        "phase1-pons-representative-dex-crosscheck.yml"
    ).read_text()

    assert "swap_execution_quote_per_token" in workflow
    assert 'currency="token"' in workflow
    assert '"canonical_price_semantics"' in workflow
    assert '"swap_execution_quote_per_token"' in workflow
    assert '"historical_price_result_semantics"' in workflow
    assert '"diagnostic_noncanonical"' in workflow
    assert "phase1-pons-full-quote-audit-current" in workflow
    assert '"quote_audit_run_id"' in workflow
    assert "representative_dex_price_disagreements" in workflow
    assert '"independent_candle_low_quote_per_token"' in workflow
    assert '"independent_candle_high_quote_per_token"' in workflow
    assert '"price_disagreements"' in workflow
    assert (
        "independent DEX historical price evidence is absent for "
        in workflow
    )
    assert (
        "independent DEX swap-price reconciliation failed for "
        not in workflow
    )


def test_representative_dex_quote_diagnostic_is_bounded() -> None:
    workflow = Path(
        ".github/workflows/"
        "phase1-pons-representative-dex-quote-diagnostic-one-shot.yml"
    ).read_text()
    config = Path(
        ".github/phase1-pons-representative-dex-quote-diagnostic.json"
    ).read_text()

    assert "DEX quote diagnostic generation must increment by one" in workflow
    assert '"priced_path_run_id": 35523404472' in config
    assert '"failure_replay_run_id": 35527327945' in config
    assert 'currency="token"' in workflow
    assert '"tolerance_bps": "0"' in workflow
    assert "len(specs) * client.attempts" in workflow
    assert "phase1-pons-representative-transfers-full.yml" not in workflow
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in workflow
    assert (
        "DEX quote diagnostic generation must increment by one"
        in workflow
    )


def test_representative_dex_execution_diagnostic_is_artifact_only() -> None:
    workflow = Path(
        ".github/workflows/"
        "phase1-pons-representative-dex-execution-diagnostic-one-shot.yml"
    ).read_text()
    config = Path(
        ".github/phase1-pons-representative-dex-execution-diagnostic.json"
    ).read_text()

    assert '"market_path_run_id": 35522831005' in config
    assert '"priced_path_run_id": 35523404472' in config
    assert '"quote_diagnostic_run_id": 35528655862' in config
    assert "execution_quote_per_token" in workflow
    assert "post_swap_spot_quote_per_token" in workflow
    assert '"external_requests": 0' in workflow
    assert "GeckoTerminalClient" not in workflow
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in workflow
    assert "phase1-pons-representative-transfers-full.yml" not in workflow
    assert (
        "DEX execution diagnostic generation must increment by one"
        in workflow
    )


def test_representative_dex_minute_diagnostic_is_bounded() -> None:
    workflow = Path(
        ".github/workflows/"
        "phase1-pons-representative-dex-minute-diagnostic-one-shot.yml"
    ).read_text()
    config = Path(
        ".github/phase1-pons-representative-dex-minute-diagnostic.json"
    ).read_text()

    assert '"execution_diagnostic_run_id": 35529024864' in config
    assert 'timeframe="minute"' in workflow
    assert 'currency="token"' in workflow
    assert "len(rows) * client.attempts" in workflow
    assert '"tolerance_bps": "0"' in workflow
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in workflow
    assert "phase1-pons-representative-transfers-full.yml" not in workflow
    assert (
        "DEX minute diagnostic generation must increment by one"
        in workflow
    )
