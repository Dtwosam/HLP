"""Materialize Phase-3 Pons trade coverage from accepted research tapes."""

from __future__ import annotations

import heapq
from pathlib import Path
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase2_pons_research_materializer import (
    PHASE2_PONS_RESEARCH_MATERIALIZATION_VERSION,
)
from hlp.data.phase3_trade_adapters import (
    iter_adapt_pons_trades_to_phase3,
)
from hlp.data.phase3_trade_tape import (
    build_phase3_trade_source_coverage,
)
from hlp.data.pons_trades import iter_normalized_pons_trades
from hlp.data.sharded_tape import iter_validated_jsonl
from hlp.data.snapshot import write_jsonl_snapshot


PHASE3_PONS_TRADE_COVERAGE_VERSION = (
    "phase3-pons-trade-coverage-v1"
)


def _event_key(row: Mapping[str, object]) -> tuple[int, int, int, str]:
    block = int(row.get("block_number", -1))
    raw_tx = row.get("transaction_index")
    tx = -1 if raw_tx is None else int(raw_tx)
    log = int(row.get("log_index", -1))
    token = normalize_address(str(row.get("token") or ""))
    if block < 0 or tx < -1 or log < 0:
        raise ValueError("Pons Phase-3 coverage event position is invalid")
    return block, tx, log, token


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower().removeprefix("sha256:")
    if len(text) != 64:
        raise ValueError(f"{label} SHA-256 is invalid")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} SHA-256 is invalid") from exc
    return text


def _merge_sorted_trade_iterators(
    iterators: Iterable[Iterable[Mapping[str, object]]],
):
    """Merge individually chronological normalized trade streams."""

    heap = []
    active = {}
    serial = 0

    def push(index: int) -> None:
        nonlocal serial
        iterator = active[index]
        try:
            row = dict(next(iterator))
        except StopIteration:
            return
        heapq.heappush(
            heap,
            (_event_key(row), serial, index, row),
        )
        serial += 1

    for index, rows in enumerate(iterators):
        active[index] = iter(rows)
        push(index)

    previous = None
    while heap:
        key, _, index, row = heapq.heappop(heap)
        if previous is not None and key <= previous:
            raise ValueError(
                "Pons Phase-3 normalized trades are not strictly ordered"
            )
        previous = key
        yield row
        push(index)


def _wallet_identity_rows(
    canonical_rows: Iterable[Mapping[str, object]],
):
    previous = None
    for raw in canonical_rows:
        row = dict(raw)
        key = _event_key(row)
        if previous is not None and key <= previous:
            raise ValueError(
                "Pons Phase-3 wallet identities are not strictly ordered"
            )
        previous = key
        yield {
            "source_id": str(row["source_id"]),
            "token": normalize_address(str(row["token"])),
            "transaction_hash": str(row["transaction_hash"]).lower(),
            "initiator": normalize_address(str(row["initiator"])),
            "block_number": key[0],
            "transaction_index": (
                None if key[1] == -1 else key[1]
            ),
            "log_index": key[2],
            "wallet_identity_kind": "source_normalized_initiator",
        }


def materialize_phase3_pons_trade_coverage(
    *,
    source_id: str,
    research_report: Mapping[str, object],
    research_point_files: Iterable[tuple[Path, Path]],
    raw_output: Path,
    canonical_output: Path,
    wallet_identity_output: Path,
    coverage_output: Path,
) -> dict:
    """Convert one accepted Pons research component into Phase-3 coverage."""

    if source_id not in {"pons_v1", "pons_v2"}:
        raise ValueError(f"unsupported Pons source: {source_id}")
    report = dict(research_report)
    if (
        str(report.get("version") or "")
        != PHASE2_PONS_RESEARCH_MATERIALIZATION_VERSION
    ):
        raise ValueError("Pons research report version changed")
    if str(report.get("source_id") or "") != source_id:
        raise ValueError("Pons research report source changed")
    for flag in (
        "eligible_token_coverage_complete",
        "accepted_lifecycle_replay_equivalent",
        "full_inputs_validated",
        "research_component_ready",
    ):
        if report.get(flag) is not True:
            raise ValueError(f"Pons research report lacks {flag}")
    if report.get("outcome_labels_computed") is not False:
        raise ValueError("Pons research report contains outcome labels")

    snapshot = int(report.get("snapshot_head_block", -1))
    if snapshot <= 0:
        raise ValueError("Pons research snapshot is invalid")
    market_registry_sha = _sha256(
        report.get("market_registry_sha256"),
        label=f"{source_id} market registry",
    )
    universe_sha = _sha256(
        report.get("eligible_universe_sha256"),
        label=f"{source_id} eligible universe",
    )

    point_specs = list(research_point_files)
    if not point_specs:
        raise ValueError("Pons research point set is empty")
    expected_point_files = 1 if source_id == "pons_v1" else 3
    if len(point_specs) != expected_point_files:
        raise ValueError(
            f"{source_id} research point file count changed"
        )

    point_records = 0
    eligible_tokens = set()
    for path, manifest_path in point_specs:
        rows = 0
        for raw in iter_validated_jsonl(path, manifest_path):
            row = dict(raw)
            token = normalize_address(str(row.get("token") or ""))
            eligible_tokens.add(token)
            if int(row.get("block_number", -1)) > snapshot:
                raise ValueError(
                    f"{source_id} research point is after snapshot"
                )
            rows += 1
        point_records += rows

    if point_records != int(report.get("materialized_records", -1)):
        raise ValueError(
            f"{source_id} research materialized-record count drift"
        )
    if len(eligible_tokens) != int(report.get("eligible_tokens", -1)):
        raise ValueError(
            f"{source_id} research eligible-token count drift"
        )
    if not eligible_tokens:
        raise ValueError(f"{source_id} has no eligible tokens")

    normalized_streams = []
    for path, manifest_path in point_specs:
        normalized_streams.append(
            iter_normalized_pons_trades(
                iter_validated_jsonl(path, manifest_path)
            )
        )

    raw_manifest = write_jsonl_snapshot(
        _merge_sorted_trade_iterators(normalized_streams),
        output=raw_output,
        provenance={
            "version": PHASE3_PONS_TRADE_COVERAGE_VERSION,
            "source_id": source_id,
            "snapshot_head_block": snapshot,
            "eligible_universe_sha256": universe_sha,
            "market_registry_sha256": market_registry_sha,
            "research_source_binding_sha256": _sha256(
                report.get("source_binding_sha256"),
                label=f"{source_id} research source binding",
            ),
            "historical_event_scan_complete": True,
            "wallet_identity_kind": "source_normalized_initiator",
            "outcome_rows_consumed": False,
            "future_state_allowed": False,
        },
    )

    raw_manifest_path = raw_output.with_suffix(
        raw_output.suffix + ".manifest.json"
    )
    canonical_manifest = write_jsonl_snapshot(
        iter_adapt_pons_trades_to_phase3(
            iter_validated_jsonl(
                raw_output,
                raw_manifest_path,
            )
        ),
        output=canonical_output,
        provenance={
            "version": PHASE3_PONS_TRADE_COVERAGE_VERSION,
            "source_id": source_id,
            "raw_trade_tape_sha256": raw_manifest["sha256"],
            "market_registry_sha256": market_registry_sha,
            "wallet_identity_kind": "source_normalized_initiator",
            "historical_event_scan_complete": True,
            "canonical_trade_adapter_complete": True,
            "outcome_rows_consumed": False,
            "future_state_allowed": False,
        },
    )

    canonical_manifest_path = canonical_output.with_suffix(
        canonical_output.suffix + ".manifest.json"
    )
    wallet_manifest = write_jsonl_snapshot(
        _wallet_identity_rows(
            iter_validated_jsonl(
                canonical_output,
                canonical_manifest_path,
            )
        ),
        output=wallet_identity_output,
        provenance={
            "version": PHASE3_PONS_TRADE_COVERAGE_VERSION,
            "source_id": source_id,
            "wallet_identity_kind": "source_normalized_initiator",
            "canonical_trade_rows_sha256": canonical_manifest["sha256"],
            "wallet_identity_complete": True,
            "outcome_rows_consumed": False,
            "future_state_allowed": False,
        },
    )

    coverage = build_phase3_trade_source_coverage(
        source_id,
        iter_validated_jsonl(
            canonical_output,
            canonical_manifest_path,
        ),
        eligible_tokens=eligible_tokens,
        snapshot_head_block=snapshot,
        market_registry_sha256=market_registry_sha,
        raw_trade_tape_sha256=raw_manifest["sha256"],
        raw_trade_rows=int(raw_manifest["records"]),
        wallet_identity_sha256=wallet_manifest["sha256"],
        wallet_identity_kind="source_normalized_initiator",
        historical_event_scan_complete=True,
        wallet_identity_complete=True,
        canonical_trade_adapter_complete=True,
    )
    if coverage["canonical_trade_rows_sha256"] != (
        canonical_manifest["sha256"]
    ):
        raise ValueError(
            f"{source_id} canonical coverage SHA disagrees with manifest"
        )
    coverage_manifest = write_jsonl_snapshot(
        [coverage],
        output=coverage_output,
        provenance={
            "version": PHASE3_PONS_TRADE_COVERAGE_VERSION,
            "source_id": source_id,
            "snapshot_head_block": snapshot,
            "eligible_universe_sha256": universe_sha,
            "market_registry_sha256": market_registry_sha,
            "raw_trade_tape_sha256": raw_manifest["sha256"],
            "wallet_identity_sha256": wallet_manifest["sha256"],
            "canonical_trade_rows_sha256": canonical_manifest["sha256"],
            "trade_coverage_complete": True,
            "outcome_rows_consumed": False,
            "future_state_allowed": False,
        },
    )

    return {
        "version": PHASE3_PONS_TRADE_COVERAGE_VERSION,
        "source_id": source_id,
        "snapshot_head_block": snapshot,
        "eligible_universe_sha256": universe_sha,
        "market_registry_sha256": market_registry_sha,
        "eligible_tokens": len(eligible_tokens),
        "research_point_rows": point_records,
        "raw_trade_rows": int(raw_manifest["records"]),
        "raw_trade_tape_sha256": raw_manifest["sha256"],
        "wallet_identity_rows": int(wallet_manifest["records"]),
        "wallet_identity_sha256": wallet_manifest["sha256"],
        "wallet_identity_kind": "source_normalized_initiator",
        "canonical_trade_rows": int(canonical_manifest["records"]),
        "canonical_trade_rows_sha256": canonical_manifest["sha256"],
        "coverage_rows_sha256": coverage_manifest["sha256"],
        "historical_event_scan_complete": True,
        "wallet_identity_complete": True,
        "canonical_trade_adapter_complete": True,
        "trade_coverage_complete": True,
        "outcome_rows_consumed": False,
        "future_state_allowed": False,
        "phase3_pons_trade_coverage_ready": True,
    }
