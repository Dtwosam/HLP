import pytest

from hlp.data.exclusions import build_phase2_exclusion_registry
from hlp.data.phase2_universe import (
    merge_phase2_universe,
    normalize_phase2_source_summary,
    summarize_phase2_universe,
)


TOKEN = "0x" + "11" * 20
OTHER = "0x" + "22" * 20
STOCK = "0x" + "33" * 20


def generic_summary(
    token=TOKEN,
    *,
    crossed=False,
    price_points=2,
    priced_points=2,
    maximum="90000",
    maximum_block=20,
):
    return {
        "token": token,
        "venue": "noxa",
        "crossed_100k": crossed,
        "price_points": price_points,
        "priced_points": priced_points,
        "max_market_cap_proxy_usd": maximum,
        "max_market_cap_block": maximum_block,
    }


def test_normalizer_derives_generic_threshold_statuses_without_lookahead_guessing():
    rows = normalize_phase2_source_summary(
        "noxa",
        [
            generic_summary(
                crossed=True,
                maximum="125000",
                maximum_block=21,
            ),
            generic_summary(
                token=OTHER,
                price_points=3,
                priced_points=2,
                maximum="95000",
            ),
        ],
    )

    assert rows[0]["eligibility_status"] == "eligible"
    assert rows[0]["pricing_complete"] is True
    assert rows[1]["eligibility_status"] == "unknown"
    assert rows[1]["unpriced_points"] == 1


def test_normalizer_honors_explicit_phase1_status_only_when_evidence_agrees():
    row = {
        "token": TOKEN,
        "eligibility_status": "unknown",
        "crossed_100k": False,
        "price_points": 4,
        "priced_points": 3,
        "unpriced_points": 1,
        "max_market_cap_proxy_usd": "99000",
        "max_market_cap_block": 30,
    }
    normalized = normalize_phase2_source_summary("pons_v1", [row])
    assert normalized[0]["eligibility_status"] == "unknown"

    with pytest.raises(ValueError, match="contradicts price evidence"):
        normalize_phase2_source_summary(
            "pons_v1",
            [{**row, "eligibility_status": "ineligible"}],
        )


def test_merge_eligible_source_beats_unknown_and_preserves_max_provenance():
    rows = merge_phase2_universe(
        {
            "pons_v1": [
                {
                    "token": TOKEN,
                    "eligibility_status": "unknown",
                    "crossed_100k": False,
                    "price_points": 2,
                    "priced_points": 1,
                    "unpriced_points": 1,
                    "max_market_cap_proxy_usd": "80000",
                    "max_market_cap_block": 10,
                }
            ],
            "noxa": [
                generic_summary(
                    crossed=True,
                    maximum="250000",
                    maximum_block=25,
                )
            ],
        },
        build_phase2_exclusion_registry(),
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["threshold_eligibility_status"] == "eligible"
    assert row["phase2_universe_status"] == "eligible"
    assert row["included"] is True
    assert row["source_ids"] == ["noxa", "pons_v1"]
    assert row["max_market_cap_proxy_usd"] == "250000"
    assert row["max_market_cap_source_id"] == "noxa"
    assert row["max_market_cap_block"] == 25


def test_exact_address_exclusion_overrides_membership_not_threshold_evidence():
    registry = build_phase2_exclusion_registry(
        [
            {
                "asset_id": "stock",
                "token_symbol": "STOCK",
                "token_name": "Canonical Stock",
                "contract_address": STOCK,
                "chain_id": 4663,
                "status": "ASSET_STATUS_ACTIVE",
            }
        ]
    )
    rows = merge_phase2_universe(
        {
            "noxa": [
                generic_summary(
                    token=STOCK,
                    crossed=True,
                    maximum="900000",
                )
            ]
        },
        registry,
    )

    row = rows[0]
    assert row["threshold_eligibility_status"] == "eligible"
    assert row["crossed_100k"] is True
    assert row["phase2_universe_status"] == "excluded"
    assert row["included"] is False
    assert row["exclusion_category"] == "robinhood_canonical_asset"


def test_merge_keeps_complete_non_crossing_history_ineligible():
    rows = merge_phase2_universe(
        {"noxa": [generic_summary()]},
        build_phase2_exclusion_registry(),
    )
    assert rows[0]["phase2_universe_status"] == "ineligible"


def test_source_normalizer_fails_closed_on_bad_counts_and_threshold_claims():
    with pytest.raises(ValueError, match="exceed"):
        normalize_phase2_source_summary(
            "noxa",
            [generic_summary(price_points=1, priced_points=2)],
        )
    with pytest.raises(ValueError, match="contradicts"):
        normalize_phase2_source_summary(
            "noxa",
            [generic_summary(crossed=True, maximum="99999")],
        )


def test_unknown_source_and_duplicate_source_token_fail_closed():
    with pytest.raises(ValueError, match="unknown Phase-2 source"):
        merge_phase2_universe(
            {"mystery": [generic_summary()]},
            build_phase2_exclusion_registry(),
        )

    with pytest.raises(ValueError, match="duplicate Phase-2 source/token"):
        merge_phase2_universe(
            {"noxa": [generic_summary(), generic_summary()]},
            build_phase2_exclusion_registry(),
        )


def test_phase2_universe_summary_counts_membership_and_sources():
    rows = merge_phase2_universe(
        {
            "noxa": [
                generic_summary(
                    crossed=True,
                    maximum="120000",
                ),
                generic_summary(token=OTHER),
            ]
        },
        build_phase2_exclusion_registry(),
    )
    report = summarize_phase2_universe(rows)

    assert report["tokens"] == 2
    assert report["included_tokens"] == 1
    assert report["ineligible_tokens"] == 1
    assert report["unknown_tokens"] == 0
    assert report["covered_source_ids"] == ["noxa"]
