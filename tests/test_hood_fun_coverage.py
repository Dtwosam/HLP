import pytest

from hlp.data.hood_fun_coverage import (
    validate_hood_fun_coverage_report,
)


SHA = "ab" * 32


def report():
    return {
        "source_id": "hood_fun_current",
        "source_readiness": "adapter_ready",
        "coverage_status": "complete",
        "required_start_block": 100,
        "first_block": 100,
        "last_block": 200,
        "continuous": True,
        "missing_ranges": [],
        "tokens_discovered": 3,
        "price_points": 10,
        "priced_points": 10,
        "observed_volume_usd": None,
        "provenance_sha256": SHA,
        "blocking_reason": None,
        "snapshot_head_block": 200,
        "event_tape_sha256": "cd" * 32,
        "sparse_anchor_sha256": "ef" * 32,
        "summary_sha256": "12" * 32,
        "eligible_tokens": 2,
        "sparse_anchor_windows": 4,
        "rpc_route": "solidrpc_keyless_public",
        "rpc_requests": 20,
    }


def validate(row):
    return validate_hood_fun_coverage_report(
        row,
        generation="current",
        required_start_block=100,
        snapshot_head_block=200,
    )


def test_validate_complete_hood_fun_coverage():
    row = validate(report())
    assert row["coverage_status"] == "complete"
    assert row["priced_points"] == row["price_points"] == 10
    assert row["eligible_tokens"] == 2


def test_hood_fun_coverage_rejects_unpriced_points():
    data = report()
    data["priced_points"] = 9
    with pytest.raises(ValueError, match="unpriced points"):
        validate(data)


def test_hood_fun_coverage_rejects_snapshot_gap():
    data = report()
    data["last_block"] = 199
    with pytest.raises(ValueError, match="reach snapshot"):
        validate(data)


def test_hood_fun_coverage_rejects_hash_drift():
    data = report()
    data["event_tape_sha256"] = "bad"
    with pytest.raises(ValueError, match="event tape"):
        validate(data)


def test_hood_fun_complete_report_cannot_remain_blocked():
    data = report()
    data["blocking_reason"] = "still blocked"
    with pytest.raises(ValueError, match="blocking_reason"):
        validate(data)
