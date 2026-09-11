import pytest

from hlp.data.pons_representative_paths import (
    build_representative_market_path_rows,
    summarize_representative_market_paths,
)


def _token(index: int) -> str:
    return "0x" + f"{index:040x}"


def _pool(index: int) -> str:
    return "0x" + f"{100 + index:040x}"


def _pool_id(index: int) -> str:
    return "0x" + f"{1000 + index:064x}"


def _fixtures():
    sample = []
    registry = []
    v1_v3 = []
    v2_curve = []
    graduations = []
    registrations = []
    v2_v4 = []

    for index in range(1, 11):
        token = _token(index)
        version = "v1" if index <= 5 else "v2"
        launch_block = 1000 + index
        sample.append(
            {
                "token": token,
                "pons_version": version,
                "sample_group": "runner" if index % 2 else "failure",
                "launch_block": launch_block,
            }
        )
        launch = {
            "token": token,
            "version": version,
            "block_number": launch_block,
            "transaction_index": 1,
            "log_index": 0,
            "pair_token": _token(90),
        }
        if version == "v1":
            launch["pool"] = _pool(index)
            registry.append(launch)
            v1_v3.append(
                {
                    "pool": _pool(index),
                    "block_number": launch_block + 1,
                    "transaction_index": 2,
                    "log_index": 0,
                    "event_type": "v3_swap",
                }
            )
        else:
            launch["curve"] = _pool(index)
            registry.append(launch)
            v2_curve.append(
                {
                    "curve": _pool(index),
                    "block_number": launch_block + 1,
                    "transaction_index": 2,
                    "log_index": 0,
                    "event_type": "curve_buy",
                }
            )
            if index in {6, 8, 10}:
                graduations.append(
                    {
                        "token": token,
                        "block_number": launch_block + 2,
                        "transaction_index": 3,
                        "log_index": 0,
                    }
                )
                registrations.append(
                    {
                        "token": token,
                        "pool_id": _pool_id(index),
                        "block_number": launch_block + 3,
                        "transaction_index": 4,
                        "log_index": 0,
                    }
                )
                v2_v4.append(
                    {
                        "pool_id": _pool_id(index),
                        "block_number": launch_block + 4,
                        "transaction_index": 5,
                        "log_index": 0,
                        "event_type": "v4_swap",
                    }
                )

    return (
        sample,
        registry,
        v1_v3,
        v2_curve,
        graduations,
        registrations,
        v2_v4,
    )


def test_representative_market_path_filters_full_tapes_and_summarizes():
    (
        sample,
        registry,
        v1_v3,
        v2_curve,
        graduations,
        registrations,
        v2_v4,
    ) = _fixtures()

    # Unrelated full-tape rows must not leak into the representative artifact.
    v1_v3.append(
        {
            "pool": _pool(99),
            "block_number": 2000,
            "transaction_index": 0,
            "log_index": 0,
            "event_type": "v3_swap",
        }
    )
    v2_curve.append(
        {
            "curve": _pool(98),
            "block_number": 2000,
            "transaction_index": 0,
            "log_index": 0,
            "event_type": "curve_buy",
        }
    )

    rows = build_representative_market_path_rows(
        sample,
        registry,
        v1_v3_rows=iter(v1_v3),
        v2_curve_rows=iter(v2_curve),
        graduation_rows=iter(graduations),
        registration_rows=iter(registrations),
        v2_v4_rows=iter(v2_v4),
    )
    summary = summarize_representative_market_paths(rows, sample)

    assert len(summary) == 10
    assert {row["token"] for row in rows} == {
        row["token"] for row in sample
    }
    assert sum(row["stage_counts"].get("launch", 0) for row in summary) == 10
    assert all(
        row["stage_counts"].get("v1_v3", 0) >= 1
        for row in summary
        if row["pons_version"] == "v1"
    )
    assert all(
        row["stage_counts"].get("v2_curve", 0) >= 1
        for row in summary
        if row["pons_version"] == "v2"
    )
    assert sum(row["registered_v4"] for row in summary) == 3
    assert sum(row["has_v4_market_events"] for row in summary) == 3


def test_representative_market_path_rejects_missing_launch():
    fixtures = _fixtures()
    sample, registry = fixtures[0], fixtures[1]

    with pytest.raises(ValueError, match="launch registry coverage missing"):
        build_representative_market_path_rows(
            sample,
            registry[:-1],
        )


def test_representative_market_path_rejects_event_before_launch():
    (
        sample,
        registry,
        v1_v3,
        v2_curve,
        graduations,
        registrations,
        v2_v4,
    ) = _fixtures()
    v1_v3[0]["block_number"] = sample[0]["launch_block"] - 1

    with pytest.raises(ValueError, match="predates representative launch"):
        build_representative_market_path_rows(
            sample,
            registry,
            v1_v3_rows=v1_v3,
            v2_curve_rows=v2_curve,
            graduation_rows=graduations,
            registration_rows=registrations,
            v2_v4_rows=v2_v4,
        )


def test_representative_market_path_summary_requires_market_events():
    fixtures = _fixtures()
    sample, registry = fixtures[0], fixtures[1]
    v2_curve = fixtures[3]
    rows = build_representative_market_path_rows(
        sample,
        registry,
        v1_v3_rows=(),
        v2_curve_rows=v2_curve,
    )

    with pytest.raises(ValueError, match="has no V3 market events"):
        summarize_representative_market_paths(rows, sample)
