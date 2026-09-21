import json
from pathlib import Path

import pytest

from hlp.data.pools_trade_cca_orientation import (
    FROZEN_CCA_ORIENTATION,
    POOLS_TRADE_CCA_ORIENTATION_VERSION,
    validate_pools_trade_cca_orientation,
)


def frozen():
    return json.loads(
        Path(
            ".github/phase2-pools-trade-cca-orientation.json"
        ).read_text()
    )


def test_repository_cca_orientation_is_frozen():
    row = validate_pools_trade_cca_orientation(frozen())
    assert row["version"] == POOLS_TRADE_CCA_ORIENTATION_VERSION
    assert row["orientation"] == FROZEN_CCA_ORIENTATION
    assert row["orientation"] == "quote_per_token"
    assert row["evidence_run_id"] == 35_627_264_268
    assert row["artifact_id"] == 10_653_022_924
    assert row["same_transaction"] is True
    assert row["cca_block"] == 30_493_816
    assert row["v4_initialize_block"] == 30_493_816
    assert float(row["direct_relative_error"]) < 1e-20


def test_cca_orientation_rejects_inverse_freeze():
    data = frozen()
    data["orientation"] = "token_per_quote"
    with pytest.raises(ValueError, match="orientation changed"):
        validate_pools_trade_cca_orientation(data)


def test_cca_orientation_requires_same_transaction_order():
    data = frozen()
    data["v4_initialize"]["transaction_hash"] = "0x" + "11" * 32
    with pytest.raises(ValueError, match="one transaction"):
        validate_pools_trade_cca_orientation(data)


def test_cca_orientation_rejects_error_threshold_drift():
    data = frozen()
    data["max_accepted_relative_error"] = "1e-40"
    with pytest.raises(ValueError, match="exceeds error threshold"):
        validate_pools_trade_cca_orientation(data)
