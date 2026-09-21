"""Validation for exploratory pools.trade LBP success-sample reports."""

from __future__ import annotations

from typing import Mapping

from hlp.config import ROBINHOOD_CHAIN_ID, normalize_address
from hlp.protocols.uniswap import v4_pool_id


POOLS_TRADE_LBP_SUCCESS_SAMPLE_VERSION = "phase2-lbp-success-sample-v1"


def _bytes32(value: object, *, label: str) -> str:
    text = str(value or "").lower()
    if not text.startswith("0x") or len(text) != 66:
        raise ValueError(f"{label} must be bytes32")
    try:
        int(text[2:], 16)
    except ValueError as exc:
        raise ValueError(f"{label} must be bytes32") from exc
    return text


def validate_pools_trade_lbp_success_sample(
    report: Mapping[str, object],
    *,
    expected_discovery_from: int | None = None,
    expected_discovery_to: int | None = None,
    expected_search_from: int | None = None,
    expected_search_to: int | None = None,
) -> dict:
    """Validate candidate initializer to exact V4 Initialize matches."""
    version = str(report.get("version") or "")
    if version != POOLS_TRADE_LBP_SUCCESS_SAMPLE_VERSION:
        raise ValueError(
            f"LBP success-sample version changed: {version!r}"
        )
    if int(report.get("chain_id", -1)) != ROBINHOOD_CHAIN_ID:
        raise ValueError("LBP success-sample chain changed")

    discovery_from = int(report.get("discovery_from_block", -1))
    discovery_to = int(report.get("discovery_to_block", -1))
    search_from = int(report.get("search_from_block", -1))
    search_to = int(report.get("search_to_block", -1))
    if (
        discovery_from < 0
        or discovery_to < discovery_from
        or search_from < 0
        or search_to < search_from
    ):
        raise ValueError("LBP success-sample range is invalid")

    expected = (
        (expected_discovery_from, discovery_from, "discovery_from"),
        (expected_discovery_to, discovery_to, "discovery_to"),
        (expected_search_from, search_from, "search_from"),
        (expected_search_to, search_to, "search_to"),
    )
    for wanted, observed, label in expected:
        if wanted is not None and int(wanted) != observed:
            raise ValueError(
                f"LBP success-sample {label} changed: "
                f"{observed} != {int(wanted)}"
            )

    if report.get("continuous_search") is not True:
        raise ValueError("LBP success-sample search is not continuous")
    missing = report.get("missing_ranges")
    if not isinstance(missing, list) or missing:
        raise ValueError("LBP success-sample search has missing ranges")

    candidates = int(report.get("candidates", -1))
    successful = int(report.get("successful_candidates", -1))
    requests = int(report.get("search_rpc_requests", 0))
    if candidates < 0 or successful < 0 or successful > candidates:
        raise ValueError("LBP success-sample candidate counts invalid")
    if requests <= 0:
        raise ValueError("LBP success-sample request count invalid")
    matches = report.get("matches")
    if not isinstance(matches, list):
        raise ValueError("LBP success-sample matches must be a list")
    if len(matches) != successful:
        raise ValueError("LBP success-sample match count drift")

    normalized = []
    seen_initializers = set()
    seen_pool_ids = set()
    for raw_match in matches:
        if not isinstance(raw_match, Mapping):
            raise ValueError("LBP success-sample match is not an object")
        candidate_raw = raw_match.get("candidate")
        initialize_raw = raw_match.get("initialize")
        if not isinstance(candidate_raw, Mapping):
            raise ValueError("LBP success-sample candidate missing")
        if not isinstance(initialize_raw, Mapping):
            raise ValueError("LBP success-sample Initialize missing")

        candidate = dict(candidate_raw)
        initializer = normalize_address(
            str(candidate.get("initializer") or "")
        )
        token = normalize_address(str(candidate.get("token") or ""))
        currency = normalize_address(
            str(candidate.get("currency") or "")
        )
        hooks = normalize_address(
            str(candidate.get("pool_hook") or "")
        )
        created = int(
            candidate.get("initializer_created_block", -1)
        )
        if created < discovery_from or created > discovery_to:
            raise ValueError(
                "LBP success-sample initializer outside discovery range"
            )
        if initializer in seen_initializers:
            raise ValueError("LBP success-sample repeats initializer")
        seen_initializers.add(initializer)

        c0, c1 = sorted(
            (token, currency),
            key=lambda value: int(value, 16),
        )
        derived = v4_pool_id(
            currency0=c0,
            currency1=c1,
            fee=int(candidate.get("pool_fee", -1)),
            tick_spacing=int(
                candidate.get("pool_tick_spacing", 1 << 24)
            ),
            hooks=hooks,
        )
        candidate_pool_id = _bytes32(
            candidate.get("derived_pool_id"),
            label="LBP candidate PoolId",
        )
        if derived != candidate_pool_id:
            raise ValueError("LBP candidate PoolKey does not derive PoolId")

        initialize = dict(initialize_raw)
        observed_pool_id = _bytes32(
            initialize.get("pool_id"),
            label="LBP Initialize PoolId",
        )
        if observed_pool_id != candidate_pool_id:
            raise ValueError(
                "LBP candidate/Initialize PoolId mismatch"
            )
        if observed_pool_id in seen_pool_ids:
            raise ValueError("LBP success-sample repeats PoolId")
        seen_pool_ids.add(observed_pool_id)

        init_c0 = normalize_address(
            str(initialize.get("currency0") or "")
        )
        init_c1 = normalize_address(
            str(initialize.get("currency1") or "")
        )
        if (
            init_c0 != c0
            or init_c1 != c1
            or int(initialize.get("fee", -1))
            != int(candidate.get("pool_fee", -2))
            or int(initialize.get("tick_spacing", 1 << 24))
            != int(candidate.get("pool_tick_spacing", -(1 << 24)))
            or normalize_address(
                str(initialize.get("hooks") or "")
            )
            != hooks
        ):
            raise ValueError(
                "LBP candidate PoolKey disagrees with V4 Initialize"
            )
        block = int(initialize.get("block_number", -1))
        if block < search_from or block > search_to:
            raise ValueError(
                "LBP Initialize outside success-search range"
            )
        if block < created:
            raise ValueError(
                "LBP V4 Initialize precedes initializer creation"
            )

        normalized.append({
            "candidate": {
                **candidate,
                "initializer": initializer,
                "token": token,
                "currency": currency,
                "pool_hook": hooks,
                "derived_pool_id": candidate_pool_id,
            },
            "initialize": {
                **initialize,
                "pool_id": observed_pool_id,
                "currency0": init_c0,
                "currency1": init_c1,
                "hooks": hooks,
                "block_number": block,
            },
        })

    return {
        "version": version,
        "chain_id": ROBINHOOD_CHAIN_ID,
        "discovery_from_block": discovery_from,
        "discovery_to_block": discovery_to,
        "search_from_block": search_from,
        "search_to_block": search_to,
        "continuous_search": True,
        "missing_ranges": [],
        "candidates": candidates,
        "successful_candidates": successful,
        "matches": normalized,
        "search_rpc_requests": requests,
    }
