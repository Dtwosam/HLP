import json
from pathlib import Path

import pytest

from hlp.data.pools_trade_lbp_evidence import (
    POOLS_TRADE_LBP_POOLKEY_VERSION,
    validate_pools_trade_lbp_poolkey,
)


def test_repository_lbp_poolkey_evidence_is_frozen():
    row = validate_pools_trade_lbp_poolkey(
        json.loads(
            Path(
                ".github/phase2-pools-trade-lbp-poolkey.json"
            ).read_text()
        )
    )
    assert row["version"] == POOLS_TRADE_LBP_POOLKEY_VERSION
    assert row["evidence_run_id"] == 35_622_821_426
    assert row["artifact_id"] == 10_649_823_387
    assert row["initializer_created_block"] == 30_001_146
    assert row["migration_block"] == 30_145_704
    assert row["pool_fee"] == 2500
    assert row["pool_tick_spacing"] == 50
    assert row["derived_pool_id"] == (
        "0x4513c2961cc5872078823f0183a94afa"
        "dc169d66d507b5778e91f8a7bbef1c4f"
    )


def test_lbp_poolkey_evidence_rejects_pool_id_drift():
    data = json.loads(
        Path(
            ".github/phase2-pools-trade-lbp-poolkey.json"
        ).read_text()
    )
    data["derived_pool_id"] = "0x" + "11" * 32
    with pytest.raises(ValueError, match="derived PoolId changed"):
        validate_pools_trade_lbp_poolkey(data)
