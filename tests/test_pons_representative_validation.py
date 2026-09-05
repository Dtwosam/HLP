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
            }
        )

    return sample, v1, v2, holders, dex


def test_representative_validation_joins_all_phase1_evidence():
    sample, v1, v2, holders, dex = _fixtures()

    rows = build_representative_validation_rows(
        sample,
        v1_lifecycle_rows=v1,
        v2_lifecycle_rows=v2,
        holder_summary_rows=holders,
        dex_crosscheck_rows=dex,
    )
    summary = summarize_representative_validation(rows)

    assert len(rows) == 10
    assert all(row["validation_status"] == "complete" for row in rows)
    assert summary["tokens"] == 10
    assert summary["sample_groups"] == {"failure": 5, "runner": 5}
    assert summary["pons_versions"] == {"v1": 5, "v2": 5}
    assert summary["priced_points"] == 100
    assert summary["transfers"] == sum(25 + index for index in range(1, 11))
    assert summary["dex_targeted"] == 10
    assert summary["dex_matched"] == 10
    assert summary["dex_price_targeted"] == 10
    assert summary["dex_price_matched"] == 10
    assert summary["dex_price_no_swap_checkpoint"] == 0


def test_representative_validation_fails_closed_on_missing_holder():
    sample, v1, v2, holders, dex = _fixtures()

    with pytest.raises(ValueError, match="holder summary coverage"):
        build_representative_validation_rows(
            sample,
            v1_lifecycle_rows=v1,
            v2_lifecycle_rows=v2,
            holder_summary_rows=holders[:-1],
            dex_crosscheck_rows=dex,
        )


def test_representative_validation_requires_priced_market_evidence():
    sample, v1, v2, holders, dex = _fixtures()
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
        )


def test_representative_validation_rejects_external_pool_mismatch():
    sample, v1, v2, holders, dex = _fixtures()
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
        )


def test_representative_validation_allows_explicit_unregistered_v2_pool():
    sample, v1, v2, holders, dex = _fixtures()
    dex[-1].update(
        {
            "crosscheck_scope": "no_registered_v4_pool",
            "external_status": "not_applicable",
            "external_match": None,
            "price_crosscheck_scope": "not_applicable",
            "price_match": None,
            "price_crosscheck_status": "not_applicable",
        }
    )

    rows = build_representative_validation_rows(
        sample,
        v1_lifecycle_rows=v1,
        v2_lifecycle_rows=v2,
        holder_summary_rows=holders,
        dex_crosscheck_rows=dex,
    )
    summary = summarize_representative_validation(rows)

    assert summary["dex_targeted"] == 9
    assert summary["dex_matched"] == 9
    assert summary["dex_price_targeted"] == 9
    assert summary["dex_price_matched"] == 9
    assert summary["no_registered_v4_pool"] == 1


def test_representative_validation_rejects_dex_price_mismatch():
    sample, v1, v2, holders, dex = _fixtures()
    dex[0]["price_match"] = False
    dex[0]["price_crosscheck_status"] = "outside_candle"

    with pytest.raises(ValueError, match="DEX price cross-check failed"):
        build_representative_validation_rows(
            sample,
            v1_lifecycle_rows=v1,
            v2_lifecycle_rows=v2,
            holder_summary_rows=holders,
            dex_crosscheck_rows=dex,
        )


def test_representative_validation_allows_explicit_no_swap_checkpoint():
    sample, v1, v2, holders, dex = _fixtures()
    dex[0].update(
        {
            "price_crosscheck_scope": "no_swap_checkpoint",
            "price_match": None,
            "price_crosscheck_status": "no_swap_checkpoint",
        }
    )

    rows = build_representative_validation_rows(
        sample,
        v1_lifecycle_rows=v1,
        v2_lifecycle_rows=v2,
        holder_summary_rows=holders,
        dex_crosscheck_rows=dex,
    )
    summary = summarize_representative_validation(rows)
    assert summary["dex_price_targeted"] == 9
    assert summary["dex_price_matched"] == 9
    assert summary["dex_price_no_swap_checkpoint"] == 1
