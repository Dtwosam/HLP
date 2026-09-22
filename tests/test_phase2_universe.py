import pytest

from hlp.config import ROBINHOOD_USDG, ROBINHOOD_WETH
from hlp.data.phase2_coverage import PHASE2_COVERAGE_LEDGER_VERSION
from hlp.data.phase2_universe import (
    PHASE2_UNIVERSE_VERSION,
    build_phase2_universe,
    normalize_phase2_source_eligibility_rows,
)


SHA = "ab" * 32
TOKEN_A = "0x" + "11" * 20
TOKEN_B = "0x" + "22" * 20
STOCK = "0x" + "33" * 20


INVENTORY = [
    {"source_id": "a", "readiness": "adapter_ready"},
    {"source_id": "b", "readiness": "adapter_ready"},
]


def complete(source_id):
    return {
        "source_id": source_id,
        "source_readiness": "adapter_ready",
        "coverage_status": "complete",
        "required_start_block": 1,
        "first_block": 1,
        "last_block": 100,
        "continuous": True,
        "missing_ranges": [],
        "tokens_discovered": 1,
        "price_points": 2,
        "priced_points": 2,
        "observed_volume_usd": None,
        "provenance_sha256": SHA,
        "blocking_reason": None,
    }


def ledger(status_b="complete"):
    row_b = complete("b")
    if status_b != "complete":
        row_b.update({
            "coverage_status": "not_started",
            "first_block": None,
            "last_block": None,
            "continuous": None,
            "tokens_discovered": 0,
            "price_points": 0,
            "priced_points": 0,
            "provenance_sha256": None,
        })
    return {
        "version": PHASE2_COVERAGE_LEDGER_VERSION,
        "snapshot_head_block": 100,
        "sources": [complete("a"), row_b],
    }


def exclusion_rows():
    return [
        {
            "address": ROBINHOOD_WETH.lower(),
            "exclusion_class": "canonical_weth",
            "identity_source": "config",
        },
        {
            "address": ROBINHOOD_USDG.lower(),
            "exclusion_class": "canonical_usdg",
            "identity_source": "config",
        },
        {
            "address": STOCK,
            "exclusion_class": "robinhood_canonical_asset",
            "identity_source": "official",
        },
    ]


def raw(token, maximum):
    maximum = str(maximum)
    return {
        "token": token,
        "price_points": 3,
        "priced_points": 3,
        "unpriced_points": 0,
        "pricing_complete": True,
        "max_market_cap_proxy_usd": maximum,
        "max_market_cap_block": 50,
        "crossed_100k": float(maximum) >= 100000,
    }


def normalized(source_id, rows):
    return normalize_phase2_source_eligibility_rows(
        source_id,
        rows,
        provenance_sha256=SHA,
        canonical_price_series=True,
    )


def test_phase2_universe_requires_all_source_coverage_complete():
    with pytest.raises(ValueError, match="complete coverage"):
        build_phase2_universe(
            {
                "a": normalized("a", [raw(TOKEN_A, 120000)]),
                "b": [],
            },
            source_inventory=INVENTORY,
            coverage_ledger=ledger("not_started"),
            exclusion_rows=exclusion_rows(),
        )


def test_phase2_universe_applies_threshold_and_exact_exclusions():
    universe, rejected, summary = build_phase2_universe(
        {
            "a": normalized("a", [
                raw(TOKEN_A, 120000),
                raw(STOCK, 500000),
            ]),
            "b": normalized("b", [raw(TOKEN_B, 90000)]),
        },
        source_inventory=INVENTORY,
        coverage_ledger=ledger(),
        exclusion_rows=exclusion_rows(),
    )

    assert [row["token"] for row in universe] == [TOKEN_A]
    rejected_by_token = {row["token"]: row for row in rejected}
    assert rejected_by_token[STOCK]["universe_status"] == "excluded"
    assert rejected_by_token[TOKEN_B]["universe_status"] == (
        "below_threshold"
    )
    assert summary["version"] == PHASE2_UNIVERSE_VERSION
    assert summary["eligible_tokens"] == 1
    assert summary["excluded_eligible_tokens"] == 1
    assert summary["phase2_universe_frozen"] is True


def test_phase2_universe_deduplicates_cross_source_token_by_address():
    universe, rejected, summary = build_phase2_universe(
        {
            "a": normalized("a", [raw(TOKEN_A, 120000)]),
            "b": normalized("b", [raw(TOKEN_A, 150000)]),
        },
        source_inventory=INVENTORY,
        coverage_ledger=ledger(),
        exclusion_rows=exclusion_rows(),
    )

    assert rejected == []
    assert len(universe) == 1
    assert universe[0]["source_ids"] == ["a", "b"]
    assert universe[0]["max_market_cap_proxy_usd"] == "150000"
    assert summary["source_overlap_tokens"] == 1


def test_source_eligibility_normalizer_rejects_threshold_disagreement():
    row = raw(TOKEN_A, 99999)
    row["crossed_100k"] = True

    with pytest.raises(ValueError, match="threshold evidence"):
        normalized("a", [row])


def test_phase2_universe_requires_canonical_price_series():
    rows = normalized("a", [raw(TOKEN_A, 120000)])
    rows[0]["canonical_price_series"] = False

    with pytest.raises(ValueError, match="not canonical"):
        build_phase2_universe(
            {"a": rows, "b": []},
            source_inventory=INVENTORY,
            coverage_ledger=ledger(),
            exclusion_rows=exclusion_rows(),
        )
