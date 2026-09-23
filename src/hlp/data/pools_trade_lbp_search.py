"""Validation for pools.trade LBP exact-PoolId initialization searches."""

from __future__ import annotations

from typing import Mapping

from hlp.config import ROBINHOOD_CHAIN_ID, normalize_address
from hlp.protocols.uniswap import v4_pool_id


POOLS_TRADE_LBP_POOL_INIT_SEARCH_VERSION = (
    "phase2-pools-trade-lbp-pool-init-search-v1"
)


def _bytes32(value: object, *, label: str) -> str:
    text = str(value or "").lower()
    if not text.startswith("0x") or len(text) != 66:
        raise ValueError(f"{label} must be bytes32")
    try:
        int(text[2:], 16)
    except ValueError as exc:
        raise ValueError(f"{label} must be bytes32") from exc
    return text


def validate_pools_trade_lbp_pool_init_search(
    report: Mapping[str, object],
    *,
    expected_token: str,
    expected_pool_id: str,
    expected_from_block: int,
    expected_to_block: int,
) -> dict:
    """Validate one merged exact-PoolId search result."""
    version = str(report.get("version") or "")
    if version != POOLS_TRADE_LBP_POOL_INIT_SEARCH_VERSION:
        raise ValueError(
            f"LBP pool-init search version changed: {version!r}"
        )
    if int(report.get("chain_id", -1)) != ROBINHOOD_CHAIN_ID:
        raise ValueError("LBP pool-init search chain changed")

    token = normalize_address(str(report.get("token") or ""))
    if token != normalize_address(expected_token):
        raise ValueError("LBP pool-init search token changed")

    pool_id = _bytes32(
        report.get("pool_id"),
        label="LBP pool-init search PoolId",
    )
    if pool_id != _bytes32(
        expected_pool_id,
        label="expected LBP PoolId",
    ):
        raise ValueError("LBP pool-init search PoolId changed")

    start = int(report.get("search_from_block", -1))
    end = int(report.get("search_to_block", -1))
    if start != int(expected_from_block) or end != int(expected_to_block):
        raise ValueError(
            "LBP pool-init search range changed: "
            f"{start}..{end}"
        )
    if start < 0 or end < start:
        raise ValueError("LBP pool-init search range is invalid")

    if report.get("continuous") is not True:
        raise ValueError("LBP pool-init search is not continuous")
    missing = report.get("missing_ranges")
    if not isinstance(missing, list) or missing:
        raise ValueError("LBP pool-init search has missing ranges")

    shards = int(report.get("shards", 0))
    requests = int(report.get("rpc_requests", 0))
    if shards <= 0 or requests <= 0:
        raise ValueError("LBP pool-init search accounting is invalid")
    routes = report.get("rpc_routes")
    if not isinstance(routes, list) or not routes:
        raise ValueError("LBP pool-init search RPC routes are missing")

    found = report.get("initialize_found")
    if not isinstance(found, bool):
        raise ValueError("LBP pool-init initialize_found must be boolean")
    raw_initialize = report.get("initialize")
    if found and not isinstance(raw_initialize, Mapping):
        raise ValueError("LBP pool-init found flag lacks Initialize row")
    if not found and raw_initialize is not None:
        raise ValueError("LBP pool-init absence contains Initialize row")

    initialize = None
    if found:
        raw = dict(raw_initialize)
        observed_pool_id = _bytes32(
            raw.get("pool_id"),
            label="observed V4 PoolId",
        )
        if observed_pool_id != pool_id:
            raise ValueError("observed V4 PoolId changed")
        currency0 = normalize_address(
            str(raw.get("currency0") or "")
        )
        currency1 = normalize_address(
            str(raw.get("currency1") or "")
        )
        if int(currency0, 16) >= int(currency1, 16):
            raise ValueError("observed V4 currencies are not ordered")
        if token not in {currency0, currency1}:
            raise ValueError("observed V4 pool lacks LBP token")
        fee = int(raw.get("fee", -1))
        spacing = int(raw.get("tick_spacing", 1 << 24))
        hooks = normalize_address(str(raw.get("hooks") or ""))
        derived = v4_pool_id(
            currency0=currency0,
            currency1=currency1,
            fee=fee,
            tick_spacing=spacing,
            hooks=hooks,
        )
        if derived != pool_id:
            raise ValueError("observed V4 PoolKey does not derive PoolId")
        block = int(raw.get("block_number", -1))
        if block < start or block > end:
            raise ValueError("observed V4 Initialize is out of range")
        tx_hash = str(raw.get("transaction_hash") or "").lower()
        if not tx_hash.startswith("0x") or len(tx_hash) != 66:
            raise ValueError("observed V4 Initialize tx hash invalid")
        int(tx_hash[2:], 16)
        initialize = {
            **raw,
            "pool_id": observed_pool_id,
            "currency0": currency0,
            "currency1": currency1,
            "hooks": hooks,
            "fee": fee,
            "tick_spacing": spacing,
            "block_number": block,
            "transaction_hash": tx_hash,
        }

    return {
        "version": version,
        "chain_id": ROBINHOOD_CHAIN_ID,
        "token": token,
        "pool_id": pool_id,
        "search_from_block": start,
        "search_to_block": end,
        "continuous": True,
        "missing_ranges": [],
        "shards": shards,
        "initialize_found": found,
        "initialize": initialize,
        "rpc_requests": requests,
        "rpc_routes": sorted(str(route) for route in routes),
    }
