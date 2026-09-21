import json
from pathlib import Path

import pytest

from hlp.data.hood_fun_generations import (
    HOOD_FUN_DEPLOYMENTS_VERSION,
    validate_hood_fun_deployments,
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
