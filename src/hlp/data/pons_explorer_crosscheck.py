"""Independent Blockscout transaction checks for representative evidence."""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, Mapping

from hlp.data.pons_representative_prices import (
    select_representative_dex_price_checkpoints,
)


_TX_RE = re.compile(r"^0x[0-9a-f]{64}$")


def _sample_index(sample_rows: Iterable[dict]) -> dict[str, dict]:
    sample: dict[str, dict] = {}
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
            "representative explorer cross-check requires exactly 10 tokens"
        )
    return sample


def _transaction_hash(row: Mapping[str, object], *, label: str) -> str:
    value = str(row.get("transaction_hash") or "").lower()
    if not _TX_RE.fullmatch(value):
        raise ValueError(f"{label} has invalid transaction hash: {value!r}")
    return value


def build_representative_explorer_targets(
    sample_rows: Iterable[dict],
    market_path_rows: Iterable[dict],
    priced_path_rows: Iterable[dict],
) -> list[dict]:
    """Select one launch and first/max/last DEX transactions per sample token."""
    sample_list = [dict(row) for row in sample_rows]
    sample = _sample_index(sample_list)

    launches: dict[str, dict] = {}
    for source in market_path_rows:
        row = dict(source)
        if str(row.get("path_stage")) != "launch":
            continue
        token = str(row["token"]).lower()
        if token not in sample:
            raise ValueError(
                f"explorer launch outside representative sample: {token}"
            )
        if token in launches:
            raise ValueError(
                f"duplicate representative launch path for {token}"
            )
        launches[token] = row

    missing = sorted(set(sample) - set(launches))
    if missing:
        raise ValueError(
            f"representative explorer launch coverage missing: {missing}"
        )

    checkpoints = select_representative_dex_price_checkpoints(
        priced_path_rows,
        sample_list,
    )
    targets: list[dict] = []
    for token, sample_row in sample.items():
        launch = launches[token]
        launch_block = int(sample_row["launch_block"])
        if int(launch["block_number"]) != launch_block:
            raise ValueError(
                f"representative explorer launch block mismatch for {token}"
            )
        targets.append(
            {
                "token": token,
                "pons_version": sample_row["pons_version"],
                "sample_group": sample_row.get("sample_group"),
                "verification_type": "launch_transaction",
                "checkpoint_roles": ["launch"],
                "transaction_hash": _transaction_hash(
                    launch,
                    label=f"{token} launch",
                ),
                "block_number": launch_block,
                "transaction_index": launch.get("transaction_index"),
                "log_index": int(launch["log_index"]),
            }
        )

        for checkpoint in checkpoints[token]:
            targets.append(
                {
                    "token": token,
                    "pons_version": sample_row["pons_version"],
                    "sample_group": sample_row.get("sample_group"),
                    "verification_type": "dex_swap_transaction",
                    "checkpoint_roles": list(
                        checkpoint["checkpoint_roles"]
                    ),
                    "transaction_hash": _transaction_hash(
                        checkpoint,
                        label=f"{token} DEX checkpoint",
                    ),
                    "block_number": int(checkpoint["block_number"]),
                    "transaction_index": checkpoint.get(
                        "transaction_index"
                    ),
                    "log_index": int(checkpoint["log_index"]),
                    "canonical_price_usd": checkpoint.get(
                        "token_price_usd"
                    ),
                    "canonical_market_cap_proxy_usd": checkpoint.get(
                        "market_cap_proxy_usd"
                    ),
                    "price_path_phase": checkpoint.get(
                        "price_path_phase"
                    ),
                }
            )

    if not 10 <= len(targets) <= 40:
        raise ValueError(
            "representative explorer target count must be between 10 and 40: "
            f"{len(targets)}"
        )
    targets.sort(
        key=lambda row: (
            int(row["block_number"]),
            -1
            if row.get("transaction_index") is None
            else int(row["transaction_index"]),
            int(row["log_index"]),
            row["verification_type"],
            row["token"],
        )
    )
    return targets


def reconcile_blockscout_transaction(
    target: Mapping[str, object],
    external: Mapping[str, object],
) -> dict:
    """Reconcile one canonical transaction target with Blockscout."""
    expected_hash = _transaction_hash(
        target,
        label="canonical explorer target",
    )
    observed_hash = str(external.get("hash") or "").lower()
    mismatches = []
    if observed_hash != expected_hash:
        mismatches.append("transaction_hash")

    observed_block = external.get("block")
    try:
        observed_block_number = (
            None if observed_block is None else int(observed_block)
        )
    except (TypeError, ValueError):
        observed_block_number = None
    expected_block = int(target["block_number"])
    if observed_block_number != expected_block:
        mismatches.append("block_number")

    output = dict(target)
    output.update(
        {
            "explorer": "robinhood_blockscout",
            "explorer_verification_scope": "transaction_identity_and_block",
            "external_transaction_hash": observed_hash or None,
            "external_block_number": observed_block_number,
            "external_timestamp": external.get("timestamp"),
            "external_match": not mismatches,
            "mismatches": mismatches,
        }
    )
    return output


def summarize_representative_explorer_crosscheck(
    rows: Iterable[dict],
    sample_rows: Iterable[dict],
) -> dict:
    """Validate exact representative explorer coverage and return counts."""
    sample = _sample_index(sample_rows)
    values = [dict(row) for row in rows]
    if not values:
        raise ValueError("representative explorer cross-check is empty")
    if len(values) > 40:
        raise ValueError("representative explorer cross-check exceeds 40 rows")

    by_token: dict[str, list[dict]] = {token: [] for token in sample}
    for row in values:
        token = str(row["token"]).lower()
        if token not in by_token:
            raise ValueError(
                f"explorer row outside representative sample: {token}"
            )
        if row.get("external_match") is not True or row.get("mismatches"):
            raise ValueError(
                f"representative explorer transaction mismatch for {token}"
            )
        by_token[token].append(row)

    launch_rows = 0
    dex_rows = 0
    checkpoint_roles = Counter()
    tokens_with_dex = 0
    for token, token_rows in by_token.items():
        launches = [
            row
            for row in token_rows
            if row.get("verification_type") == "launch_transaction"
        ]
        if len(launches) != 1:
            raise ValueError(
                f"representative explorer must have one launch for {token}"
            )
        launch_rows += 1
        dex = [
            row
            for row in token_rows
            if row.get("verification_type") == "dex_swap_transaction"
        ]
        if dex:
            tokens_with_dex += 1
        dex_rows += len(dex)
        roles = Counter(
            role
            for row in dex
            for role in list(row.get("checkpoint_roles") or [])
        )
        if dex and roles != {"first": 1, "max": 1, "last": 1}:
            raise ValueError(
                f"representative explorer DEX roles invalid for {token}: "
                f"{dict(roles)}"
            )
        checkpoint_roles.update(roles)

    return {
        "tokens": len(sample),
        "verified_transactions": len(values),
        "verified_launch_transactions": launch_rows,
        "verified_dex_swap_transactions": dex_rows,
        "tokens_with_verified_dex_swaps": tokens_with_dex,
        "checkpoint_role_counts": dict(sorted(checkpoint_roles.items())),
        "all_transactions_matched": True,
    }
