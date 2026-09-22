import pytest

from hlp.data.phase2_dump_research import build_phase2_dump_geometry
from hlp.data.phase2_research_paths import (
    DIRECT_RESEARCH_COMPONENT_ID,
    PHASE2_RESEARCH_PRICE_PATH_VERSION,
    build_phase2_research_path_components,
    build_phase2_research_price_path,
    materialize_phase2_research_price_path,
)
from hlp.data.phase2_universe import PHASE2_UNIVERSE_VERSION


SHA = "ab" * 32
TOKEN_A = "0x" + "11" * 20
TOKEN_B = "0x" + "22" * 20


INVENTORY = [
    {"source_id": "launch_a", "source_kind": "launchpad"},
    {"source_id": "launch_b", "source_kind": "launchpad"},
    {"source_id": "direct_a", "source_kind": "direct_dex"},
    {"source_id": "direct_b", "source_kind": "direct_dex"},
]


def universe(overlap=False):
    rows = [
        {
            "token": TOKEN_A,
            "source_ids": (
                ["launch_a", "launch_b"] if overlap else ["launch_a"]
            ),
            "universe_status": "eligible",
        },
        {
            "token": TOKEN_B,
            "source_ids": ["direct_a"],
            "universe_status": "eligible",
        },
    ]
    summary = {
        "version": PHASE2_UNIVERSE_VERSION,
        "snapshot_head_block": 100,
        "inventory_sources": 4,
        "complete_source_ids": [
            "launch_a",
            "launch_b",
            "direct_a",
            "direct_b",
        ],
        "eligible_tokens": 2,
        "coverage_complete": True,
        "phase2_universe_frozen": True,
    }
    return rows, summary


def components(overlap=False):
    launch_b = []
    if overlap:
        launch_b = [
            {
                "source_id": "launch_b",
                "token": TOKEN_A,
                "block_number": 2,
                "transaction_index": 0,
                "log_index": 1,
                "market_cap_proxy_usd": "90000",
            }
        ]
    return {
        "launch_a": [
            {
                "source_id": "launch_a",
                "token": TOKEN_A,
                "block_number": 1,
                "transaction_index": None,
                "log_index": 0,
                "market_cap_proxy_usd": "100000",
            },
            {
                "source_id": "launch_a",
                "token": TOKEN_A,
                "block_number": 3,
                "transaction_index": 0,
                "log_index": 0,
                "market_cap_proxy_usd": "70000",
            },
        ],
        "launch_b": launch_b,
        DIRECT_RESEARCH_COMPONENT_ID: [
            {
                "source_id": "direct_b",
                "token": TOKEN_B,
                "block_number": 4,
                "transaction_index": 2,
                "log_index": 3,
                "market_cap_proxy_usd": "150000",
                "canonical_price_series": True,
            }
        ],
    }


def provenance():
    return {
        "launch_a": SHA,
        "launch_b": SHA,
        DIRECT_RESEARCH_COMPONENT_ID: SHA,
    }


def test_research_path_components_collapse_direct_sources_once():
    mapping = build_phase2_research_path_components(INVENTORY)

    assert mapping == {
        DIRECT_RESEARCH_COMPONENT_ID: ("direct_a", "direct_b"),
        "launch_a": ("launch_a",),
        "launch_b": ("launch_b",),
    }


def test_research_price_path_normalizes_real_event_order_and_direct_switches():
    rows, summary = universe()
    path, report = build_phase2_research_price_path(
        components(),
        universe_rows=rows,
        universe_summary=summary,
        universe_sha256=SHA,
        source_inventory=INVENTORY,
        component_provenance_sha256=provenance(),
    )

    assert report["version"] == PHASE2_RESEARCH_PRICE_PATH_VERSION
    assert report["eligible_tokens"] == 2
    assert report["price_points"] == 3
    assert report["direct_dex_sources_collapsed_after_selector"] is True
    assert report["dump_threshold_frozen"] is False
    assert report["outcome_labels_computed"] is False

    assert path[0]["token"] == TOKEN_A
    assert path[0]["transaction_index"] is None
    direct = next(row for row in path if row["token"] == TOKEN_B)
    assert direct["source_ids"] == ["direct_b"]
    assert direct["component_ids"] == [DIRECT_RESEARCH_COMPONENT_ID]

    geometry, geometry_summary = build_phase2_dump_geometry(
        rows,
        path,
        universe_summary=summary,
        universe_sha256=SHA,
        price_path_provenance_sha256=report[
            "normalized_price_path_sha256"
        ],
    )
    assert len(geometry) == 3
    assert geometry_summary["price_points"] == 3


def test_research_price_path_requires_every_frozen_source_membership_path():
    rows, summary = universe(overlap=True)

    with pytest.raises(ValueError, match="membership coverage mismatch"):
        build_phase2_research_price_path(
            components(overlap=False),
            universe_rows=rows,
            universe_summary=summary,
            universe_sha256=SHA,
            source_inventory=INVENTORY,
            component_provenance_sha256=provenance(),
        )


def test_research_price_path_rejects_duplicate_event_price_disagreement():
    rows, summary = universe(overlap=True)
    data = components(overlap=True)
    data["launch_b"][0].update({
        "block_number": 1,
        "transaction_index": None,
        "log_index": 0,
        "market_cap_proxy_usd": "99999",
    })

    with pytest.raises(ValueError, match="duplicate event disagrees"):
        build_phase2_research_price_path(
            data,
            universe_rows=rows,
            universe_summary=summary,
            universe_sha256=SHA,
            source_inventory=INVENTORY,
            component_provenance_sha256=provenance(),
        )


def test_research_price_path_rejects_unfrozen_or_incomplete_source_set():
    rows, summary = universe()
    summary["phase2_universe_frozen"] = False

    with pytest.raises(ValueError, match="requires a frozen"):
        build_phase2_research_price_path(
            components(),
            universe_rows=rows,
            universe_summary=summary,
            universe_sha256=SHA,
            source_inventory=INVENTORY,
            component_provenance_sha256=provenance(),
        )



def test_streaming_research_price_path_matches_in_memory_contract(tmp_path):
    rows, summary = universe(overlap=True)
    data = components(overlap=True)
    expected_rows, expected_report = build_phase2_research_price_path(
        data,
        universe_rows=rows,
        universe_summary=summary,
        universe_sha256=SHA,
        source_inventory=INVENTORY,
        component_provenance_sha256=provenance(),
    )

    output = tmp_path / "research.jsonl"
    manifest, report = materialize_phase2_research_price_path(
        {
            component: iter(component_rows)
            for component, component_rows in data.items()
        },
        universe_rows=rows,
        universe_summary=summary,
        universe_sha256=SHA,
        source_inventory=INVENTORY,
        component_provenance_sha256=provenance(),
        output=output,
    )

    import json
    actual_rows = [
        json.loads(line)
        for line in output.read_text().splitlines()
        if line.strip()
    ]
    assert actual_rows == expected_rows
    assert manifest["sha256"] == expected_report[
        "normalized_price_path_sha256"
    ]
    assert report["normalized_price_path_sha256"] == manifest["sha256"]
    assert report["price_points"] == expected_report["price_points"]
    assert report["token_price_points"] == expected_report[
        "token_price_points"
    ]
    assert report["streaming_materialization"] is True
    assert report["phase2_dump_detector_frozen"] is False
    assert report["outcome_labels_computed"] is False
