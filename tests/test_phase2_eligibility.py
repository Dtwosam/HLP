import pytest

from hlp.data.phase2_eligibility import (
    PHASE2_LAUNCHPAD_ELIGIBILITY_VERSION,
    build_launchpad_eligibility_handoff,
)


SHA = "ab" * 32
TOKEN = "0x" + "11" * 20
INVENTORY = [
    {
        "source_id": "launch",
        "source_kind": "launchpad",
        "readiness": "adapter_ready",
    },
    {
        "source_id": "direct",
        "source_kind": "direct_dex",
        "readiness": "adapter_ready",
    },
]


def coverage():
    return {
        "source_id": "launch",
        "source_readiness": "adapter_ready",
        "coverage_status": "complete",
        "required_start_block": 1,
        "first_block": 1,
        "last_block": 100,
        "snapshot_head_block": 100,
        "continuous": True,
        "missing_ranges": [],
        "tokens_discovered": 1,
        "price_points": 4,
        "priced_points": 4,
    }


def summary_row():
    return {
        "token": TOKEN,
        "price_points": 4,
        "priced_points": 4,
        "unpriced_points": 0,
        "pricing_complete": True,
        "max_market_cap_proxy_usd": "150000",
        "max_market_cap_block": 50,
        "crossed_100k": True,
    }


def test_launchpad_eligibility_handoff_reconciles_coverage():
    rows, summary = build_launchpad_eligibility_handoff(
        "launch",
        [summary_row()],
        coverage(),
        source_inventory=INVENTORY,
        provenance_sha256=SHA,
    )

    assert len(rows) == 1
    assert rows[0]["source_id"] == "launch"
    assert rows[0]["canonical_price_series"] is True
    assert summary["version"] == PHASE2_LAUNCHPAD_ELIGIBILITY_VERSION
    assert summary["eligible_tokens"] == 1
    assert summary["phase2_universe_source_ready"] is True
    assert summary["phase2_universe_frozen"] is False


def test_launchpad_eligibility_handoff_rejects_direct_sources():
    report = coverage()
    report["source_id"] = "direct"

    with pytest.raises(ValueError, match="rejects direct"):
        build_launchpad_eligibility_handoff(
            "direct",
            [summary_row()],
            report,
            source_inventory=INVENTORY,
            provenance_sha256=SHA,
        )


def test_launchpad_eligibility_handoff_requires_exact_token_count():
    report = coverage()
    report["tokens_discovered"] = 2

    with pytest.raises(ValueError, match="token count"):
        build_launchpad_eligibility_handoff(
            "launch",
            [summary_row()],
            report,
            source_inventory=INVENTORY,
            provenance_sha256=SHA,
        )


def test_launchpad_eligibility_handoff_requires_exact_point_accounting():
    report = coverage()
    report["price_points"] = 5
    report["priced_points"] = 5

    with pytest.raises(ValueError, match="price-point count"):
        build_launchpad_eligibility_handoff(
            "launch",
            [summary_row()],
            report,
            source_inventory=INVENTORY,
            provenance_sha256=SHA,
        )
