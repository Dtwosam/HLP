from hlp.config import (
    NOXA_LAUNCH_FACTORY,
    PONS_V1_FACTORIES,
    PONS_V2_FACTORY,
)
from hlp.data.phase2_sources import (
    PHASE2_SOURCE_INVENTORY_VERSION,
    build_phase2_source_inventory,
    validate_phase2_source_inventory,
)


def test_source_inventory_is_deterministic_and_unique():
    rows = build_phase2_source_inventory()
    report = validate_phase2_source_inventory(rows)

    assert report["version"] == PHASE2_SOURCE_INVENTORY_VERSION
    assert report["sources"] == len(rows)
    assert len(report["source_ids"]) == len(set(report["source_ids"]))


def test_pons_sources_are_phase1_proven():
    rows = {row["source_id"]: row for row in build_phase2_source_inventory()}

    assert rows["pons_v1"]["readiness"] == "phase1_proven"
    assert rows["pons_v1"]["launch_contracts"] == [
        address.lower() for address in PONS_V1_FACTORIES
    ]
    assert rows["pons_v2"]["readiness"] == "phase1_proven"
    assert rows["pons_v2"]["launch_contracts"] == [PONS_V2_FACTORY.lower()]


def test_noxa_registry_adapter_is_ready_without_claiming_phase1_proof():
    rows = {row["source_id"]: row for row in build_phase2_source_inventory()}
    noxa = rows["noxa"]

    assert noxa["launch_contracts"] == [NOXA_LAUNCH_FACTORY.lower()]
    assert noxa["readiness"] == "adapter_ready"
    assert "hlp.data.noxa_registry" in noxa["implementation_evidence"]


def test_direct_dex_market_adapters_are_ready_without_claiming_origin_resolution():
    rows = {row["source_id"]: row for row in build_phase2_source_inventory()}

    for source_id in (
        "direct_uniswap_v3",
        "direct_uniswap_v4",
        "direct_sushiswap_v3",
    ):
        row = rows[source_id]
        assert row["source_kind"] == "direct_dex"
        assert row["readiness"] == "adapter_ready"
        assert row["launch_contracts"] == []
        assert "hlp.data.direct_markets" in row["implementation_evidence"]
        assert "multi-pool selection" in row["blocking_gap"]
        assert "launch-origin attribution" in row["blocking_gap"]


def test_inventory_tracks_partial_lifecycle_adapters_without_claiming_phase1_proof():
    rows = {row["source_id"]: row for row in build_phase2_source_inventory()}

    for source_id in (
        "pools_fun",
        "pools_trade_instant",
        "doppler",
        "flap",
        "trench_today",
        "hood_fun_current",
    ):
        assert rows[source_id]["readiness"] == "adapter_ready"
        assert rows[source_id]["implementation_evidence"]
