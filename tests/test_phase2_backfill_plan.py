import json
from pathlib import Path

import pytest

from hlp.config import SOLIDRPC_PUBLIC_FILTERED_LOG_BLOCK_CAP
from hlp.data.phase2_backfill_plan import (
    estimate_source_discovery_windows,
)


def test_estimate_source_discovery_windows_is_lower_bound():
    report = estimate_source_discovery_windows(
        [
            {
                "source_id": "a",
                "source_kind": "launchpad",
                "source_readiness": "adapter_ready",
                "required_start_block": 1,
            },
            {
                "source_id": "b",
                "source_kind": "direct_dex",
                "source_readiness": "adapter_ready",
                "required_start_block": 301,
            },
        ],
        snapshot_head_block=500,
        filtered_log_block_cap=200,
    )
    assert report["sources"] == 2
    assert report["minimum_discovery_windows"] == 4
    assert [row["source_id"] for row in report["rows"]] == [
        "b",
        "a",
    ]
    assert report["lower_bound_only"] is True
    assert "downstream_pool_event_tapes" in report["excludes"]


def test_estimate_source_discovery_windows_rejects_duplicate_source():
    with pytest.raises(ValueError, match="repeats source"):
        estimate_source_discovery_windows(
            [
                {"source_id": "a", "required_start_block": 1},
                {"source_id": "a", "required_start_block": 2},
            ],
            snapshot_head_block=100,
            filtered_log_block_cap=20,
        )


def test_repository_boundary_plan_matches_current_keyless_cap():
    frozen = json.loads(
        Path(
            ".github/phase2-source-deployment-boundaries.json"
        ).read_text()
    )
    report = estimate_source_discovery_windows(
        frozen["sources"],
        snapshot_head_block=frozen["snapshot_head_block"],
        filtered_log_block_cap=SOLIDRPC_PUBLIC_FILTERED_LOG_BLOCK_CAP,
    )

    assert report["sources"] == 12
    assert report["filtered_log_block_cap"] == 200
    assert report["minimum_discovery_windows"] == 2_932_208
    rows = {
        row["source_id"]: row
        for row in report["rows"]
    }
    assert rows["pools_fun"]["minimum_discovery_windows"] == 104_580
    assert (
        rows["hood_fun_current"]["minimum_discovery_windows"]
        == 244_374
    )
    assert (
        rows["hood_fun_previous"]["minimum_discovery_windows"]
        == 264_046
    )
