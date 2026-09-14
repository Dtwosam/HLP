"""Fail-closed causal-history backfill for direct USDG Uniswap V4 quotes."""

from __future__ import annotations

from typing import Iterable, Mapping

from eth_utils import keccak

from hlp.config import ROBINHOOD_USDG, UNISWAP_V4_POOL_MANAGER
from hlp.data.quote_v4_routes import (
    _address_topic,
    _record_dict,
    select_v4_quote_routes,
)
from hlp.data.reconstruct import event_order
from hlp.price import v3_v4_quote_per_token
from hlp.protocols.uniswap import (
    V4_INITIALIZE_TOPIC,
    V4_SWAP_TOPIC,
    decode_v4_pool_initialized,
    decode_v4_swap,
)


MAX_CAUSAL_HISTORY_SEGMENT_BLOCKS = 100_000


def _address_word(address: str) -> bytes:
    value = address.lower()
    if not value.startswith("0x") or len(value) != 42:
        raise ValueError(f"invalid EVM address: {address!r}")
    number = int(value[2:], 16)
    return number.to_bytes(32, "big")


def v4_pool_id(
    *,
    currency0: str,
    currency1: str,
    fee: int,
    tick_spacing: int,
    hooks: str,
) -> str:
    """Return the Uniswap V4 PoolId for one exact PoolKey."""
    token0 = currency0.lower()
    token1 = currency1.lower()
    if int(token0, 16) >= int(token1, 16):
        raise ValueError("V4 PoolKey currencies must be strictly ordered")
    fee_value = int(fee)
    if fee_value < 0 or fee_value >= 1 << 24:
        raise ValueError("V4 pool fee must fit uint24")
    spacing = int(tick_spacing)
    if spacing < -(1 << 23) or spacing >= 1 << 23:
        raise ValueError("V4 tick spacing must fit int24")
    spacing_word = spacing if spacing >= 0 else (1 << 256) + spacing
    encoded = b"".join((
        _address_word(token0),
        _address_word(token1),
        fee_value.to_bytes(32, "big"),
        spacing_word.to_bytes(32, "big"),
        _address_word(hooks),
    ))
    return "0x" + keccak(encoded).hex()


def _best_causal_candidate(candidates: Iterable[dict]) -> dict | None:
    ready = [
        row for row in candidates
        if row.get("latest_pre_use_swap") is not None
    ]
    if not ready:
        return None
    return max(
        ready,
        key=lambda row: (
            event_order(row["latest_pre_use_swap"]),
            int(row["latest_pre_use_swap"]["liquidity"]),
            row["pool_id"],
        ),
    )


def _swap_evidence(source: dict, candidate: dict, swap) -> dict:
    initialized = candidate["initialize"]
    token = source["quote_token"].lower()
    token_is_token0 = initialized["currency0"].lower() == token
    quote_per_token = v3_v4_quote_per_token(
        int(swap.sqrt_price_x96),
        token_is_token0=token_is_token0,
        token_decimals=int(source["quote_decimals"]),
        quote_decimals=6,
    )
    if quote_per_token <= 0:
        raise ValueError("causal V4 fallback price is not positive")
    row = _record_dict(swap)
    row.update({
        "quote_per_token": str(quote_per_token),
        "usd_price": str(quote_per_token),
    })
    return row


def validate_v4_usdg_causal_swap_witness(
    rpc,
    quote_row: dict,
    *,
    pool_id: str,
    currency0: str,
    currency1: str,
    fee: int,
    tick_spacing: int,
    hooks: str,
    witness_block: int,
    pool_manager: str = UNISWAP_V4_POOL_MANAGER,
) -> dict:
    """Validate one exact positive pre-use V4 swap and return a causal route.

    This is a positive-witness path, not an exhaustive-history claim.  The
    supplied pool key is cryptographically bound to ``pool_id`` before a
    single-block PoolManager Swap query is accepted as causal evidence.
    """
    source = dict(quote_row)
    token = source["quote_token"].lower()
    usdg = ROBINHOOD_USDG.lower()
    currency0 = currency0.lower()
    currency1 = currency1.lower()
    if {currency0, currency1} != {token, usdg}:
        raise ValueError("causal V4 witness currencies are not quote/USDG")

    candidate_pool = pool_id.lower()
    if not candidate_pool.startswith("0x") or len(candidate_pool) != 66:
        raise ValueError(f"invalid V4 pool id: {pool_id!r}")
    int(candidate_pool[2:], 16)
    computed = v4_pool_id(
        currency0=currency0,
        currency1=currency1,
        fee=int(fee),
        tick_spacing=int(tick_spacing),
        hooks=hooks,
    )
    if computed != candidate_pool:
        raise ValueError(
            "V4 witness pool id does not match pool key: "
            f"expected={candidate_pool} computed={computed}"
        )

    block = int(witness_block)
    first_use = int(source["first_launch_block"])
    if block < 0 or block >= first_use:
        raise ValueError(
            "V4 causal witness block must be before first Pons use: "
            f"witness={block} first_use={first_use}"
        )

    raw_logs = rpc.iter_logs_chunked(
        block,
        block,
        address=pool_manager,
        topics=[V4_SWAP_TOPIC, candidate_pool],
        chunk_size=1,
        min_chunk_size=1,
    )
    positive = []
    for raw in raw_logs:
        swap = decode_v4_swap(raw)
        if swap.pool_id.lower() != candidate_pool:
            raise ValueError("V4 witness Swap pool id mismatch")
        if swap.pool_manager.lower() != pool_manager.lower():
            raise ValueError("V4 witness Swap PoolManager mismatch")
        if int(swap.block_number) != block:
            raise ValueError("V4 witness Swap escaped requested block")
        if int(swap.sqrt_price_x96) <= 0 or int(swap.liquidity) <= 0:
            continue
        positive.append(swap)
    if not positive:
        raise ValueError("V4 causal witness has no positive-liquidity Swap")

    latest = max(
        positive,
        key=lambda swap: (
            int(swap.block_number),
            -1 if swap.transaction_index is None else int(swap.transaction_index),
            int(swap.log_index),
        ),
    )
    candidate = {
        "pool_id": candidate_pool,
        "initialize": {
            "pool_manager": pool_manager.lower(),
            "pool_id": candidate_pool,
            "currency0": currency0,
            "currency1": currency1,
            "fee": int(fee),
            "tick_spacing": int(tick_spacing),
            "hooks": hooks.lower(),
        },
        "latest_pre_use_swap": None,
        "first_post_use_swap": None,
        "swap_count_in_window": len(positive),
    }
    candidate["latest_pre_use_swap"] = _swap_evidence(source, candidate, latest)
    probe = {
        **source,
        "v4_candidates": [candidate],
        "causal_route_ready": True,
        "delayed_route_ready": False,
        "selected_causal_candidate": candidate,
        "selected_delayed_candidate": None,
    }
    routes = select_v4_quote_routes([probe])
    if len(routes) != 1:
        raise ValueError("V4 causal witness did not produce exactly one route")
    route = dict(routes[0])
    route.update({
        "witness_validation": "single_block_positive_v4_swap",
        "witness_block": block,
        "pool_key_verified": True,
    })
    return route


def extend_v4_usdg_causal_history(
    rpc,
    probe_rows: Iterable[dict],
    *,
    lower_bound_by_token: Mapping[str, int],
    segment_blocks: int = MAX_CAUSAL_HISTORY_SEGMENT_BLOCKS,
    chunk_size: int = 2_000,
    min_chunk_size: int = 25,
    pool_manager: str = UNISWAP_V4_POOL_MANAGER,
) -> list[dict]:
    """Advance exact quote/USDG V4 causal discovery by one bounded segment.

    Target rows are named by ``lower_bound_by_token``.  Their complete causal
    interval is scanned chronologically from the supplied hard lower bound
    through ``first_launch_block - 1``.  A delayed route is deliberately
    suppressed until that interval is complete, so interrupted acquisition
    fails closed rather than silently promoting a later pool.
    """
    blocks = int(segment_blocks)
    if blocks <= 0 or blocks > MAX_CAUSAL_HISTORY_SEGMENT_BLOCKS:
        raise ValueError(
            "causal V4 history segment must be between 1 and 100000 blocks"
        )

    bounds = {
        str(token).lower(): int(block)
        for token, block in lower_bound_by_token.items()
    }
    usdg = ROBINHOOD_USDG.lower()
    output = []

    for raw_source in probe_rows:
        source = dict(raw_source)
        token = source["quote_token"].lower()
        if token not in bounds:
            output.append(source)
            continue

        first_use = int(source["first_launch_block"])
        target = first_use - 1
        lower = bounds[token]
        if lower < 0 or lower > target:
            raise ValueError(
                f"invalid causal V4 history bound for {token}: "
                f"{lower}..{target}"
            )

        source["causal_history_required"] = True
        source["causal_history_from_block"] = lower
        source["causal_history_to_block"] = target
        if source.get("causal_history_complete"):
            output.append(source)
            continue

        scanned = source.get("causal_history_scanned_through")
        if scanned is None:
            start = lower
            deferred = source.get("deferred_delayed_candidate")
            if deferred is None:
                deferred = source.get("selected_delayed_candidate")
            source["deferred_delayed_candidate"] = deferred
        else:
            scanned = int(scanned)
            if scanned < lower - 1 or scanned > target:
                raise ValueError(
                    f"invalid causal V4 history checkpoint for {token}: {scanned}"
                )
            start = scanned + 1

        if start > target:
            source["causal_history_complete"] = True
            output.append(source)
            continue
        end = min(target, start + blocks - 1)
        source["causal_history_segment_from_block"] = start
        source["causal_history_segment_to_block"] = end

        candidates = []
        for raw_candidate in source.get("v4_candidates", []):
            candidate = dict(raw_candidate)
            if candidate.get("initialize") is not None:
                candidate["initialize"] = dict(candidate["initialize"])
            candidates.append(candidate)

        currency0, currency1 = sorted(
            (token, usdg),
            key=lambda value: int(value, 16),
        )
        init_logs = rpc.iter_logs_chunked(
            start,
            end,
            address=pool_manager,
            topics=[
                V4_INITIALIZE_TOPIC,
                None,
                _address_topic(currency0),
                _address_topic(currency1),
            ],
            chunk_size=chunk_size,
            min_chunk_size=min_chunk_size,
        )
        new_initializes = []
        for raw in init_logs:
            event = decode_v4_pool_initialized(raw)
            if {
                event.currency0.lower(),
                event.currency1.lower(),
            } != {token, usdg}:
                raise ValueError("causal V4 Initialize currency mismatch")
            if not start <= int(event.block_number) <= end:
                raise ValueError("causal V4 Initialize escaped segment bounds")
            new_initializes.append(_record_dict(event))

        by_pool = {row["pool_id"].lower(): row for row in candidates}
        for initialized in new_initializes:
            pool_id = initialized["pool_id"].lower()
            if pool_id in by_pool:
                continue
            candidate = {
                "pool_id": pool_id,
                "initialize": initialized,
                "latest_pre_use_swap": None,
                "first_post_use_swap": None,
                "swap_count_in_window": 0,
                "causal_history_swap_count": 0,
            }
            candidates.append(candidate)
            by_pool[pool_id] = candidate

        for candidate in candidates:
            initialized = candidate.get("initialize") or {}
            initialize_block = initialized.get("block_number")
            if initialize_block is None:
                raise ValueError("V4 candidate is missing Initialize block")
            scan_from = max(start, int(initialize_block))
            if scan_from > end:
                continue
            swap_logs = rpc.iter_logs_chunked(
                scan_from,
                end,
                address=pool_manager,
                topics=[V4_SWAP_TOPIC, candidate["pool_id"]],
                chunk_size=chunk_size,
                min_chunk_size=min_chunk_size,
            )
            observed = 0
            latest = candidate.get("latest_pre_use_swap")
            for raw in swap_logs:
                swap = decode_v4_swap(raw)
                block_number = int(swap.block_number)
                if not scan_from <= block_number <= end:
                    raise ValueError("causal V4 swap escaped segment bounds")
                if swap.sqrt_price_x96 <= 0 or swap.liquidity <= 0:
                    continue
                if block_number >= first_use:
                    raise ValueError("causal V4 scan observed post-use swap")
                observed += 1
                evidence = _swap_evidence(source, candidate, swap)
                if latest is None or event_order(evidence) > event_order(latest):
                    latest = evidence
            candidate["latest_pre_use_swap"] = latest
            candidate["causal_history_swap_count"] = (
                int(candidate.get("causal_history_swap_count", 0)) + observed
            )

        source["v4_candidates"] = candidates
        source["initialize_events"] = len(candidates)
        source["causal_history_scanned_through"] = end
        complete = end == target
        source["causal_history_complete"] = complete

        best_causal = _best_causal_candidate(candidates)
        if complete:
            source["causal_route_ready"] = best_causal is not None
            source["selected_causal_candidate"] = best_causal
            if best_causal is not None:
                source["delayed_route_ready"] = False
                source["selected_delayed_candidate"] = None
            else:
                delayed = source.get("deferred_delayed_candidate")
                source["delayed_route_ready"] = delayed is not None
                source["selected_delayed_candidate"] = delayed
        else:
            source["causal_route_ready"] = False
            source["selected_causal_candidate"] = None
            source["delayed_route_ready"] = False
            source["selected_delayed_candidate"] = None

        output.append(source)

    output.sort(
        key=lambda row: (row["first_launch_block"], row["quote_token"])
    )
    return output


def select_v4_quote_routes_after_causal_history(
    probe_rows: Iterable[dict],
) -> list[dict]:
    """Select routes only after every required causal-history scan is complete."""
    rows = [dict(row) for row in probe_rows]
    incomplete = [
        row["quote_token"]
        for row in rows
        if row.get("causal_history_required")
        and not row.get("causal_history_complete")
    ]
    if incomplete:
        raise ValueError(
            "V4 causal history is incomplete for: " + ", ".join(sorted(incomplete))
        )
    return select_v4_quote_routes(rows)
