"""Canonical source selection for recovered WETH/USDG anchor promotion."""

from __future__ import annotations

from collections.abc import Iterable, Mapping


def select_anchor_source_ranges(
    sources: Iterable[Mapping[str, object]],
    *,
    start_block: int,
    snapshot_head_block: int,
    chain_id: int,
    weth: str,
    usdg: str,
    pool: str,
) -> list[dict]:
    """Return one exact continuous source per block range.

    Sources must already normalize raw RPC token/quote_token fields and
    recovered-range weth/usdg fields to weth and usdg.
    Exact duplicate range+SHA evidence is deduplicated deterministically.
    Any conflicting duplicate, overlap, gap or identity drift fails closed.
    """
    start = int(start_block)
    head = int(snapshot_head_block)
    if start <= 0 or head < start:
        raise ValueError(f"invalid anchor promotion range: {start}..{head}")

    expected_weth = weth.lower()
    expected_usdg = usdg.lower()
    expected_pool = pool.lower()

    by_range: dict[tuple[int, int], dict] = {}
    for raw in sources:
        row = dict(raw)
        lo = int(row["from_block"])
        hi = int(row["to_block"])
        if lo <= 0 or hi < lo:
            raise ValueError(f"invalid anchor source range: {lo}..{hi}")
        if int(row.get("chain_id", -1)) != int(chain_id):
            raise ValueError(
                f"anchor source chain mismatch for {lo}..{hi}"
            )
        if str(row.get("weth") or "").lower() != expected_weth:
            raise ValueError(
                f"anchor source WETH mismatch for {lo}..{hi}"
            )
        if str(row.get("usdg") or "").lower() != expected_usdg:
            raise ValueError(
                f"anchor source USDG mismatch for {lo}..{hi}"
            )
        if str(row.get("pool") or "").lower() != expected_pool:
            raise ValueError(
                f"anchor source pool mismatch for {lo}..{hi}"
            )

        sha = str(row.get("sha256") or "")
        if len(sha) != 64:
            raise ValueError(
                f"anchor source SHA is invalid for {lo}..{hi}"
            )
        records = int(row.get("records", -1))
        if records < 0:
            raise ValueError(
                f"anchor source record count is invalid for {lo}..{hi}"
            )

        key = (lo, hi)
        prior = by_range.get(key)
        if prior is not None:
            if prior["sha256"] != sha:
                raise ValueError(
                    "conflicting anchor evidence for exact range "
                    f"{lo}..{hi}: {prior['sha256']} != {sha}"
                )
            if int(prior["records"]) != records:
                raise ValueError(
                    "conflicting anchor record count for exact range "
                    f"{lo}..{hi}: {prior['records']} != {records}"
                )
            prior_ref = (
                str(prior.get("source_run_id") or ""),
                str(prior.get("source_artifact") or ""),
                str(prior.get("path") or ""),
            )
            row_ref = (
                str(row.get("source_run_id") or ""),
                str(row.get("source_artifact") or ""),
                str(row.get("path") or ""),
            )
            if row_ref < prior_ref:
                by_range[key] = row
            continue
        by_range[key] = row

    selected = [by_range[key] for key in sorted(by_range)]
    if not selected:
        raise ValueError("anchor promotion has no source ranges")

    previous_hi = None
    for row in selected:
        lo = int(row["from_block"])
        hi = int(row["to_block"])
        if previous_hi is None:
            if lo != start:
                raise ValueError(
                    f"anchor promotion starts at {lo}, expected {start}"
                )
        elif lo != previous_hi + 1:
            kind = "overlap" if lo <= previous_hi else "gap"
            raise ValueError(
                f"anchor promotion {kind}: {previous_hi} -> {lo}"
            )
        previous_hi = hi

    if previous_hi != head:
        raise ValueError(
            f"anchor promotion ends at {previous_hi}, expected {head}"
        )
    return selected
