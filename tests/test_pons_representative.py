import pytest

from hlp.data.pons_representative import (
    select_representative_pons_tokens,
)


def life(token, version, status, launch, max_mcap):
    return {
        "token": token,
        "pons_version": version,
        "eligibility_status": status,
        "launch_block": launch,
        "max_market_cap_proxy_usd": max_mcap,
    }


def outcome(token, multiple):
    return {
        "token": token,
        "max_future_multiple": multiple,
    }


def test_representative_selector_balances_generations_and_groups():
    v1 = [
        life("0x" + f"{i:040x}", "v1", "eligible", i, "200000")
        for i in range(1, 5)
    ] + [
        life("0x" + f"{i:040x}", "v1", "ineligible", i, str(90000 - i))
        for i in range(101, 106)
    ]
    v2 = [
        life("0x" + f"{i:040x}", "v2", "eligible", i, "300000")
        for i in range(11, 15)
    ] + [
        life("0x" + f"{i:040x}", "v2", "ineligible", i, str(80000 - i))
        for i in range(111, 116)
    ]
    outcomes = [
        outcome(row["token"], str(20 - index))
        for index, row in enumerate(
            [*v1[:4], *v2[:4]]
        )
    ]

    rows = select_representative_pons_tokens(
        v1,
        v2,
        outcomes,
        runner_count=5,
        failure_count=5,
    )
    runners = [row for row in rows if row["sample_group"] == "runner"]
    failures = [row for row in rows if row["sample_group"] == "failure"]

    assert len(runners) == 5
    assert len(failures) == 5
    assert {row["pons_version"] for row in runners} == {"v1", "v2"}
    assert {row["pons_version"] for row in failures} == {"v1", "v2"}
    assert len({row["token"] for row in rows}) == 10
    assert all(row["eligibility_status"] == "eligible" for row in runners)
    assert all(row["eligibility_status"] == "ineligible" for row in failures)


def test_representative_selector_fails_when_runner_evidence_is_insufficient():
    v1 = [life("0x" + "01" * 20, "v1", "eligible", 1, "200000")]
    with pytest.raises(ValueError, match="not enough representative candidates"):
        select_representative_pons_tokens(
            v1,
            [],
            [outcome(v1[0]["token"], "4.99")],
            runner_count=1,
            failure_count=0,
        )


def test_representative_selector_rejects_runner_not_marked_eligible():
    token = "0x" + "11" * 20
    v1 = [life(token, "v1", "ineligible", 1, "90000")]
    with pytest.raises(ValueError, match=">=5x runner is not lifecycle-eligible"):
        select_representative_pons_tokens(
            v1,
            [],
            [outcome(token, "6")],
            runner_count=1,
            failure_count=0,
        )


def test_representative_failures_rank_near_misses_first():
    v1 = [
        life("0x" + "01" * 20, "v1", "ineligible", 1, "50000"),
        life("0x" + "02" * 20, "v1", "ineligible", 2, "99999"),
    ]
    rows = select_representative_pons_tokens(
        v1,
        [],
        [],
        runner_count=0,
        failure_count=1,
    )
    assert rows[0]["token"] == "0x" + "02" * 20
    assert rows[0]["selection_value"] == "99999"
