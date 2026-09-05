import pytest

from hlp.data.pons_explorer_crosscheck import (
    build_representative_explorer_targets,
    build_representative_explorer_token_summaries,
    reconcile_blockscout_transaction,
    summarize_representative_explorer_crosscheck,
)


def _token(index: int) -> str:
    return "0x" + f"{index:040x}"


def _tx(index: int) -> str:
    return "0x" + f"{index:064x}"


def _sample():
    return [
        {
            "token": _token(index),
            "pons_version": "v1" if index <= 5 else "v2",
            "sample_group": "runner" if index % 2 else "failure",
            "launch_block": 1_000 + index,
        }
        for index in range(1, 11)
    ]


def _market_paths():
    return [
        {
            "token": _token(index),
            "pons_version": "v1" if index <= 5 else "v2",
            "path_stage": "launch",
            "block_number": 1_000 + index,
            "transaction_hash": _tx(index),
            "transaction_index": 1,
            "log_index": 0,
        }
        for index in range(1, 11)
    ]


def _priced_paths():
    rows = []
    for index in range(1, 11):
        version = "v1" if index <= 5 else "v2"
        rows.append(
            {
                "token": _token(index),
                "pons_version": version,
                "price_path_phase": "v1_v3" if version == "v1" else "v2_v4",
                "event_type": "v3_swap" if version == "v1" else "v4_swap",
                "block_number": 2_000 + index,
                "transaction_hash": _tx(100 + index),
                "transaction_index": 2,
                "log_index": 3,
                "token_price_usd": str(index),
                "market_cap_proxy_usd": str(index * 1_000_000),
            }
        )
    return rows


def test_build_explorer_targets_covers_launch_and_deduplicated_dex_roles():
    targets = build_representative_explorer_targets(
        _sample(),
        _market_paths(),
        _priced_paths(),
    )

    assert len(targets) == 20
    launches = [
        row for row in targets
        if row["verification_type"] == "launch_transaction"
    ]
    dex = [
        row for row in targets
        if row["verification_type"] == "dex_swap_transaction"
    ]
    assert len(launches) == 10
    assert len(dex) == 10
    assert all(
        row["checkpoint_roles"] == ["first", "max", "last"]
        for row in dex
    )


def test_build_explorer_targets_rejects_missing_launch():
    with pytest.raises(ValueError, match="launch coverage missing"):
        build_representative_explorer_targets(
            _sample(),
            _market_paths()[:-1],
            _priced_paths(),
        )


def test_reconcile_blockscout_transaction_matches_hash_and_block():
    target = {
        "token": _token(1),
        "verification_type": "launch_transaction",
        "transaction_hash": _tx(1),
        "block_number": 1001,
    }
    result = reconcile_blockscout_transaction(
        target,
        {
            "hash": _tx(1),
            "block": 1001,
            "timestamp": "2026-09-01T00:00:00Z",
        },
    )

    assert result["external_match"] is True
    assert result["mismatches"] == []
    assert result["external_block_number"] == 1001


def test_reconcile_blockscout_transaction_reports_mismatches():
    target = {
        "token": _token(1),
        "verification_type": "launch_transaction",
        "transaction_hash": _tx(1),
        "block_number": 1001,
    }
    result = reconcile_blockscout_transaction(
        target,
        {
            "hash": _tx(2),
            "block": 999,
        },
    )

    assert result["external_match"] is False
    assert result["mismatches"] == ["transaction_hash", "block_number"]


def test_explorer_token_summaries_reconcile_launch_and_dex_roles():
    targets = build_representative_explorer_targets(
        _sample(),
        _market_paths(),
        _priced_paths(),
    )
    rows = [
        reconcile_blockscout_transaction(
            target,
            {
                "hash": target["transaction_hash"],
                "block": target["block_number"],
            },
        )
        for target in targets
    ]
    summaries = build_representative_explorer_token_summaries(
        rows,
        _sample(),
    )

    assert len(summaries) == 10
    assert all(row["verified_launch_transactions"] == 1 for row in summaries)
    assert all(row["verified_dex_swap_transactions"] == 1 for row in summaries)
    assert all(
        row["checkpoint_role_counts"]
        == {"first": 1, "last": 1, "max": 1}
        for row in summaries
    )


def test_explorer_summary_requires_all_transactions_matched():
    targets = build_representative_explorer_targets(
        _sample(),
        _market_paths(),
        _priced_paths(),
    )
    rows = [
        reconcile_blockscout_transaction(
            target,
            {
                "hash": target["transaction_hash"],
                "block": target["block_number"],
            },
        )
        for target in targets
    ]
    summary = summarize_representative_explorer_crosscheck(
        rows,
        _sample(),
    )

    assert summary["tokens"] == 10
    assert summary["verified_transactions"] == 20
    assert summary["verified_launch_transactions"] == 10
    assert summary["verified_dex_swap_transactions"] == 10
    assert summary["tokens_with_verified_dex_swaps"] == 10
    assert summary["checkpoint_role_counts"] == {
        "first": 10,
        "last": 10,
        "max": 10,
    }
    assert summary["all_transactions_matched"] is True


def test_explorer_summary_rejects_failed_transaction():
    targets = build_representative_explorer_targets(
        _sample(),
        _market_paths(),
        _priced_paths(),
    )
    rows = [
        reconcile_blockscout_transaction(
            target,
            {
                "hash": target["transaction_hash"],
                "block": target["block_number"],
            },
        )
        for target in targets
    ]
    rows[0]["external_match"] = False
    rows[0]["mismatches"] = ["block_number"]

    with pytest.raises(ValueError, match="transaction mismatch"):
        summarize_representative_explorer_crosscheck(rows, _sample())
