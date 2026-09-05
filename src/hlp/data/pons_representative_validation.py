"""Fail-closed Phase 1 validation for the frozen representative Pons cohort."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from typing import Iterable


def _token_index(rows: Iterable[dict], *, label: str) -> dict[str, dict]:
    output: dict[str, dict] = {}
    for source in rows:
        row = dict(source)
        token = str(row["token"]).lower()
        if token in output:
            raise ValueError(f"{label} contains duplicate token {token}")
        row["token"] = token
        output[token] = row
    return output


def build_representative_validation_rows(
    sample_rows: Iterable[dict],
    *,
    v1_lifecycle_rows: Iterable[dict],
    v2_lifecycle_rows: Iterable[dict],
    holder_summary_rows: Iterable[dict],
    dex_crosscheck_rows: Iterable[dict],
) -> list[dict]:
    """Join the frozen 10-token sample to independent Phase 1 evidence.

    This function does not create new labels or infer missing history. It only
    proves that every sampled token has the already-required launch/lifecycle
    price evidence, complete transfer/holder replay, and an explicit DEX
    reconciliation result.
    """
    sample = [dict(row) for row in sample_rows]
    if len(sample) != 10:
        raise ValueError(
            "representative validation requires exactly 10 sample tokens"
        )

    sample_by_token = _token_index(sample, label="representative sample")
    if len(sample_by_token) != 10:
        raise ValueError("representative sample coverage is not exactly 10")

    groups = Counter(str(row.get("sample_group")) for row in sample)
    if groups != {"runner": 5, "failure": 5}:
        raise ValueError(
            "representative sample must contain five runners and five failures"
        )

    versions = Counter(str(row.get("pons_version")) for row in sample)
    if set(versions) != {"v1", "v2"}:
        raise ValueError(
            "representative sample must contain both Pons generations"
        )

    v1 = _token_index(v1_lifecycle_rows, label="V1 lifecycle")
    v2 = _token_index(v2_lifecycle_rows, label="V2 lifecycle")
    overlap = set(v1) & set(v2)
    if overlap:
        raise ValueError(
            "lifecycle token appears in both Pons generations: "
            f"{sorted(overlap)[:10]}"
        )

    holders = _token_index(
        holder_summary_rows,
        label="representative holder summary",
    )
    if set(holders) != set(sample_by_token):
        missing = sorted(set(sample_by_token) - set(holders))
        extra = sorted(set(holders) - set(sample_by_token))
        raise ValueError(
            "representative holder summary coverage mismatch: "
            f"missing={missing} extra={extra}"
        )

    dex = _token_index(
        dex_crosscheck_rows,
        label="representative DEX cross-check",
    )
    if set(dex) != set(sample_by_token):
        missing = sorted(set(sample_by_token) - set(dex))
        extra = sorted(set(dex) - set(sample_by_token))
        raise ValueError(
            "representative DEX cross-check coverage mismatch: "
            f"missing={missing} extra={extra}"
        )

    output = []
    for token, sample_row in sample_by_token.items():
        version = str(sample_row.get("pons_version"))
        if version not in {"v1", "v2"}:
            raise ValueError(
                f"unsupported representative Pons version for {token}: {version}"
            )
        lifecycle = (v1 if version == "v1" else v2).get(token)
        if lifecycle is None:
            raise ValueError(
                f"representative lifecycle coverage missing for {token}"
            )

        launch_block = int(sample_row["launch_block"])
        if int(lifecycle["launch_block"]) != launch_block:
            raise ValueError(
                f"representative launch block mismatch for {token}: "
                f"sample={launch_block} lifecycle={lifecycle['launch_block']}"
            )

        sample_status = str(sample_row.get("eligibility_status"))
        lifecycle_status = str(lifecycle.get("eligibility_status"))
        if lifecycle_status != sample_status:
            raise ValueError(
                f"representative eligibility mismatch for {token}: "
                f"sample={sample_status} lifecycle={lifecycle_status}"
            )

        price_points = int(lifecycle.get("price_points", 0))
        priced_points = int(lifecycle.get("priced_points", 0))
        unpriced_points = int(lifecycle.get("unpriced_points", 0))
        if price_points < 0 or priced_points < 0 or unpriced_points < 0:
            raise ValueError(
                f"negative lifecycle price-point count for {token}"
            )
        if price_points != priced_points + unpriced_points:
            raise ValueError(
                f"lifecycle price-point accounting mismatch for {token}"
            )
        if priced_points <= 0:
            raise ValueError(
                f"representative token has no priced lifecycle evidence: {token}"
            )

        max_market_cap = lifecycle.get("max_market_cap_proxy_usd")
        if max_market_cap is None or Decimal(str(max_market_cap)) <= 0:
            raise ValueError(
                f"representative token has no positive market-cap evidence: {token}"
            )

        pricing_complete = bool(
            lifecycle.get("pricing_complete", unpriced_points == 0)
        )
        if pricing_complete != (unpriced_points == 0):
            raise ValueError(
                f"lifecycle pricing-completeness mismatch for {token}"
            )
        if lifecycle_status == "ineligible" and not pricing_complete:
            raise ValueError(
                f"ineligible representative token has incomplete pricing: {token}"
            )

        holder = holders[token]
        transfers = int(holder.get("transfers", 0))
        holder_count = int(holder.get("holder_count", -1))
        supply_raw = int(holder.get("accounted_supply_raw", -1))
        holder_last_block = int(holder.get("last_block_number", -1))
        if transfers <= 0:
            raise ValueError(
                f"representative holder history has no transfers for {token}"
            )
        if holder_count < 0 or supply_raw < 0:
            raise ValueError(
                f"representative holder history is invalid for {token}"
            )
        if holder_last_block < launch_block:
            raise ValueError(
                f"representative holder history ends before launch for {token}"
            )

        dex_row = dex[token]
        dex_version = dex_row.get("pons_version")
        if dex_version is not None and str(dex_version) != version:
            raise ValueError(
                f"representative DEX version mismatch for {token}"
            )
        scope = str(dex_row.get("crosscheck_scope"))
        external_match = dex_row.get("external_match")
        mismatches = list(dex_row.get("mismatches") or [])
        if scope == "canonical_dex_pool":
            if external_match is not True or mismatches:
                raise ValueError(
                    f"representative DEX cross-check failed for {token}: "
                    f"mismatches={mismatches}"
                )
        elif scope == "no_registered_v4_pool":
            if version != "v2" or external_match is not None or mismatches:
                raise ValueError(
                    f"invalid no-pool DEX cross-check state for {token}"
                )
        else:
            raise ValueError(
                f"unsupported representative DEX cross-check scope for "
                f"{token}: {scope}"
            )

        output.append(
            {
                "token": token,
                "pons_version": version,
                "sample_group": sample_row["sample_group"],
                "launch_block": launch_block,
                "eligibility_status": lifecycle_status,
                "price_points": price_points,
                "priced_points": priced_points,
                "unpriced_points": unpriced_points,
                "pricing_complete": pricing_complete,
                "max_market_cap_proxy_usd": str(max_market_cap),
                "transfers": transfers,
                "holder_count": holder_count,
                "accounted_supply_raw": supply_raw,
                "holder_last_block_number": holder_last_block,
                "dex_crosscheck_scope": scope,
                "external_match": external_match,
                "validation_status": "complete",
            }
        )

    output.sort(
        key=lambda row: (
            row["sample_group"],
            row["pons_version"],
            row["launch_block"],
            row["token"],
        )
    )
    return output


def summarize_representative_validation(rows: Iterable[dict]) -> dict:
    """Return compact Phase 1 acceptance evidence for a validated cohort."""
    values = [dict(row) for row in rows]
    if len(values) != 10:
        raise ValueError(
            "representative validation must contain exactly 10 tokens"
        )
    tokens = [str(row["token"]).lower() for row in values]
    if len(tokens) != len(set(tokens)):
        raise ValueError("representative validation contains duplicate tokens")
    if any(row.get("validation_status") != "complete" for row in values):
        raise ValueError("representative validation contains incomplete rows")

    scopes = Counter(str(row["dex_crosscheck_scope"]) for row in values)
    return {
        "tokens": len(values),
        "sample_groups": dict(
            sorted(Counter(str(row["sample_group"]) for row in values).items())
        ),
        "pons_versions": dict(
            sorted(Counter(str(row["pons_version"]) for row in values).items())
        ),
        "price_points": sum(int(row["price_points"]) for row in values),
        "priced_points": sum(int(row["priced_points"]) for row in values),
        "unpriced_points": sum(int(row["unpriced_points"]) for row in values),
        "transfers": sum(int(row["transfers"]) for row in values),
        "final_holders": sum(int(row["holder_count"]) for row in values),
        "dex_targeted": scopes.get("canonical_dex_pool", 0),
        "dex_matched": sum(row.get("external_match") is True for row in values),
        "no_registered_v4_pool": scopes.get("no_registered_v4_pool", 0),
        "complete_tokens": sum(
            row.get("validation_status") == "complete" for row in values
        ),
    }
