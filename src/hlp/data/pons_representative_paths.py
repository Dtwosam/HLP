"""Artifact-only market-path extraction for representative Pons tokens."""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from hlp.data.reconstruct import event_order


_STAGE_ORDER = {
    "launch": 0,
    "v2_curve": 1,
    "v1_v3": 2,
    "v2_graduation": 3,
    "v2_registration": 4,
    "v2_v4": 5,
}


def _sample_index(sample_rows: Iterable[dict]) -> dict[str, dict]:
    sample: dict[str, dict] = {}
    for source in sample_rows:
        row = dict(source)
        token = str(row["token"]).lower()
        if token in sample:
            raise ValueError(
                f"representative sample contains duplicate token {token}"
            )
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
            "representative market path requires exactly 10 sample tokens"
        )
    return sample


def build_representative_market_path_rows(
    sample_rows: Iterable[dict],
    registry_rows: Iterable[dict],
    *,
    v1_v3_rows: Iterable[dict] = (),
    v2_curve_rows: Iterable[dict] = (),
    graduation_rows: Iterable[dict] = (),
    registration_rows: Iterable[dict] = (),
    v2_v4_rows: Iterable[dict] = (),
) -> list[dict]:
    """Filter frozen full tapes to the exact 10-token representative cohort."""
    sample = _sample_index(sample_rows)

    launches: dict[str, dict] = {}
    for source in registry_rows:
        token = str(source["token"]).lower()
        if token not in sample:
            continue
        if token in launches:
            raise ValueError(
                f"registry contains duplicate representative token {token}"
            )
        row = dict(source)
        version = str(row.get("version"))
        if version != sample[token]["pons_version"]:
            raise ValueError(
                f"representative registry version mismatch for {token}: "
                f"{version} != {sample[token]['pons_version']}"
            )
        row["token"] = token
        launches[token] = row

    missing = sorted(set(sample) - set(launches))
    if missing:
        raise ValueError(
            f"representative launch registry coverage missing: {missing}"
        )

    pool_to_token: dict[str, str] = {}
    curve_to_token: dict[str, str] = {}
    for token, launch in launches.items():
        if sample[token]["pons_version"] == "v1":
            pool = str(launch.get("pool") or "").lower()
            if not pool:
                raise ValueError(
                    f"Pons V1 representative has no launch pool: {token}"
                )
            if pool in pool_to_token:
                raise ValueError(
                    f"representative V1 pool maps to multiple tokens: {pool}"
                )
            pool_to_token[pool] = token
        else:
            curve = str(launch.get("curve") or "").lower()
            if not curve:
                raise ValueError(
                    f"Pons V2 representative has no launch curve: {token}"
                )
            if curve in curve_to_token:
                raise ValueError(
                    f"representative V2 curve maps to multiple tokens: {curve}"
                )
            curve_to_token[curve] = token

    rows: list[dict] = []

    def append(stage: str, source: dict, token: str) -> None:
        row = dict(source)
        observed = row.get("token")
        if observed is not None and str(observed).lower() != token:
            raise ValueError(
                f"{stage} token mismatch: {observed} != {token}"
            )
        block = int(row["block_number"])
        launch_block = int(launches[token]["block_number"])
        if block < launch_block:
            raise ValueError(
                f"{stage} event predates representative launch for {token}"
            )
        row["token"] = token
        row["pons_version"] = sample[token]["pons_version"]
        row["path_stage"] = stage
        rows.append(row)

    for token, launch in launches.items():
        append("launch", launch, token)

    for source in v1_v3_rows:
        pool = str(source["pool"]).lower()
        token = pool_to_token.get(pool)
        if token is not None:
            append("v1_v3", source, token)

    for source in v2_curve_rows:
        curve = str(source["curve"]).lower()
        token = curve_to_token.get(curve)
        if token is not None:
            append("v2_curve", source, token)

    registered_pool_to_token: dict[str, str] = {}
    for source in graduation_rows:
        token = str(source["token"]).lower()
        if token in sample:
            if sample[token]["pons_version"] != "v2":
                raise ValueError(
                    f"V1 representative appears in V2 graduation: {token}"
                )
            append("v2_graduation", source, token)

    for source in registration_rows:
        token = str(source["token"]).lower()
        if token not in sample:
            continue
        if sample[token]["pons_version"] != "v2":
            raise ValueError(
                f"V1 representative appears in V2 registration: {token}"
            )
        pool_id = str(source["pool_id"]).lower()
        owner = registered_pool_to_token.get(pool_id)
        if owner is not None and owner != token:
            raise ValueError(
                f"representative V4 pool maps to multiple tokens: {pool_id}"
            )
        registered_pool_to_token[pool_id] = token
        append("v2_registration", source, token)

    for source in v2_v4_rows:
        pool_id = str(source["pool_id"]).lower()
        token = registered_pool_to_token.get(pool_id)
        if token is not None:
            append("v2_v4", source, token)

    rows.sort(
        key=lambda row: (
            event_order(row),
            _STAGE_ORDER[row["path_stage"]],
            row["token"],
        )
    )
    return rows


def summarize_representative_market_paths(
    path_rows: Iterable[dict],
    sample_rows: Iterable[dict],
) -> list[dict]:
    """Return structural path coverage for each representative token."""
    sample = _sample_index(sample_rows)
    grouped: dict[str, list[dict]] = {token: [] for token in sample}
    for source in path_rows:
        row = dict(source)
        token = str(row["token"]).lower()
        if token not in grouped:
            raise ValueError(
                f"market path contains token outside representative sample: {token}"
            )
        grouped[token].append(row)

    output = []
    for token, sample_row in sample.items():
        rows = grouped[token]
        stages = Counter(str(row["path_stage"]) for row in rows)
        if stages.get("launch", 0) != 1:
            raise ValueError(
                f"representative path must contain one launch for {token}"
            )
        version = sample_row["pons_version"]
        if version == "v1" and stages.get("v1_v3", 0) == 0:
            raise ValueError(
                f"Pons V1 representative has no V3 market events: {token}"
            )
        if version == "v2" and stages.get("v2_curve", 0) == 0:
            raise ValueError(
                f"Pons V2 representative has no curve market events: {token}"
            )

        blocks = [int(row["block_number"]) for row in rows]
        output.append(
            {
                "token": token,
                "pons_version": version,
                "sample_group": sample_row.get("sample_group"),
                "launch_block": int(sample_row["launch_block"]),
                "path_rows": len(rows),
                "stage_counts": dict(sorted(stages.items())),
                "first_path_block": min(blocks),
                "last_path_block": max(blocks),
                "graduated": stages.get("v2_graduation", 0) > 0,
                "registered_v4": stages.get("v2_registration", 0) > 0,
                "has_v4_market_events": stages.get("v2_v4", 0) > 0,
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
