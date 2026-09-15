import pytest

from hlp.data.phase1_coverage import (
    PHASE1_SNAPSHOT_HEAD,
    summarize_sharded_manifest_coverage,
    summarize_snapshot_manifest_coverage,
    validate_representative_coverage_report,
)


def _sharded(label, *, start=100, head=PHASE1_SNAPSHOT_HEAD):
    mid = (start + head) // 2
    return {
        "provenance": {
            "source": label,
            "chain_id": 4663,
            "snapshot_head_block": head,
            "shards": [
                {"from_block": start, "to_block": mid},
                {"from_block": mid + 1, "to_block": head},
            ],
        }
    }


def _snapshot(label):
    return {
        "provenance": {
            "source": label,
            "chain_id": 4663,
            "snapshot_head_block": PHASE1_SNAPSHOT_HEAD,
        }
    }


def test_sharded_coverage_proves_exact_continuity_and_head():
    result = summarize_sharded_manifest_coverage(
        _sharded("v1"),
        label="v1_v3",
        required_start=500,
    )

    assert result["first_block"] == 100
    assert result["last_block"] == PHASE1_SNAPSHOT_HEAD
    assert result["shards"] == 2
    assert result["continuous"] is True


def test_sharded_coverage_rejects_gap():
    manifest = _sharded("v1")
    manifest["provenance"]["shards"][1]["from_block"] += 1

    with pytest.raises(ValueError, match="gap/overlap"):
        summarize_sharded_manifest_coverage(
            manifest,
            label="v1_v3",
        )


def test_sharded_coverage_can_require_exact_start():
    with pytest.raises(ValueError, match="coverage start changed"):
        summarize_sharded_manifest_coverage(
            _sharded("transfers", start=100),
            label="representative_transfers",
            required_start=101,
            exact_start=True,
        )


def test_snapshot_coverage_requires_phase1_head():
    result = summarize_snapshot_manifest_coverage(
        _snapshot("oracle"),
        label="stock_oracle_updates",
    )
    assert result["snapshot_pinned"] is True

    bad = _snapshot("oracle")
    bad["provenance"]["snapshot_head_block"] -= 1
    with pytest.raises(ValueError, match="snapshot head changed"):
        summarize_snapshot_manifest_coverage(
            bad,
            label="stock_oracle_updates",
        )


def _coverage_report(sample_start=1000):
    sharded_labels = [
        "v1_v3",
        "v2_curve",
        "v2_graduation",
        "v2_registration",
        "v2_v4",
        "weth_usdg_anchor",
        "representative_transfers",
    ]
    snapshot_labels = [
        "stock_oracle_initial",
        "stock_oracle_updates",
        "quote_fallback_initial",
        "quote_fallback_updates",
    ]
    sources = []
    for label in sharded_labels:
        start = sample_start if label == "representative_transfers" else 100
        sources.append(
            {
                "label": label,
                "first_block": start,
                "last_block": PHASE1_SNAPSHOT_HEAD,
                "shards": 2,
                "continuous": True,
                "required_start_block": (
                    sample_start
                    if label == "representative_transfers"
                    else 500
                ),
                "snapshot_head_block": PHASE1_SNAPSHOT_HEAD,
            }
        )
    for label in snapshot_labels:
        sources.append(
            {
                "label": label,
                "snapshot_head_block": PHASE1_SNAPSHOT_HEAD,
                "snapshot_pinned": True,
            }
        )
    return {"sources": sources}


def test_representative_coverage_report_proves_no_block_gaps():
    result = validate_representative_coverage_report(
        _coverage_report(),
        sample_start_block=1000,
    )

    assert result == {
        "sources": 11,
        "continuous_sharded_sources": 7,
        "snapshot_pinned_sources": 4,
        "sample_start_block": 1000,
        "snapshot_head_block": PHASE1_SNAPSHOT_HEAD,
        "no_unexplained_block_gaps": True,
    }


def test_representative_coverage_report_rejects_missing_source():
    report = _coverage_report()
    report["sources"] = report["sources"][:-1]

    with pytest.raises(ValueError, match="source contract mismatch"):
        validate_representative_coverage_report(
            report,
            sample_start_block=1000,
        )


def test_representative_coverage_report_rejects_transfer_start_drift():
    report = _coverage_report()
    transfer = next(
        row for row in report["sources"]
        if row["label"] == "representative_transfers"
    )
    transfer["first_block"] = 999

    with pytest.raises(ValueError, match="earliest sample"):
        validate_representative_coverage_report(
            report,
            sample_start_block=1000,
        )
