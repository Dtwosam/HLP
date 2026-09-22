"""Phase-3 ERC-20 deployment discovery and transfer-batch planning."""

from __future__ import annotations

from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.rpc import RpcClient


PHASE3_TOKEN_DEPLOYMENT_VERSION = "phase3-token-deployment-boundary-v1"
PHASE3_TRANSFER_BATCH_PLAN_VERSION = "phase3-transfer-batch-plan-v1"


def discover_phase3_token_deployments(
    rpc: RpcClient,
    tokens: Iterable[str],
    *,
    snapshot_head_block: int,
) -> list[dict]:
    """Find and verify each token's first code block at the frozen snapshot."""

    snapshot = int(snapshot_head_block)
    if snapshot <= 0:
        raise ValueError("Phase-3 deployment snapshot is invalid")
    normalized = sorted({
        normalize_address(str(token))
        for token in tokens
    })
    if not normalized:
        raise ValueError("Phase-3 deployment discovery has no tokens")

    output = []
    for token in normalized:
        first = rpc.find_first_code_block(
            token,
            low=0,
            high=snapshot,
        )
        before = (
            "0x"
            if first == 0
            else str(rpc.get_code(token, first - 1))
        )
        at = str(rpc.get_code(token, first))
        if first > 0 and before not in {"0x", "0x0", ""}:
            raise ValueError(
                f"Phase-3 token code exists before boundary: {token}"
            )
        if at in {"0x", "0x0", ""}:
            raise ValueError(
                f"Phase-3 token has no code at boundary: {token}"
            )
        output.append({
            "version": PHASE3_TOKEN_DEPLOYMENT_VERSION,
            "token": token,
            "snapshot_head_block": snapshot,
            "first_code_block": int(first),
            "code_before_empty": True,
            "code_at_boundary_present": True,
            "code_bytes_at_boundary": len(
                at.removeprefix("0x")
            ) // 2,
            "deployment_boundary_verified": True,
            "outcome_rows_consumed": False,
            "future_state_allowed": False,
        })
    return output


def plan_phase3_transfer_batches(
    deployment_rows: Iterable[Mapping[str, object]],
    *,
    snapshot_head_block: int,
    max_tokens_per_batch: int = 25,
) -> list[dict]:
    """Group verified token starts into bounded address-filtered scan jobs."""

    snapshot = int(snapshot_head_block)
    batch_size = int(max_tokens_per_batch)
    if snapshot <= 0:
        raise ValueError("Phase-3 transfer-plan snapshot is invalid")
    if batch_size < 1 or batch_size > 50:
        raise ValueError(
            "Phase-3 transfer-plan batch size must be between 1 and 50"
        )

    rows = []
    seen = set()
    for raw in deployment_rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE3_TOKEN_DEPLOYMENT_VERSION
        ):
            raise ValueError("Phase-3 deployment plan version changed")
        token = normalize_address(str(row.get("token") or ""))
        if token in seen:
            raise ValueError(
                f"Phase-3 deployment plan repeats token: {token}"
            )
        seen.add(token)
        if int(row.get("snapshot_head_block", -1)) != snapshot:
            raise ValueError(
                f"Phase-3 deployment plan snapshot drift: {token}"
            )
        first = int(row.get("first_code_block", -1))
        if first < 0 or first > snapshot:
            raise ValueError(
                f"Phase-3 deployment boundary is invalid: {token}"
            )
        for flag in (
            "code_before_empty",
            "code_at_boundary_present",
            "deployment_boundary_verified",
        ):
            if row.get(flag) is not True:
                raise ValueError(
                    f"Phase-3 deployment boundary lacks {flag}: {token}"
                )
        if row.get("outcome_rows_consumed") is not False:
            raise ValueError(
                f"Phase-3 deployment boundary consumed outcomes: {token}"
            )
        if row.get("future_state_allowed") is not False:
            raise ValueError(
                f"Phase-3 deployment boundary allows future state: {token}"
            )
        rows.append((first, token))

    if not rows:
        raise ValueError("Phase-3 transfer plan has no deployments")
    rows.sort(key=lambda item: (item[0], item[1]))

    output = []
    for offset in range(0, len(rows), batch_size):
        group = rows[offset : offset + batch_size]
        batch_index = offset // batch_size
        output.append({
            "version": PHASE3_TRANSFER_BATCH_PLAN_VERSION,
            "batch_id": f"{batch_index:04d}",
            "tokens": [token for _, token in group],
            "token_count": len(group),
            "from_block": min(first for first, _ in group),
            "to_block": snapshot,
            "first_code_blocks": {
                token: first
                for first, token in group
            },
            "deployment_boundary_verified": True,
            "outcome_rows_consumed": False,
            "future_state_allowed": False,
        })
    return output
