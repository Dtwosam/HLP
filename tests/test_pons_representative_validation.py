import pytest

from hlp.data.pons_representative_validation import (
    build_representative_validation_rows,
    summarize_representative_validation,
)


def _token(index: int) -> str:
    return "0x" + f"{index:040x}"


def _fixtures():
    sample = []
    v1 = []
    v2 = []
    holders = []
    dex = []
    explorer = []
    market_paths = []
    priced_paths = []

    for index in range(1, 11):
        token = _token(index)
        version = "v1" if index <= 5 else "v2"
        group = "runner" if index % 2 else "failure"
        status = "eligible" if group == "runner" else "ineligible"
        launch_block = 1_000 + index
        sample.append(
            {
                "token": token,
                "pons_version": version,
                "sample_group": group,
                "launch_block": launch_block,
                "eligibility_status": status,
            }
        )
        lifecycle = {
            "token": token,
            "launch_block": launch_block,
            "eligibility_status": status,
            "pricing_complete": group == "failure",
            "price_points": 12 if group == "runner" else 10,
            "priced_points": 10,
            "unpriced_points": 2 if group == "runner" else 0,
            "max_market_cap_proxy_usd": (
                "250000" if group == "runner" else "90000"
            ),
        }
        (v1 if version == "v1" else v2).append(lifecycle)
        holders.append(
            {
                "token": token,
                "last_block_number": 2_000 + index,
                "transfers": 25 + index,
                "holder_count": 7 + index,
                "accounted_supply_raw": 1_000_000,
            }
        )
        registered_v4 = version == "v2"
        stage_counts = (
            {"launch": 1, "v1_v3": 7}
            if version == "v1"
            else {
                "launch": 1,
                "v2_curve": 8,
                "v2_graduation": 1,
                "v2_registration": 1,
                "v2_v4": 4,
            }
        )
        market_paths.append(
            {
                "token": token,
                "pons_version": version,
                "sample_group": group,
                "launch_block": launch_block,
                "path_rows": sum(stage_counts.values()),
                "stage_counts": stage_counts,
                "first_path_block": launch_block,
                "last_path_block": 1_500 + index,
                "graduated": registered_v4,
                "registered_v4": registered_v4,
                "has_v4_market_events": registered_v4,
            }
        )
        priced_paths.append(
            {
                "token": token,
                "pons_version": version,
                "sample_group": group,
                "launch_block": launch_block,
                "price_points": lifecycle["price_points"],
                "priced_points": lifecycle["priced_points"],
                "unpriced_points": lifecycle["unpriced_points"],
                "pricing_complete": lifecycle["pricing_complete"],
                "max_market_cap_proxy_usd": (
                    lifecycle["max_market_cap_proxy_usd"]
                ),
                "max_market_cap_block": 1_400 + index,
                "max_market_cap_phase": (
                    "v1_v3" if version == "v1" else "v2_curve"
                ),
            }
        )
        explorer.append(
            {
                "token": token,
                "pons_version": version,
                "sample_group": group,
                "launch_block": launch_block,
                "verified_launch_transactions": 1,
                "verified_dex_swap_transactions": 3,
                "checkpoint_role_counts": {
                    "first": 1,
                    "max": 1,
                    "last": 1,
                },
                "verified_transactions": 4,
                "all_transactions_matched": True,
            }
        )
        dex.append(
            {
                "token": token,
                "pons_version": version,
                "crosscheck_scope": "canonical_dex_pool",
                "external_status": "matched",
                "external_match": True,
                "mismatches": [],
                "price_crosscheck_scope": "canonical_dex_swap",
                "price_match": True,
                "price_crosscheck_status": "matched",
                "price_checkpoints": [
                    {
                        "checkpoint_roles": ["first"],
                        "price_match": True,
                        "price_crosscheck_status": "matched",
                    },
                    {
                        "checkpoint_roles": ["max"],
                        "price_match": True,
                        "price_crosscheck_status": "matched",
                    },
                    {
                        "checkpoint_roles": ["last"],
                        "price_match": True,
                        "price_crosscheck_status": "matched",
                    },
                ],
            }
        )

    return (
        sample,
        v1,
        v2,
        holders,
        dex,
        explorer,
        market_paths,
        priced_paths,
    )


def _build(fixtures):
    (
        sample,
        v1,
        v2,
        holders,
        dex,
        explorer,
        market_paths,
        priced_paths,
    ) = fixtures
    return build_representative_validation_rows(
        sample,
        v1_lifecycle_rows=v1,
        v2_lifecycle_rows=v2,
        holder_summary_rows=holders,
        dex_crosscheck_rows=dex,
        explorer_summary_rows=explorer,
        market_path_summary_rows=market_paths,
        priced_path_summary_rows=priced_paths,
    )


def test_representative_validation_joins_all_phase1_evidence():
    fixtures = _fixtures()
    rows = _build(fixtures)
    summary = summarize_representative_validation(rows)

    assert len(rows) == 10
    assert all(row["validation_status"] == "complete" for row in rows)
    assert summary["tokens"] == 10
    assert summary["sample_groups"] == {"failure": 5, "runner": 5}
    assert summary["pons_versions"] == {"v1": 5, "v2": 5}
    assert summary["priced_points"] == 100
    assert summary["detailed_price_points"] == 110
    assert summary["detailed_priced_points"] == 100
    assert summary["detailed_unpriced_points"] == 10
    assert summary["detailed_price_path_complete_tokens"] == 5
    assert summary["market_path_rows"] == 115
    assert summary["market_path_registered_v4"] == 5
    assert summary["market_path_with_v4_events"] == 5
    assert summary["transfers"] == sum(25 + index for index in range(1, 11))
    assert summary["dex_targeted"] == 10
    assert summary["dex_matched"] == 10
    assert summary["dex_price_targeted"] == 10
    assert summary["dex_price_matched"] == 10
    assert summary["dex_price_checkpoints_targeted"] == 30
    assert summary["dex_price_checkpoints_matched"] == 30
    assert summary["dex_price_multi_checkpoint_tokens"] == 10
    assert summary["dex_price_no_swap_checkpoint"] == 0
    assert summary["explorer_verified_transactions"] == 40
    assert summary["explorer_verified_launch_transactions"] == 10
    assert summary["explorer_verified_dex_swap_transactions"] == 30


def test_representative_validation_fails_closed_on_missing_holder():
    sample, v1, v2, holders, dex, explorer, market_paths, priced_paths = _fixtures()

    with pytest.raises(ValueError, match="holder summary coverage"):
        build_representative_validation_rows(
            sample,
            v1_lifecycle_rows=v1,
            v2_lifecycle_rows=v2,
            holder_summary_rows=holders[:-1],
            dex_crosscheck_rows=dex,
            explorer_summary_rows=explorer,
            market_path_summary_rows=market_paths,
            priced_path_summary_rows=priced_paths,
        )


def test_representative_validation_fails_closed_on_missing_explorer():
    sample, v1, v2, holders, dex, explorer, market_paths, priced_paths = (
        _fixtures()
    )

    with pytest.raises(ValueError, match="explorer summary coverage"):
        build_representative_validation_rows(
            sample,
            v1_lifecycle_rows=v1,
            v2_lifecycle_rows=v2,
            holder_summary_rows=holders,
            dex_crosscheck_rows=dex,
            explorer_summary_rows=explorer[:-1],
            market_path_summary_rows=market_paths,
            priced_path_summary_rows=priced_paths,
        )


def test_representative_validation_rejects_explorer_dex_count_drift():
    sample, v1, v2, holders, dex, explorer, market_paths, priced_paths = (
        _fixtures()
    )
    explorer[0]["verified_dex_swap_transactions"] = 2
    explorer[0]["verified_transactions"] = 3

    with pytest.raises(ValueError, match="explorer/DEX checkpoint count mismatch"):
        build_representative_validation_rows(
            sample,
            v1_lifecycle_rows=v1,
            v2_lifecycle_rows=v2,
            holder_summary_rows=holders,
            dex_crosscheck_rows=dex,
            explorer_summary_rows=explorer,
            market_path_summary_rows=market_paths,
            priced_path_summary_rows=priced_paths,
        )


def test_representative_validation_fails_closed_on_missing_market_path():
    sample, v1, v2, holders, dex, explorer, market_paths, priced_paths = _fixtures()

    with pytest.raises(ValueError, match="market-path summary coverage"):
        build_representative_validation_rows(
            sample,
            v1_lifecycle_rows=v1,
            v2_lifecycle_rows=v2,
            holder_summary_rows=holders,
            dex_crosscheck_rows=dex,
            market_path_summary_rows=market_paths[:-1],
            priced_path_summary_rows=priced_paths,
        )


def test_representative_validation_fails_closed_on_missing_priced_path():
    sample, v1, v2, holders, dex, explorer, market_paths, priced_paths = _fixtures()

    with pytest.raises(ValueError, match="priced-path summary coverage"):
        build_representative_validation_rows(
            sample,
            v1_lifecycle_rows=v1,
            v2_lifecycle_rows=v2,
            holder_summary_rows=holders,
            dex_crosscheck_rows=dex,
            explorer_summary_rows=explorer,
            market_path_summary_rows=market_paths,
            priced_path_summary_rows=priced_paths[:-1],
        )


def test_representative_validation_rejects_detailed_price_count_drift():
    sample, v1, v2, holders, dex, explorer, market_paths, priced_paths = _fixtures()
    priced_paths[0]["priced_points"] -= 1
    priced_paths[0]["unpriced_points"] += 1

    with pytest.raises(ValueError, match="detailed price-point accounting mismatch"):
        build_representative_validation_rows(
            sample,
            v1_lifecycle_rows=v1,
            v2_lifecycle_rows=v2,
            holder_summary_rows=holders,
            dex_crosscheck_rows=dex,
            explorer_summary_rows=explorer,
            market_path_summary_rows=market_paths,
            priced_path_summary_rows=priced_paths,
        )


def test_representative_validation_requires_priced_market_evidence():
    sample, v1, v2, holders, dex, explorer, market_paths, priced_paths = _fixtures()
    v1[0]["price_points"] = 2
    v1[0]["priced_points"] = 0
    v1[0]["max_market_cap_proxy_usd"] = None

    with pytest.raises(ValueError, match="no priced lifecycle evidence"):
        build_representative_validation_rows(
            sample,
            v1_lifecycle_rows=v1,
            v2_lifecycle_rows=v2,
            holder_summary_rows=holders,
            dex_crosscheck_rows=dex,
            explorer_summary_rows=explorer,
            market_path_summary_rows=market_paths,
            priced_path_summary_rows=priced_paths,
        )


def test_representative_validation_rejects_external_pool_mismatch():
    sample, v1, v2, holders, dex, explorer, market_paths, priced_paths = _fixtures()
    dex[0]["external_status"] = "mismatch"
    dex[0]["external_match"] = False
    dex[0]["mismatches"] = ["token_pair"]

    with pytest.raises(ValueError, match="DEX cross-check failed"):
        build_representative_validation_rows(
            sample,
            v1_lifecycle_rows=v1,
            v2_lifecycle_rows=v2,
            holder_summary_rows=holders,
            dex_crosscheck_rows=dex,
            explorer_summary_rows=explorer,
            market_path_summary_rows=market_paths,
            priced_path_summary_rows=priced_paths,
        )


def test_representative_validation_allows_explicit_unregistered_v2_pool():
    sample, v1, v2, holders, dex, explorer, market_paths, priced_paths = _fixtures()
    dex[-1].update(
        {
            "crosscheck_scope": "no_registered_v4_pool",
            "external_status": "not_applicable",
            "external_match": None,
            "price_crosscheck_scope": "not_applicable",
            "price_match": None,
            "price_crosscheck_status": "not_applicable",
            "price_checkpoints": [],
        }
    )
    explorer[-1].update(
        {
            "verified_dex_swap_transactions": 0,
            "checkpoint_role_counts": {},
            "verified_transactions": 1,
        }
    )
    market_paths[-1].update(
        {
            "stage_counts": {"launch": 1, "v2_curve": 8},
            "path_rows": 9,
            "graduated": False,
            "registered_v4": False,
            "has_v4_market_events": False,
        }
    )

    rows = build_representative_validation_rows(
        sample,
        v1_lifecycle_rows=v1,
        v2_lifecycle_rows=v2,
        holder_summary_rows=holders,
        dex_crosscheck_rows=dex,
        explorer_summary_rows=explorer,
        market_path_summary_rows=market_paths,
        priced_path_summary_rows=priced_paths,
    )
    summary = summarize_representative_validation(rows)

    assert summary["dex_targeted"] == 9
    assert summary["dex_matched"] == 9
    assert summary["dex_price_targeted"] == 9
    assert summary["dex_price_matched"] == 9
    assert summary["no_registered_v4_pool"] == 1
    assert summary["market_path_registered_v4"] == 4


def test_representative_validation_rejects_registration_without_v4_events():
    sample, v1, v2, holders, dex, explorer, market_paths, priced_paths = _fixtures()
    market_paths[-1]["has_v4_market_events"] = False

    with pytest.raises(ValueError, match="has no V4 market events"):
        build_representative_validation_rows(
            sample,
            v1_lifecycle_rows=v1,
            v2_lifecycle_rows=v2,
            holder_summary_rows=holders,
            dex_crosscheck_rows=dex,
            explorer_summary_rows=explorer,
            market_path_summary_rows=market_paths,
            priced_path_summary_rows=priced_paths,
        )


def test_representative_validation_rejects_dex_price_mismatch():
    sample, v1, v2, holders, dex, explorer, market_paths, priced_paths = _fixtures()
    dex[0]["price_match"] = False
    dex[0]["price_crosscheck_status"] = "outside_candle"

    with pytest.raises(ValueError, match="DEX price cross-check failed"):
        build_representative_validation_rows(
            sample,
            v1_lifecycle_rows=v1,
            v2_lifecycle_rows=v2,
            holder_summary_rows=holders,
            dex_crosscheck_rows=dex,
            explorer_summary_rows=explorer,
            market_path_summary_rows=market_paths,
            priced_path_summary_rows=priced_paths,
        )


def test_representative_validation_rejects_nested_dex_checkpoint_mismatch():
    sample, v1, v2, holders, dex, explorer, market_paths, priced_paths = _fixtures()
    dex[0]["price_checkpoints"][1]["price_match"] = False
    dex[0]["price_checkpoints"][1][
        "price_crosscheck_status"
    ] = "outside_candle"

    with pytest.raises(ValueError, match="DEX checkpoint mismatch"):
        build_representative_validation_rows(
            sample,
            v1_lifecycle_rows=v1,
            v2_lifecycle_rows=v2,
            holder_summary_rows=holders,
            dex_crosscheck_rows=dex,
            explorer_summary_rows=explorer,
            market_path_summary_rows=market_paths,
            priced_path_summary_rows=priced_paths,
        )


def test_representative_validation_allows_explicit_no_swap_checkpoint():
    sample, v1, v2, holders, dex, explorer, market_paths, priced_paths = _fixtures()
    dex[0].update(
        {
            "price_crosscheck_scope": "no_swap_checkpoint",
            "price_match": None,
            "price_crosscheck_status": "no_swap_checkpoint",
            "price_checkpoints": [],
        }
    )
    explorer[0].update(
        {
            "verified_dex_swap_transactions": 0,
            "checkpoint_role_counts": {},
            "verified_transactions": 1,
        }
    )

    rows = build_representative_validation_rows(
        sample,
        v1_lifecycle_rows=v1,
        v2_lifecycle_rows=v2,
        holder_summary_rows=holders,
        dex_crosscheck_rows=dex,
        explorer_summary_rows=explorer,
        market_path_summary_rows=market_paths,
        priced_path_summary_rows=priced_paths,
    )
    summary = summarize_representative_validation(rows)
    assert summary["dex_price_targeted"] == 9
    assert summary["dex_price_matched"] == 9
    assert summary["dex_price_no_swap_checkpoint"] == 1
