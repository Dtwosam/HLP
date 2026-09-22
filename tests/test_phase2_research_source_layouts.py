import pytest

from hlp.data.phase2_research_paths import DIRECT_RESEARCH_COMPONENT_ID
from hlp.data.phase2_research_source_layouts import (
    PHASE2_RESEARCH_SOURCE_LAYOUT_VERSION,
    build_phase2_research_source_layouts,
    validate_phase2_research_source_layouts,
)
from hlp.data.phase2_sources import build_phase2_source_inventory


def test_research_source_layouts_cover_all_11_launchpads_and_one_direct_component():
    layouts = build_phase2_research_source_layouts()
    report = validate_phase2_research_source_layouts(
        layouts,
        build_phase2_source_inventory(),
    )

    assert report["version"] == PHASE2_RESEARCH_SOURCE_LAYOUT_VERSION
    assert report["components"] == 12
    assert report["launchpad_components"] == 11
    assert report["direct_sources_collapsed"] == 3
    assert report["all_sources_have_explicit_layout"] is True
    assert report["dump_threshold_frozen"] is False
    assert report["outcome_labels_computed"] is False
    assert DIRECT_RESEARCH_COMPONENT_ID in layouts


def test_research_source_layouts_lock_known_storage_strategies():
    layouts = build_phase2_research_source_layouts()

    assert layouts["pons_v1"]["strategy"] == "canonical_replay"
    assert layouts["pons_v2"]["strategy"] == "canonical_replay"
    assert layouts["hood_fun_current"]["strategy"] == "coverage_single"
    assert layouts["hood_fun_previous"]["strategy"] == "coverage_single"
    assert layouts["pools_fun"]["strategy"] == "coverage_sharded"
    assert layouts["doppler"]["strategy"] == "coverage_sharded"
    assert layouts["noxa"]["strategy"] == "coverage_sharded"
    assert layouts["flap"]["strategy"] == "composite"
    assert layouts["trench_today"]["strategy"] == "composite"
    assert layouts["pools_trade_lbp"]["strategy"] == "composite"

    flap_v3 = next(
        row
        for row in layouts["flap"]["segments"]
        if row["segment_id"] == "flap_v3"
    )
    assert flap_v3["storage_mode"] == "shard_report_rebuild"

    direct = layouts[DIRECT_RESEARCH_COMPONENT_ID]["segments"][0]
    assert direct["data_path"] == "direct-canonical-market-cap-points.jsonl"


def test_research_source_layout_validation_rejects_implicit_or_unknown_layouts():
    layouts = build_phase2_research_source_layouts()
    layouts["flap"]["segments"][1]["storage_mode"] = "guess_from_files"

    with pytest.raises(ValueError, match="storage mode changed"):
        validate_phase2_research_source_layouts(
            layouts,
            build_phase2_source_inventory(),
        )
