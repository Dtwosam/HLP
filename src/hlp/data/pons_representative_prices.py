"""Validation and summaries for representative per-event USD price paths."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from typing import Iterable


_ALLOWED_PHASES = {"v1_v3", "v2_curve", "v2_seed", "v2_v4"}


def _sample_index(sample_rows: Iterable[dict]) -> dict[str, dict]:
    sample = {}
    for source in sample_rows:
        row = dict(source)
        token = str(row["token"]).lower()
        if token in sample:
            raise ValueError(f"duplicate representative token {token}")
        version = str(row.get("pons_version"))
        if version not in {"v1", "v2"}:
            raise ValueError(
                f"unsupported representative Pons version: {version}"
            )
        row["token"] = token
        row["pons_version"] = version
        sample[token] = row
    if len(sample) != 10:
        raise ValueError(
            "representative priced path requires exactly 10 sample tokens"
        )
    return sample


def validate_representative_priced_path_rows(
    rows: Iterable[dict],
    sample_rows: Iterable[dict],
) -> list[dict]:
    """Validate and deterministically order detailed representative price rows."""
    sample = _sample_index(sample_rows)
    output = []
    previous = None

    for source in rows:
        row = dict(source)
        token = str(row["token"]).lower()
        if token not in sample:
            raise ValueError(
                f"priced path contains token outside representative sample: {token}"
            )
        row["token"] = token
        version = str(row.get("pons_version") or sample[token]["pons_version"])
        if version != sample[token]["pons_version"]:
            raise ValueError(
                f"priced path Pons version mismatch for {token}: {version}"
            )
        row["pons_version"] = version

        phase = str(row.get("price_path_phase"))
        if phase not in _ALLOWED_PHASES:
            raise ValueError(
                f"unsupported representative price-path phase: {phase}"
            )
        if version == "v1" and phase != "v1_v3":
            raise ValueError(
                f"Pons V1 representative has non-V3 price phase: {token}"
            )
        if version == "v2" and phase == "v1_v3":
            raise ValueError(
                f"Pons V2 representative has V1 price phase: {token}"
            )

        block = int(row["block_number"])
        launch_block = int(sample[token]["launch_block"])
        if block < launch_block:
            raise ValueError(
                f"priced path event predates representative launch for {token}"
            )
        row["block_number"] = block

        priced = row.get("market_cap_proxy_usd") is not None
        if priced:
            market_cap = Decimal(str(row["market_cap_proxy_usd"]))
            token_price = Decimal(str(row["token_price_usd"]))
            quote_per_token = Decimal(str(row["quote_per_token"]))
            if market_cap <= 0 or token_price <= 0 or quote_per_token <= 0:
                raise ValueError(
                    f"non-positive priced path value for {token}"
                )
        elif row.get("token_price_usd") is not None:
            raise ValueError(
                f"unpriced representative row has token USD price for {token}"
            )

        key = (
            block,
            -1
            if row.get("transaction_index") is None
            else int(row["transaction_index"]),
            int(row["log_index"]),
            phase,
            token,
        )
        if previous is not None and key < previous:
            raise ValueError(
                "representative priced path rows are not chronological"
            )
        previous = key
        output.append(row)

    seen = {row["token"] for row in output}
    missing = sorted(set(sample) - seen)
    if missing:
        raise ValueError(
            f"representative priced path coverage missing: {missing}"
        )
    return output


def summarize_representative_priced_paths(
    rows: Iterable[dict],
    sample_rows: Iterable[dict],
) -> list[dict]:
    """Return one exact detailed-price-path summary per representative token."""
    sample = _sample_index(sample_rows)
    grouped = {token: [] for token in sample}
    for source in rows:
        row = dict(source)
        token = str(row["token"]).lower()
        if token not in grouped:
            raise ValueError(
                f"priced path contains token outside representative sample: {token}"
            )
        grouped[token].append(row)

    output = []
    for token, sample_row in sample.items():
        values = grouped[token]
        if not values:
            raise ValueError(
                f"representative priced path has no rows for {token}"
            )
        phases = Counter(str(row["price_path_phase"]) for row in values)
        statuses = Counter(str(row.get("pricing_status")) for row in values)
        priced = [
            row for row in values
            if row.get("market_cap_proxy_usd") is not None
        ]
        unpriced = len(values) - len(priced)
        if not priced:
            raise ValueError(
                f"representative token has no priced path evidence: {token}"
            )

        max_row = max(
            priced,
            key=lambda row: (
                Decimal(str(row["market_cap_proxy_usd"])),
                int(row["block_number"]),
                -1
                if row.get("transaction_index") is None
                else int(row["transaction_index"]),
                int(row["log_index"]),
            ),
        )
        blocks = [int(row["block_number"]) for row in values]

        version = sample_row["pons_version"]
        if version == "v1" and phases.get("v1_v3", 0) != len(values):
            raise ValueError(
                f"Pons V1 representative price path is not all V3: {token}"
            )
        if version == "v2" and phases.get("v2_curve", 0) == 0:
            raise ValueError(
                f"Pons V2 representative price path has no curve points: {token}"
            )

        output.append(
            {
                "token": token,
                "pons_version": version,
                "sample_group": sample_row.get("sample_group"),
                "launch_block": int(sample_row["launch_block"]),
                "price_points": len(values),
                "priced_points": len(priced),
                "unpriced_points": unpriced,
                "pricing_complete": unpriced == 0,
                "phase_counts": dict(sorted(phases.items())),
                "pricing_status_counts": dict(sorted(statuses.items())),
                "first_price_block": min(blocks),
                "last_price_block": max(blocks),
                "max_market_cap_proxy_usd": str(
                    Decimal(str(max_row["market_cap_proxy_usd"]))
                ),
                "max_market_cap_block": int(max_row["block_number"]),
                "max_market_cap_phase": str(max_row["price_path_phase"]),
            }
        )

    output.sort(
        key=lambda row: (
            row["pons_version"],
            row["launch_block"],
            row["token"],
        )
    )
    return output

def select_representative_dex_price_checkpoints(
    rows: Iterable[dict],
    sample_rows: Iterable[dict],
) -> dict[str, list[dict]]:
    """Select first/max/last priced DEX swaps for each representative token."""
    sample = _sample_index(sample_rows)
    grouped: dict[str, list[dict]] = {token: [] for token in sample}

    for source in rows:
        row = dict(source)
        token = str(row["token"]).lower()
        if token not in sample:
            raise ValueError(
                f"priced path contains token outside representative sample: {token}"
            )
        version = sample[token]["pons_version"]
        phase = str(row.get("price_path_phase"))
        event_type = str(row.get("event_type"))
        is_dex_swap = (
            version == "v1"
            and phase == "v1_v3"
            and event_type == "v3_swap"
        ) or (
            version == "v2"
            and phase == "v2_v4"
            and event_type == "v4_swap"
        )
        if not is_dex_swap or row.get("token_price_usd") is None:
            continue
        price = Decimal(str(row["token_price_usd"]))
        if price <= 0:
            raise ValueError(
                f"representative DEX swap has non-positive USD price: {token}"
            )
        row["token"] = token
        row["pons_version"] = version
        grouped[token].append(row)

    role_order = {"first": 0, "max": 1, "last": 2}
    output: dict[str, list[dict]] = {}
    for token, values in grouped.items():
        values.sort(
            key=lambda row: (
                int(row["block_number"]),
                -1
                if row.get("transaction_index") is None
                else int(row["transaction_index"]),
                int(row["log_index"]),
            )
        )
        if not values:
            output[token] = []
            continue

        maximum = max(
            values,
            key=lambda row: (
                Decimal(str(row["token_price_usd"])),
                int(row["block_number"]),
                -1
                if row.get("transaction_index") is None
                else int(row["transaction_index"]),
                int(row["log_index"]),
            ),
        )
        selected: dict[tuple[int, int, int], dict] = {}
        for role, row in (
            ("first", values[0]),
            ("max", maximum),
            ("last", values[-1]),
        ):
            key = (
                int(row["block_number"]),
                -1
                if row.get("transaction_index") is None
                else int(row["transaction_index"]),
                int(row["log_index"]),
            )
            current = selected.get(key)
            if current is None:
                current = dict(row)
                current["checkpoint_roles"] = []
                selected[key] = current
            current["checkpoint_roles"].append(role)

        checkpoints = list(selected.values())
        for row in checkpoints:
            row["checkpoint_roles"].sort(key=role_order.__getitem__)
        checkpoints.sort(
            key=lambda row: (
                int(row["block_number"]),
                -1
                if row.get("transaction_index") is None
                else int(row["transaction_index"]),
                int(row["log_index"]),
            )
        )
        output[token] = checkpoints

    return output

