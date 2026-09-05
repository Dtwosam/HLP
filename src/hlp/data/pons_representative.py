"""Deterministic representative cohort selection for Phase 1 validation."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable


def _balanced_take(
    rows: list[dict],
    count: int,
    *,
    sort_key,
) -> list[dict]:
    if count < 0:
        raise ValueError("representative sample counts cannot be negative")
    if count == 0:
        return []

    ordered = sorted(rows, key=sort_key)
    if len(ordered) < count:
        raise ValueError(
            f"not enough representative candidates: need={count} "
            f"available={len(ordered)}"
        )

    selected: list[dict] = []
    selected_tokens: set[str] = set()
    by_version = {
        version: [row for row in ordered if row["pons_version"] == version]
        for version in ("v1", "v2")
    }

    # When both generations are represented, reserve one slot for each before
    # filling the remainder by the deterministic global ranking.
    if count >= 2 and all(by_version.values()):
        for version in ("v1", "v2"):
            row = by_version[version][0]
            selected.append(row)
            selected_tokens.add(row["token"])

    for row in ordered:
        if len(selected) >= count:
            break
        if row["token"] in selected_tokens:
            continue
        selected.append(row)
        selected_tokens.add(row["token"])

    return selected


def select_representative_pons_tokens(
    v1_lifecycle_rows: Iterable[dict],
    v2_lifecycle_rows: Iterable[dict],
    outcome_rows: Iterable[dict],
    *,
    runner_count: int = 5,
    failure_count: int = 5,
) -> list[dict]:
    """Select a reproducible >=5x-runner / lifecycle-failure validation cohort.

    Runner candidates must be lifecycle-eligible and have at least one
    strictly-later measured market-cap multiple >=5 in the supplied outcome
    tape. Failure candidates are lifecycle-ineligible tokens ranked by their
    maximum observed market cap, which intentionally favors informative
    near-misses over arbitrary dead tokens.
    """
    lifecycle = {}
    for version, rows in (
        ("v1", v1_lifecycle_rows),
        ("v2", v2_lifecycle_rows),
    ):
        for source in rows:
            row = dict(source)
            token = row["token"].lower()
            if token in lifecycle:
                raise ValueError(
                    f"representative lifecycle token appears twice: {token}"
                )
            observed_version = row.get("pons_version") or version
            if observed_version != version:
                raise ValueError(
                    f"representative lifecycle version mismatch for {token}"
                )
            row["token"] = token
            row["pons_version"] = version
            lifecycle[token] = row

    runner_multiple: dict[str, Decimal] = {}
    for source in outcome_rows:
        token = source["token"].lower()
        lifecycle_row = lifecycle.get(token)
        if lifecycle_row is None:
            raise ValueError(
                f"representative outcome token absent from lifecycle: {token}"
            )
        value = source.get("max_future_multiple")
        if value is None:
            continue
        multiple = Decimal(str(value))
        if multiple < 0:
            raise ValueError(
                f"negative future multiple for representative token {token}"
            )
        if multiple >= Decimal("5"):
            prior = runner_multiple.get(token)
            if prior is None or multiple > prior:
                runner_multiple[token] = multiple

    runners = []
    for token, multiple in runner_multiple.items():
        row = lifecycle[token]
        if row.get("eligibility_status") != "eligible":
            raise ValueError(
                f">=5x runner is not lifecycle-eligible: {token}"
            )
        runners.append(
            {
                "token": token,
                "pons_version": row["pons_version"],
                "launch_block": int(row["launch_block"]),
                "sample_group": "runner",
                "selection_metric": "max_future_multiple",
                "selection_value": str(multiple),
                "eligibility_status": "eligible",
            }
        )

    failures = []
    for token, row in lifecycle.items():
        if row.get("eligibility_status") != "ineligible":
            continue
        max_market_cap = row.get("max_market_cap_proxy_usd")
        if max_market_cap is None:
            value = Decimal(0)
        else:
            value = Decimal(str(max_market_cap))
            if value < 0:
                raise ValueError(
                    f"negative max market cap for representative token {token}"
                )
        failures.append(
            {
                "token": token,
                "pons_version": row["pons_version"],
                "launch_block": int(row["launch_block"]),
                "sample_group": "failure",
                "selection_metric": "max_market_cap_proxy_usd",
                "selection_value": str(value),
                "eligibility_status": "ineligible",
            }
        )

    selected_runners = _balanced_take(
        runners,
        runner_count,
        sort_key=lambda row: (
            -Decimal(row["selection_value"]),
            int(row["launch_block"]),
            row["token"],
        ),
    )
    selected_failures = _balanced_take(
        failures,
        failure_count,
        sort_key=lambda row: (
            -Decimal(row["selection_value"]),
            int(row["launch_block"]),
            row["token"],
        ),
    )

    output = []
    for group, selected in (
        ("runner", selected_runners),
        ("failure", selected_failures),
    ):
        for index, row in enumerate(selected):
            out = dict(row)
            out["sample_index"] = index
            out["sample_group"] = group
            output.append(out)

    tokens = [row["token"] for row in output]
    if len(tokens) != len(set(tokens)):
        raise ValueError("representative runner/failure groups overlap")
    return output
