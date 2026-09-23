from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import shutil
from pathlib import Path
from typing import Iterable, Iterator

from hlp.data.reconstruct import event_order
from hlp.data.snapshot import write_jsonl_snapshot


FIRST_V4_FALLBACK_SWAP = 36_023_158
SNAPSHOT_HEAD = 54_486_035


def validate_full_coverage(
    start: int,
    head: int,
    intervals: Iterable[tuple[int, int]],
) -> list[tuple[int, int]]:
    ordered = sorted(intervals)
    cursor = start
    for lo, hi in ordered:
        if hi < lo:
            raise ValueError(f"invalid V4 range: {(lo, hi)}")
        if hi < cursor:
            continue
        if lo > cursor:
            raise ValueError(f"uncovered V4 range: {cursor}..{lo - 1}")
        cursor = hi + 1
        if cursor > head:
            break
    if cursor <= head:
        raise ValueError(f"uncovered V4 range: {cursor}..{head}")
    return ordered


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_files(source_dirs: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for directory in source_dirs:
        files.extend(directory.glob("v4-quote-events-shard-*.jsonl"))
        files.extend(directory.glob("v4-quote-events-gap-*.jsonl"))
    return sorted(set(files))


def _validated_rows(
    path: Path,
    manifest: dict,
    *,
    pool_ids: set[str],
    activation_by_pool: dict[str, int],
) -> Iterator[dict]:
    expected_records = int(manifest["records"])
    prior = None
    count = 0
    with path.open() as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            order = event_order(row)
            if prior is not None and not prior < order:
                raise ValueError(f"non-increasing V4 source tape: {path.name}")
            prior = order
            if row["event_type"] != "v4_swap":
                raise ValueError(f"unexpected V4 event type in {path.name}")
            pool_id = row["pool_id"].lower()
            if pool_id not in pool_ids:
                raise ValueError(f"unknown V4 pool in {path.name}: {pool_id}")
            block = int(row["block_number"])
            provenance = manifest["provenance"]
            lo = int(provenance["from_block"])
            hi = int(provenance["to_block"])
            if not lo <= block <= hi:
                raise ValueError(f"V4 row outside source range: {path.name}")
            if block < activation_by_pool[pool_id]:
                raise ValueError(f"V4 row predates pool activation: {path.name}")
            count += 1
            yield row
    if count != expected_records:
        raise ValueError(
            f"V4 source record mismatch for {path.name}: {count} != {expected_records}"
        )


def salvage_v4_quote_tape(
    *,
    routes_path: Path,
    source_dirs: Iterable[Path],
    output_dir: Path,
    partial_run_id: int,
    start: int = FIRST_V4_FALLBACK_SWAP,
    head: int = SNAPSHOT_HEAD,
) -> dict:
    routes = [
        json.loads(line)
        for line in routes_path.read_text().splitlines()
        if line.strip()
    ]
    if not routes:
        raise ValueError("frozen V4 quote route selection is empty")
    activation_by_pool = {
        row["pool_id"].lower(): int(row["activation_block"])
        for row in routes
    }
    pool_ids = set(activation_by_pool)

    files = _source_files(source_dirs)
    if not files:
        raise ValueError("no V4 quote artifacts available for salvage")

    sources = []
    iterators = []
    intervals = []
    for path in files:
        manifest_path = path.with_suffix(path.suffix + ".manifest.json")
        manifest = json.loads(manifest_path.read_text())
        if _sha256(path) != manifest["sha256"]:
            raise ValueError(f"V4 source SHA mismatch: {path.name}")
        provenance = manifest["provenance"]
        lo = int(provenance["from_block"])
        hi = int(provenance["to_block"])
        intervals.append((lo, hi))
        sources.append(
            {
                "source": path.parent.name,
                "file": path.name,
                "sha256": manifest["sha256"],
                "records": int(manifest["records"]),
                "from_block": lo,
                "to_block": hi,
            }
        )
        iterators.append(
            _validated_rows(
                path,
                manifest,
                pool_ids=pool_ids,
                activation_by_pool=activation_by_pool,
            )
        )

    validate_full_coverage(start, head, intervals)

    state = {"records": 0, "duplicate_rows": 0}

    def rows() -> Iterator[dict]:
        prior_order = None
        prior_row = None
        for row in heapq.merge(*iterators, key=event_order):
            order = event_order(row)
            if prior_order == order:
                if row != prior_row:
                    raise ValueError(f"conflicting overlapping V4 event: {order}")
                state["duplicate_rows"] += 1
                continue
            if prior_order is not None and not prior_order < order:
                raise ValueError(f"non-increasing salvaged V4 tape: {order}")
            prior_order = order
            prior_row = row
            state["records"] += 1
            yield row

    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "pons-v4-quote-fallback-events-full.jsonl"
    snapshot = write_jsonl_snapshot(
        rows(),
        output=output,
        provenance={
            "source": "paginated_overlap_safe_v4_quote_salvage",
            "chain_id": 4663,
            "snapshot_head_block": head,
            "partial_run_id": partial_run_id,
            "routes": len(routes),
            "sources": sources,
        },
    )

    shutil.copy2(routes_path, output_dir / "pons-v4-quote-routes.jsonl")
    summary_source = routes_path.with_name("pons-v4-quote-route-selection-summary.json")
    if summary_source.exists():
        shutil.copy2(
            summary_source,
            output_dir / "pons-v4-quote-route-selection-summary.json",
        )

    summary = {
        "snapshot_head_block": head,
        "selected_routes": len(routes),
        "records": state["records"],
        "duplicate_rows_removed": state["duplicate_rows"],
        "event_tape_sha256": snapshot["sha256"],
        "source_files": len(files),
    }
    (output_dir / "pons-v4-quote-fallback-events-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--routes", required=True, type=Path)
    parser.add_argument("--source-dir", action="append", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--partial-run-id", required=True, type=int)
    parser.add_argument("--start", type=int, default=FIRST_V4_FALLBACK_SWAP)
    parser.add_argument("--head", type=int, default=SNAPSHOT_HEAD)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    summary = salvage_v4_quote_tape(
        routes_path=args.routes,
        source_dirs=args.source_dir,
        output_dir=args.out_dir,
        partial_run_id=args.partial_run_id,
        start=args.start,
        head=args.head,
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
