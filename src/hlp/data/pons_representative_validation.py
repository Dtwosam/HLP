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
    market_path_summary_rows: Iterable[dict],
    priced_path_summary_rows: Iterable[dict],
) -> list[dict]:
    """Join the frozen 10-token sample to independent Phase 1 evidence.

    This function does not create new labels or infer missing history. It only
    proves that every sampled token has the already-required launch/lifecycle
    price evidence, a frozen detailed market path plus per-event USD replay,
    complete transfer/holder replay, and an explicit DEX reconciliation result.
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

    market_paths = _token_index(
        market_path_summary_rows,
        label="representative market-path summary",
    )
    if set(market_paths) != set(sample_by_token):
        missing = sorted(set(sample_by_token) - set(market_paths))
        extra = sorted(set(market_paths) - set(sample_by_token))
        raise ValueError(
            "representative market-path summary coverage mismatch: "
            f"missing={missing} extra={extra}"
        )

    priced_paths = _token_index(
        priced_path_summary_rows,
        label="representative priced-path summary",
    )
    if set(priced_paths) != set(sample_by_token):
        missing = sorted(set(sample_by_token) - set(priced_paths))
        extra = sorted(set(priced_paths) - set(sample_by_token))
        raise ValueError(
            "representative priced-path summary coverage mismatch: "
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

        priced_path = priced_paths[token]
        if str(priced_path.get("pons_version")) != version:
            raise ValueError(
                f"representative priced-path version mismatch for {token}"
            )
        if str(priced_path.get("sample_group")) != str(
            sample_row.get("sample_group")
        ):
            raise ValueError(
                f"representative priced-path sample-group mismatch for {token}"
            )
        if int(priced_path.get("launch_block", -1)) != launch_block:
            raise ValueError(
                f"representative priced-path launch mismatch for {token}"
            )
        detailed_price_points = int(priced_path.get("price_points", -1))
        detailed_priced_points = int(priced_path.get("priced_points", -1))
        detailed_unpriced_points = int(priced_path.get("unpriced_points", -1))
        if (
            detailed_price_points != price_points
            or detailed_priced_points != priced_points
            or detailed_unpriced_points != unpriced_points
        ):
            raise ValueError(
                f"representative detailed price-point accounting mismatch "
                f"for {token}: lifecycle=({price_points},{priced_points},"
                f"{unpriced_points}) detailed=({detailed_price_points},"
                f"{detailed_priced_points},{detailed_unpriced_points})"
            )
        detailed_max = priced_path.get("max_market_cap_proxy_usd")
        if detailed_max is None or Decimal(str(detailed_max)) != Decimal(
            str(max_market_cap)
        ):
            raise ValueError(
                f"representative detailed max market cap mismatch for {token}"
            )
        lifecycle_max_block = lifecycle.get("max_market_cap_block")
        if lifecycle_max_block is not None and int(
            priced_path.get("max_market_cap_block", -1)
        ) != int(lifecycle_max_block):
            raise ValueError(
                f"representative detailed max block mismatch for {token}"
            )

        pricing_complete = bool(
            lifecycle.get("pricing_complete", unpriced_points == 0)
        )
        if pricing_complete != (unpriced_points == 0):
            raise ValueError(
                f"lifecycle pricing-completeness mismatch for {token}"
            )
        if bool(priced_path.get("pricing_complete")) != pricing_complete:
            raise ValueError(
                f"representative detailed pricing-completeness mismatch for "
                f"{token}"
            )
        if lifecycle_status == "ineligible" and not pricing_complete:
            raise ValueError(
                f"ineligible representative token has incomplete pricing: {token}"
            )

        market_path = market_paths[token]
        if str(market_path.get("pons_version")) != version:
            raise ValueError(
                f"representative market-path version mismatch for {token}"
            )
        if str(market_path.get("sample_group")) != str(
            sample_row.get("sample_group")
        ):
            raise ValueError(
                f"representative market-path sample-group mismatch for {token}"
            )
        if int(market_path.get("launch_block", -1)) != launch_block:
            raise ValueError(
                f"representative market-path launch mismatch for {token}"
            )
        path_rows = int(market_path.get("path_rows", 0))
        first_path_block = int(market_path.get("first_path_block", -1))
        last_path_block = int(market_path.get("last_path_block", -1))
        stage_counts = dict(market_path.get("stage_counts") or {})
        if path_rows <= 1:
            raise ValueError(
                f"representative market path has no market events for {token}"
            )
        if int(stage_counts.get("launch", 0)) != 1:
            raise ValueError(
                f"representative market path launch count is invalid for {token}"
            )
        if first_path_block != launch_block or last_path_block < launch_block:
            raise ValueError(
                f"representative market-path block coverage is invalid for {token}"
            )
        if version == "v1":
            if int(stage_counts.get("v1_v3", 0)) <= 0:
                raise ValueError(
                    f"Pons V1 representative market path has no V3 events: {token}"
                )
        elif int(stage_counts.get("v2_curve", 0)) <= 0:
            raise ValueError(
                f"Pons V2 representative market path has no curve events: {token}"
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
        price_scope = str(dex_row.get("price_crosscheck_scope"))
        price_match = dex_row.get("price_match")
        price_status = str(dex_row.get("price_crosscheck_status"))
        price_checkpoints = list(dex_row.get("price_checkpoints") or [])
        checkpoint_roles = Counter(
            role
            for checkpoint in price_checkpoints
            for role in list(checkpoint.get("checkpoint_roles") or [])
        )
        registered_v4 = bool(market_path.get("registered_v4"))
        has_v4_market_events = bool(
            market_path.get("has_v4_market_events")
        )
        if version == "v1":
            if registered_v4 or has_v4_market_events:
                raise ValueError(
                    f"Pons V1 representative has impossible V4 path state: {token}"
                )
        elif registered_v4 and not has_v4_market_events:
            raise ValueError(
                f"registered V2 representative has no V4 market events: {token}"
            )
        if scope == "canonical_dex_pool":
            if version == "v2" and not registered_v4:
                raise ValueError(
                    f"V2 representative DEX pool lacks path registration: {token}"
                )
            if external_match is not True or mismatches:
                raise ValueError(
                    f"representative DEX cross-check failed for {token}: "
                    f"mismatches={mismatches}"
                )
            if price_scope == "canonical_dex_swap":
                if price_match is not True or price_status != "matched":
                    raise ValueError(
                        f"representative DEX price cross-check failed for "
                        f"{token}: status={price_status}"
                    )
                if not price_checkpoints:
                    raise ValueError(
                        f"representative DEX price checkpoints missing for "
                        f"{token}"
                    )
                if checkpoint_roles != {
                    "first": 1,
                    "max": 1,
                    "last": 1,
                }:
                    raise ValueError(
                        f"representative DEX checkpoint roles invalid for "
                        f"{token}: {dict(checkpoint_roles)}"
                    )
                bad_checkpoints = [
                    checkpoint
                    for checkpoint in price_checkpoints
                    if (
                        checkpoint.get("price_match") is not True
                        or checkpoint.get("price_crosscheck_status")
                        != "matched"
                    )
                ]
                if bad_checkpoints:
                    raise ValueError(
                        f"representative DEX checkpoint mismatch for "
                        f"{token}"
                    )
            elif price_scope == "no_swap_checkpoint":
                if price_match is not None or price_checkpoints:
                    raise ValueError(
                        f"invalid no-swap DEX price state for {token}"
                    )
            else:
                raise ValueError(
                    f"unsupported representative DEX price scope for "
                    f"{token}: {price_scope}"
                )
        elif scope == "no_registered_v4_pool":
            if registered_v4:
                raise ValueError(
                    f"no-pool DEX state contradicts path registration for {token}"
                )
            if version != "v2" or external_match is not None or mismatches:
                raise ValueError(
                    f"invalid no-pool DEX cross-check state for {token}"
                )
            if (
                price_scope != "not_applicable"
                or price_match is not None
                or price_checkpoints
            ):
                raise ValueError(
                    f"invalid no-pool DEX price state for {token}"
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
                "detailed_price_points": detailed_price_points,
                "detailed_priced_points": detailed_priced_points,
                "detailed_unpriced_points": detailed_unpriced_points,
                "detailed_price_path_complete": pricing_complete,
                "market_path_rows": path_rows,
                "market_path_first_block": first_path_block,
                "market_path_last_block": last_path_block,
                "market_path_stage_counts": stage_counts,
                "market_path_registered_v4": registered_v4,
                "market_path_has_v4_market_events": has_v4_market_events,
                "transfers": transfers,
                "holder_count": holder_count,
                "accounted_supply_raw": supply_raw,
                "holder_last_block_number": holder_last_block,
                "dex_crosscheck_scope": scope,
                "external_match": external_match,
                "dex_price_crosscheck_scope": price_scope,
                "dex_price_match": price_match,
                "dex_price_checkpoint_count": len(price_checkpoints),
                "dex_price_checkpoint_matched": sum(
                    checkpoint.get("price_match") is True
                    for checkpoint in price_checkpoints
                ),
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
        "detailed_price_points": sum(
            int(row["detailed_price_points"]) for row in values
        ),
        "detailed_priced_points": sum(
            int(row["detailed_priced_points"]) for row in values
        ),
        "detailed_unpriced_points": sum(
            int(row["detailed_unpriced_points"]) for row in values
        ),
        "detailed_price_path_complete_tokens": sum(
            bool(row["detailed_price_path_complete"]) for row in values
        ),
        "market_path_rows": sum(
            int(row["market_path_rows"]) for row in values
        ),
        "market_path_registered_v4": sum(
            bool(row["market_path_registered_v4"]) for row in values
        ),
        "market_path_with_v4_events": sum(
            bool(row["market_path_has_v4_market_events"]) for row in values
        ),
        "transfers": sum(int(row["transfers"]) for row in values),
        "final_holders": sum(int(row["holder_count"]) for row in values),
        "dex_targeted": scopes.get("canonical_dex_pool", 0),
        "dex_matched": sum(row.get("external_match") is True for row in values),
        "dex_price_targeted": sum(
            row.get("dex_price_crosscheck_scope") == "canonical_dex_swap"
            for row in values
        ),
        "dex_price_matched": sum(
            row.get("dex_price_match") is True for row in values
        ),
        "dex_price_checkpoints_targeted": sum(
            int(row["dex_price_checkpoint_count"]) for row in values
        ),
        "dex_price_checkpoints_matched": sum(
            int(row["dex_price_checkpoint_matched"]) for row in values
        ),
        "dex_price_multi_checkpoint_tokens": sum(
            int(row["dex_price_checkpoint_count"]) > 1
            for row in values
        ),
        "dex_price_no_swap_checkpoint": sum(
            row.get("dex_price_crosscheck_scope") == "no_swap_checkpoint"
            for row in values
        ),
        "no_registered_v4_pool": scopes.get("no_registered_v4_pool", 0),
        "complete_tokens": sum(
            row.get("validation_status") == "complete" for row in values
        ),
    }
