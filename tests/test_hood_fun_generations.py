import json
from pathlib import Path

import pytest

from hlp.data.hood_fun_generations import (
    HOOD_FUN_DEPLOYMENTS_VERSION,
    HOOD_FUN_LEGACY_COMPATIBILITY_VERSION,
    validate_hood_fun_deployments,
    validate_hood_fun_legacy_compatibility,
)


def test_repository_hood_fun_deployment_evidence_is_frozen():
    row = validate_hood_fun_deployments(
        json.loads(
            Path(".github/phase2-hoodfun-deployments.json").read_text()
        )
    )

    assert row["version"] == HOOD_FUN_DEPLOYMENTS_VERSION
    assert row["snapshot_head_block"] == 54_486_035
    assert row["pricing_anchor"]["first_code_block"] == 1_506_281
    assert (
        row["generations"]["previous"]["first_code_block"]
        == 1_676_992
    )
    assert (
        row["generations"]["current"]["first_code_block"]
        == 5_611_265
    )


def test_deployment_evidence_rejects_anchor_after_generation():
    data = json.loads(
        Path(".github/phase2-hoodfun-deployments.json").read_text()
    )
    data["pricing_anchor"]["first_code_block"] = 6_000_000

    with pytest.raises(ValueError, match="ordering changed"):
        validate_hood_fun_deployments(data)



def test_repository_legacy_hood_fun_compatibility_is_frozen():
    row = validate_hood_fun_legacy_compatibility(
        json.loads(
            Path(
                ".github/phase2-hoodfun-legacy-compatibility.json"
            ).read_text()
        )
    )

    assert row["version"] == HOOD_FUN_LEGACY_COMPATIBILITY_VERSION
    assert row["evidence_run_id"] == 35_614_752_750
    assert row["artifact_id"] == 10_646_067_112
    assert row["first_code_block"] == 1_676_992
    assert row["probe_blocks_scanned"] == 100_000
    assert row["event_counts"] == {
        "token_created": 1,
        "trade": 21,
    }
    assert row["current_surface_compatible"] is True


def test_legacy_hood_fun_compatibility_requires_both_core_events():
    data = json.loads(
        Path(
            ".github/phase2-hoodfun-legacy-compatibility.json"
        ).read_text()
    )
    data["event_counts"]["trade"] = 0

    with pytest.raises(ValueError, match="both core event types"):
        validate_hood_fun_legacy_compatibility(data)
