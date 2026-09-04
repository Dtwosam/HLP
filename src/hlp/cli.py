"""HLP command-line entry point."""

from __future__ import annotations

import argparse
import json
import os
import time
from decimal import Decimal
from dataclasses import asdict
from pathlib import Path

from hlp.config import (
    DEFAULT_RPC_URL,
    SOLIDRPC_PUBLIC_RPC_URL,
    ROBINHOOD_USDG,
    ROBINHOOD_WETH,
    UNISWAP_V3_WETH_USDG_ANCHOR_POOL,
    UNISWAP_V3_FACTORY,
    PONS_V1_FACTORY,
    PONS_V2_FACTORY,
    PONS_V1_DEPLOYMENT_BLOCK,
    PONS_V2_DEPLOYMENT_BLOCK,
    PONS_V2_MEME_HOOK,
    UNISWAP_V4_POOL_MANAGER,
)
from hlp.protocols.uniswap import (
    PONS_V2_POOL_REGISTERED_TOPIC,
    V3_SWAP_TOPIC,
    V4_SWAP_TOPIC,
    decode_pons_v2_pool_registered,
    decode_v3_swap,
    decode_v4_swap,
)
from hlp.data.blockscout import BlockscoutClient
from hlp.data.chainlink_directory import ChainlinkDirectoryClient
from hlp.data.hoodexplorer import HoodExplorerClient
from hlp.data.oracle_registry import resolve_stock_quote_feed_specs
from hlp.data.oracles import reconstruct_chainlink_usd_tapes
from hlp.data.pons_v1 import iter_enriched_v1_launches
from hlp.data.pons_v2 import ZERO_ADDRESS, iter_enriched_v2_launches
from hlp.data.robinhood_assets import RobinhoodAssetsClient
from hlp.data.rpc import RpcClient
from hlp.data.reconstruct import (
    attach_quote_usd_anchor,
    event_order,
    reconstruct_v3_price_points,
    v3_quote_price_at_block,
)
from hlp.data.snapshot import write_jsonl_snapshot
from hlp.data.universe import build_v1_market_cap_points, summarize_v1_market_caps
from hlp.data.transition import summarize_v2_transition_continuity
from hlp.data.v2_curve import (
    build_v2_curve_market_cap_points,
    summarize_v2_curve_market_caps,
)
from hlp.data.v4 import (
    build_v2_graduation_seed_points,
    build_v2_v4_market_cap_points,
)
from hlp.protocols.erc20 import read_erc20_static
from hlp.protocols.pons_state import (
    read_v1_launch_config_state,
    read_v2_launch_config_state,
    read_v2_pair_token_economics_state,
)
from hlp.protocols.pons import (
    V1_LAUNCH_CONFIG_ADDED_TOPIC,
    V1_LAUNCH_CONFIG_UPDATED_TOPIC,
    V1_TOKEN_LAUNCHED_TOPIC,
    V2_CURVE_BUYBACK_LOCKED_TOPIC,
    V2_CURVE_BUY_TOPIC,
    V2_CURVE_SELL_TOPIC,
    V2_LAUNCH_CONFIG_ADDED_TOPIC,
    V2_LAUNCH_CONFIG_UPDATED_TOPIC,
    V2_PAIR_TOKEN_ECONOMICS_UPDATED_TOPIC,
    V2_POOL_GRADUATED_TOPIC,
    V2_TOKEN_LAUNCHED_TOPIC,
    decode_v1_launch,
    decode_v2_curve_buyback,
    decode_v2_curve_trade,
    decode_v2_launch,
    decode_v2_launch_config_event_id,
    decode_v2_pool_graduation,
)


def _rpc(args: argparse.Namespace) -> RpcClient:
    return RpcClient(
        os.environ.get("ROBINHOOD_RPC_URL", args.rpc_url),
        timeout=args.timeout,
        attempts=args.attempts,
        min_interval_seconds=args.min_interval,
    )


def _archive_rpc(args: argparse.Namespace) -> RpcClient:
    """Build the historical RPC without exposing API keys in command lines."""
    url = os.environ.get("ROBINHOOD_ARCHIVE_RPC_URL", SOLIDRPC_PUBLIC_RPC_URL)
    key = os.environ.get("ROBINHOOD_ARCHIVE_RPC_API_KEY")
    headers = {"X-API-Key": key} if key else None
    return RpcClient(
        url,
        timeout=args.timeout,
        attempts=args.attempts,
        min_interval_seconds=args.min_interval,
        extra_headers=headers,
    )


def cmd_network_smoke(args: argparse.Namespace) -> int:
    rpc = _rpc(args)
    rpc.assert_robinhood()
    head = rpc.block_number()
    block = rpc.get_block(head)
    factories = {}
    for name, address in (
        ("pons_v1", PONS_V1_FACTORY),
        ("pons_v2", PONS_V2_FACTORY),
        ("uniswap_v3_factory", UNISWAP_V3_FACTORY),
        ("pons_v2_meme_hook", PONS_V2_MEME_HOOK),
        ("uniswap_v4_pool_manager", UNISWAP_V4_POOL_MANAGER),
    ):
        code = rpc.get_code(address, head)
        factories[name] = {
            "address": address.lower(),
            "has_code": code not in {"0x", "0x0", ""},
            "code_bytes": max(0, (len(code.removeprefix("0x")) // 2)),
        }
        if not factories[name]["has_code"]:
            raise SystemExit(f"{name} factory has no bytecode at head {head}")
    # A deliberately tiny query proves log access without pretending the
    # public RPC is suitable for bulk history.
    bounded_from = max(0, head - 9)
    bounded_logs = rpc.get_logs(
        bounded_from,
        head,
        address=[PONS_V1_FACTORY, PONS_V2_FACTORY],
    )

    print(
        json.dumps(
            {
                "ok": True,
                "chain_id": rpc.chain_id(),
                "head": head,
                "head_hash": block["hash"],
                "head_timestamp": int(block["timestamp"], 16),
                "bounded_log_query": {
                    "from_block": bounded_from,
                    "to_block": head,
                    "logs": len(bounded_logs),
                },
                "factories": factories,
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_hood_smoke(args: argparse.Namespace) -> int:
    hood = HoodExplorerClient(timeout=args.timeout)
    deployments = {}
    for name, address, topic in (
        ("pons_v1", PONS_V1_FACTORY, V1_TOKEN_LAUNCHED_TOPIC),
        ("pons_v2", PONS_V2_FACTORY, V2_TOKEN_LAUNCHED_TOPIC),
    ):
        deployment = hood.contract_deployment(address)
        block = deployment["block_number"]
        code_at = hood.get_code(address, block)
        code_before = "0x" if block == 0 else hood.get_code(address, block - 1)
        if code_at in {"0x", "0x0", ""}:
            raise SystemExit(f"{name}: no code at creation block {block}")
        if block > 0 and code_before not in {"0x", "0x0", ""}:
            raise SystemExit(f"{name}: code unexpectedly exists before creation block")
        first_launch = hood.get_logs_page(
            address=address,
            topic0=topic,
            from_block=block,
            to_block="latest",
            page=1,
            offset=1,
            sort="asc",
        )
        deployments[name] = {
            **deployment,
            "code_bytes": len(code_at.removeprefix("0x")) // 2,
            "first_launch_block": first_launch[0].block_number if first_launch else None,
            "first_launch_tx": first_launch[0].transaction_hash if first_launch else None,
        }
    print(json.dumps({"ok": True, "deployments": deployments}, sort_keys=True))
    return 0


def cmd_contract_creation(args: argparse.Namespace) -> int:
    client = BlockscoutClient(timeout=args.timeout)
    print(json.dumps(client.contract_deployment(args.address), sort_keys=True))
    return 0


def cmd_deployment_block(args: argparse.Namespace) -> int:
    rpc = _rpc(args)
    rpc.assert_robinhood()
    first = rpc.find_first_code_block(args.address, low=args.low, high=args.high)
    before_code = "0x" if first == 0 else rpc.get_code(args.address, first - 1)
    at_code = rpc.get_code(args.address, first)
    block = rpc.get_block(first)
    if first > 0 and before_code not in {"0x", "0x0", ""}:
        raise SystemExit("deployment boundary verification failed: code exists before first block")
    if at_code in {"0x", "0x0", ""}:
        raise SystemExit("deployment boundary verification failed: no code at first block")
    print(
        json.dumps(
            {
                "address": args.address.lower(),
                "first_code_block": first,
                "timestamp": int(block["timestamp"], 16),
                "code_bytes": len(at_code.removeprefix("0x")) // 2,
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_blockscout_pons_sample(args: argparse.Namespace) -> int:
    client = BlockscoutClient(timeout=args.timeout, attempts=args.attempts)
    if args.version == "v1":
        address = PONS_V1_FACTORY
        topic = V1_TOKEN_LAUNCHED_TOPIC
        decoder = decode_v1_launch
    else:
        address = PONS_V2_FACTORY
        topic = V2_TOKEN_LAUNCHED_TOPIC
        decoder = decode_v2_launch

    started = time.monotonic()
    deployment = client.contract_deployment(address)
    head = client.block_number()
    raw_logs = client.iter_indexed_logs_bisect(
        deployment["block_number"],
        head,
        address=address,
        topic0=topic,
        max_records=args.limit,
    )
    launches = (decoder(log) for log in raw_logs)
    output = Path(args.out)
    manifest = write_jsonl_snapshot(
        launches,
        output=output,
        provenance={
            "source": "robinhood_blockscout_indexed_logs",
            "source_url": client.base_url,
            "chain_id": 4663,
            "protocol": "pons",
            "protocol_version": args.version,
            "factory": address.lower(),
            "event_topic0": topic,
            "deployment_block": deployment["block_number"],
            "head_block": head,
            "requested_limit": args.limit,
            "documented_result_cap": 1000,
        },
    )
    print(
        json.dumps(
            {
                **manifest,
                "requests_made": client.requests_made,
                "bytes_received": client.bytes_received,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_hood_pons_sample(args: argparse.Namespace) -> int:
    hood = HoodExplorerClient(timeout=args.timeout)
    if args.version == "v1":
        address = PONS_V1_FACTORY
        topic = V1_TOKEN_LAUNCHED_TOPIC
        decoder = decode_v1_launch
    else:
        address = PONS_V2_FACTORY
        topic = V2_TOKEN_LAUNCHED_TOPIC
        decoder = decode_v2_launch

    started = time.monotonic()
    deployment = hood.contract_deployment(address)
    raw_logs = hood.iter_logs(
        address=address,
        topic0=topic,
        from_block=deployment["block_number"],
        to_block="latest",
        page_size=args.page_size,
        max_records=args.limit,
    )
    launches = (decoder(log) for log in raw_logs)
    output = Path(args.out)
    manifest = write_jsonl_snapshot(
        launches,
        output=output,
        provenance={
            "source": "hoodexplorer",
            "source_url": hood.base_url,
            "chain_id": 4663,
            "protocol": "pons",
            "protocol_version": args.version,
            "factory": address.lower(),
            "event_topic0": topic,
            "deployment_block": deployment["block_number"],
            "requested_limit": args.limit,
            "page_size": args.page_size,
        },
    )
    elapsed = time.monotonic() - started
    result = {
        **manifest,
        "requests_made": hood.requests_made,
        "bytes_received": hood.bytes_received,
        "elapsed_seconds": round(elapsed, 3),
    }
    print(json.dumps(result, sort_keys=True))
    return 0









def cmd_rpc_v2_stock_oracle_window(args: argparse.Namespace) -> int:
    """Build official Stock Token/USD initial states and shared update tape."""
    registry = _load_jsonl(args.registry)
    assets = RobinhoodAssetsClient(timeout=args.timeout, attempts=args.attempts)
    directory = ChainlinkDirectoryClient(
        timeout=args.timeout,
        attempts=args.attempts,
    )
    started = time.monotonic()
    specs = resolve_stock_quote_feed_specs(
        registry,
        assets_client=assets,
        directory_client=directory,
    )

    feed_manifest = write_jsonl_snapshot(
        specs,
        output=Path(args.feed_out),
        provenance={
            "source": "robinhood_rhj_assets_plus_chainlink_directory",
            "chain_id": 4663,
            "robinhood_assets_url": assets.url,
            "chainlink_directory_url": directory.url,
            "chainlink_directory_sha256": directory.last_sha256,
            "robinhood_asset_requests": assets.requests_made,
            "chainlink_directory_requests": directory.requests_made,
        },
    )

    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    states, updates = reconstruct_chainlink_usd_tapes(
        rpc,
        feeds=specs,
        from_block=args.from_block,
        to_block=args.to_block,
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )
    state_manifest = write_jsonl_snapshot(
        states,
        output=Path(args.state_out),
        provenance={
            "source": "chainlink_aggregator_v3_historical_state",
            "chain_id": 4663,
            "feed_registry_sha256": feed_manifest["sha256"],
            "state_block": args.from_block - 1,
        },
    )
    update_manifest = write_jsonl_snapshot(
        updates,
        output=Path(args.out),
        provenance={
            "source": "chainlink_answer_updated_shared_tape",
            "chain_id": 4663,
            "feed_registry_sha256": feed_manifest["sha256"],
            "from_block": args.from_block,
            "to_block": args.to_block,
            "event_topic0": "0x0559884fd3a460db3073b7fc896cc77986f16e378210ded43186175bf646fc5f",
            "initial_chunk_size": args.chunk_size,
            "min_chunk_size": args.min_chunk_size,
        },
    )
    print(
        json.dumps(
            {
                "feed_registry": feed_manifest,
                "initial_states": state_manifest,
                "updates": update_manifest,
                "stock_quote_assets": len(specs),
                "symbols": [row["symbol"] for row in specs],
                "rhj_requests": assets.requests_made,
                "rhj_bytes": assets.bytes_received,
                "chainlink_directory_requests": directory.requests_made,
                "chainlink_directory_bytes": directory.bytes_received,
                "archive_rpc_requests": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_rpc_v2_v4_market_cap_window(args: argparse.Namespace) -> int:
    """Reconstruct V2 graduation seed/V4 prices and lifecycle continuity."""
    if args.from_block <= 0:
        raise SystemExit("from-block must be > 0")

    registry = _load_jsonl(args.registry)
    graduations = _load_jsonl(args.graduations)
    registrations = _load_jsonl(args.registrations)
    v4_swaps = _load_jsonl(args.v4_swaps)
    curve_points = _load_jsonl(args.curve_points)
    initial_quote_usd, quote_usd_updates = _load_quote_oracle_inputs(args)

    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    started = time.monotonic()

    initial_weth_usd = v3_quote_price_at_block(
        rpc,
        token=ROBINHOOD_WETH,
        quote_token=ROBINHOOD_USDG,
        pool=args.usd_anchor_pool,
        block=args.from_block - 1,
    )
    anchor_points = list(
        reconstruct_v3_price_points(
            rpc,
            token=ROBINHOOD_WETH,
            quote_token=ROBINHOOD_USDG,
            pool=args.usd_anchor_pool,
            from_block=args.from_block,
            to_block=args.to_block,
            chunk_size=args.chunk_size,
            min_chunk_size=args.min_chunk_size,
        )
    )

    seed_points = list(
        build_v2_graduation_seed_points(
            registry,
            graduations,
            anchor_points,
            initial_weth_usd=initial_weth_usd,
            initial_quote_usd=initial_quote_usd,
            quote_usd_updates=quote_usd_updates,
        )
    )
    v4_points = list(
        build_v2_v4_market_cap_points(
            registry,
            registrations,
            v4_swaps,
            anchor_points,
            initial_weth_usd=initial_weth_usd,
            initial_quote_usd=initial_quote_usd,
            quote_usd_updates=quote_usd_updates,
        )
    )

    seed_manifest = write_jsonl_snapshot(
        seed_points,
        output=Path(args.seed_out),
        provenance={
            "source": "derived_v2_pool_graduated",
            "chain_id": 4663,
            "registry": Path(args.registry).name,
            "graduations": Path(args.graduations).name,
            "usd_anchor_pool": args.usd_anchor_pool.lower(),
            "from_block": args.from_block,
            "to_block": args.to_block,
        },
    )
    v4_manifest = write_jsonl_snapshot(
        v4_points,
        output=Path(args.out),
        provenance={
            "source": "derived_v2_v4_swaps",
            "chain_id": 4663,
            "registry": Path(args.registry).name,
            "registrations": Path(args.registrations).name,
            "v4_swaps": Path(args.v4_swaps).name,
            "usd_anchor_pool": args.usd_anchor_pool.lower(),
            "from_block": args.from_block,
            "to_block": args.to_block,
        },
    )

    transition_rows = summarize_v2_transition_continuity(
        curve_points,
        seed_points,
        v4_points,
    )
    transition_manifest = write_jsonl_snapshot(
        transition_rows,
        output=Path(args.transition_out),
        provenance={
            "source": "derived_v2_curve_to_v4_continuity",
            "curve_points": Path(args.curve_points).name,
            "seed_points_sha256": seed_manifest["sha256"],
            "v4_points_sha256": v4_manifest["sha256"],
        },
    )

    lifecycle_points = [*curve_points, *seed_points, *v4_points]
    lifecycle_points.sort(key=event_order)
    summary = summarize_v2_curve_market_caps(lifecycle_points)
    summary_manifest = write_jsonl_snapshot(
        summary,
        output=Path(args.summary_out),
        provenance={
            "source": "derived_v2_full_lifecycle_market_cap_points",
            "curve_points": Path(args.curve_points).name,
            "seed_points_sha256": seed_manifest["sha256"],
            "v4_points_sha256": v4_manifest["sha256"],
            "eligibility_threshold_usd": "100000",
            "threshold_semantics": "reached at least once on curve, V4 seed, or V4 swap path",
        },
    )

    priced_transitions = [
        row
        for row in transition_rows
        if row["curve_to_seed_bps"] is not None
    ]
    first_v4_transitions = [
        row
        for row in transition_rows
        if row["seed_to_first_v4_bps"] is not None
    ]

    print(
        json.dumps(
            {
                "seed_points": seed_manifest,
                "v4_points": v4_manifest,
                "transition_report": transition_manifest,
                "token_summary": summary_manifest,
                "graduations": len(graduations),
                "registrations": len(registrations),
                "v4_swaps": len(v4_swaps),
                "curve_to_seed_comparisons": len(priced_transitions),
                "seed_to_first_v4_comparisons": len(first_v4_transitions),
                "tokens_crossed_100k_full_lifecycle": sum(
                    bool(row["crossed_100k"]) for row in summary
                ),
                "requests_made": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_rpc_v2_graduation_tape(args: argparse.Namespace) -> int:
    registry = _load_jsonl(args.registry)
    tokens = {row["token"].lower() for row in registry}
    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    started = time.monotonic()
    raw = rpc.iter_logs_chunked(
        args.from_block,
        args.to_block,
        address=PONS_V2_FACTORY,
        topics=[V2_POOL_GRADUATED_TOPIC],
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )
    counters = {"all_graduations": 0, "matched_graduations": 0}

    def decoded():
        for log in raw:
            counters["all_graduations"] += 1
            row = decode_v2_pool_graduation(log)
            if row.token not in tokens:
                continue
            counters["matched_graduations"] += 1
            yield row

    manifest = write_jsonl_snapshot(
        decoded(),
        output=Path(args.out),
        provenance={
            "source": "evm_json_rpc",
            "chain_id": 4663,
            "protocol": "pons_v2_graduations",
            "registry": Path(args.registry).name,
            "from_block": args.from_block,
            "to_block": args.to_block,
            "event_topic0": V2_POOL_GRADUATED_TOPIC,
        },
    )
    print(
        json.dumps(
            {
                **manifest,
                **counters,
                "requests_made": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_rpc_v2_registration_tape(args: argparse.Namespace) -> int:
    registry = _load_jsonl(args.registry)
    tokens = {row["token"].lower() for row in registry}
    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    started = time.monotonic()
    raw = rpc.iter_logs_chunked(
        args.from_block,
        args.to_block,
        address=PONS_V2_MEME_HOOK,
        topics=[PONS_V2_POOL_REGISTERED_TOPIC],
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )
    counters = {"all_registrations": 0, "matched_registrations": 0}

    def decoded():
        for log in raw:
            counters["all_registrations"] += 1
            row = decode_pons_v2_pool_registered(log)
            if row.token not in tokens:
                continue
            counters["matched_registrations"] += 1
            yield row

    manifest = write_jsonl_snapshot(
        decoded(),
        output=Path(args.out),
        provenance={
            "source": "evm_json_rpc",
            "chain_id": 4663,
            "protocol": "pons_v2_v4_pool_registrations",
            "hook": PONS_V2_MEME_HOOK.lower(),
            "registry": Path(args.registry).name,
            "from_block": args.from_block,
            "to_block": args.to_block,
            "event_topic0": PONS_V2_POOL_REGISTERED_TOPIC,
        },
    )
    print(
        json.dumps(
            {
                **manifest,
                **counters,
                "requests_made": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_rpc_v2_v4_tape(args: argparse.Namespace) -> int:
    registrations = _load_jsonl(args.registrations)
    pool_ids = {row["pool_id"].lower() for row in registrations}
    if not pool_ids:
        # A valid window can contain no graduations/registrations.
        write_jsonl_snapshot(
            [],
            output=Path(args.out),
            provenance={
                "source": "evm_json_rpc",
                "chain_id": 4663,
                "protocol": "pons_v2_v4_swaps",
                "registrations": Path(args.registrations).name,
                "from_block": args.from_block,
                "to_block": args.to_block,
                "empty_reason": "no registered Pons V2 pool ids",
            },
        )
        print(json.dumps({"records": 0, "requests_made": 0}, sort_keys=True))
        return 0

    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    started = time.monotonic()
    raw = rpc.iter_logs_chunked(
        args.from_block,
        args.to_block,
        address=UNISWAP_V4_POOL_MANAGER,
        topics=[V4_SWAP_TOPIC],
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )
    counters = {"all_v4_swaps": 0, "matched_pons_v4_swaps": 0}
    matched_ids: set[str] = set()

    def decoded():
        for log in raw:
            counters["all_v4_swaps"] += 1
            row = decode_v4_swap(log)
            if row.pool_id not in pool_ids:
                continue
            counters["matched_pons_v4_swaps"] += 1
            matched_ids.add(row.pool_id)
            yield row

    manifest = write_jsonl_snapshot(
        decoded(),
        output=Path(args.out),
        provenance={
            "source": "evm_json_rpc",
            "chain_id": 4663,
            "protocol": "pons_v2_v4_swaps",
            "pool_manager": UNISWAP_V4_POOL_MANAGER.lower(),
            "registrations": Path(args.registrations).name,
            "registered_pool_ids": len(pool_ids),
            "from_block": args.from_block,
            "to_block": args.to_block,
            "event_topic0": V4_SWAP_TOPIC,
        },
    )
    print(
        json.dumps(
            {
                **manifest,
                **counters,
                "matched_pool_ids": len(matched_ids),
                "requests_made": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_rpc_v2_curve_market_cap_window(args: argparse.Namespace) -> int:
    """Replay V2 curve spot prices and emit $100k eligibility evidence."""
    if args.from_block <= 0:
        raise SystemExit("from-block must be > 0")

    registry = _load_jsonl(args.registry)
    initial_quote_usd, quote_usd_updates = _load_quote_oracle_inputs(args)
    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    started = time.monotonic()
    initial_weth_usd = v3_quote_price_at_block(
        rpc,
        token=ROBINHOOD_WETH,
        quote_token=ROBINHOOD_USDG,
        pool=args.usd_anchor_pool,
        block=args.from_block - 1,
    )
    anchor_points = reconstruct_v3_price_points(
        rpc,
        token=ROBINHOOD_WETH,
        quote_token=ROBINHOOD_USDG,
        pool=args.usd_anchor_pool,
        from_block=args.from_block,
        to_block=args.to_block,
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )
    points = build_v2_curve_market_cap_points(
        registry,
        _iter_jsonl(args.curve_events),
        anchor_points,
        initial_weth_usd=initial_weth_usd,
        initial_quote_usd=initial_quote_usd,
        quote_usd_updates=quote_usd_updates,
    )
    point_manifest = write_jsonl_snapshot(
        points,
        output=Path(args.out),
        provenance={
            "source": "derived_shared_tapes",
            "chain_id": 4663,
            "protocol": "pons_v2_curve",
            "registry": Path(args.registry).name,
            "curve_events": Path(args.curve_events).name,
            "usd_anchor_pool": args.usd_anchor_pool.lower(),
            "from_block": args.from_block,
            "to_block": args.to_block,
            "oracle_state": (
                Path(args.oracle_state).name if args.oracle_state else None
            ),
            "oracle_events": (
                Path(args.oracle_events).name if args.oracle_events else None
            ),
        },
    )
    summary = summarize_v2_curve_market_caps(_iter_jsonl(args.out))
    summary_manifest = write_jsonl_snapshot(
        summary,
        output=Path(args.summary_out),
        provenance={
            "source": "derived_v2_curve_market_cap_points",
            "market_cap_points_sha256": point_manifest["sha256"],
            "eligibility_threshold_usd": "100000",
            "threshold_semantics": "reached at least once on reconstructed curve path",
        },
    )
    print(
        json.dumps(
            {
                "market_cap_points": point_manifest,
                "token_summary": summary_manifest,
                "tokens": len(summary),
                "tokens_priced": sum(row["priced_points"] > 0 for row in summary),
                "tokens_crossed_100k_on_curve": sum(
                    bool(row["crossed_100k"]) for row in summary
                ),
                "unsupported_quote_tokens": sum(
                    row["priced_points"] == 0 for row in summary
                ),
                "initial_weth_usd": str(initial_weth_usd),
                "requests_made": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_rpc_v2_curve_tape(args: argparse.Namespace) -> int:
    """Acquire one shared Pons V2 reserve-changing event tape."""
    registry = _load_jsonl(args.registry)
    curve_to_token = {
        row["curve"].lower(): row["token"].lower()
        for row in registry
        if row.get("curve")
    }
    if not curve_to_token:
        raise SystemExit("V2 registry contains no curves")

    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    started = time.monotonic()
    topics = [
        V2_CURVE_BUY_TOPIC,
        V2_CURVE_SELL_TOPIC,
        V2_CURVE_BUYBACK_LOCKED_TOPIC,
    ]
    raw_tape = rpc.iter_logs_chunked(
        args.from_block,
        args.to_block,
        topics=[topics],
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )
    counters = {"all_curve_signature_logs": 0, "matched_pons_curve_events": 0}
    matched_curves: set[str] = set()

    def decoded():
        for raw in raw_tape:
            counters["all_curve_signature_logs"] += 1
            curve = raw.address.lower()
            token = curve_to_token.get(curve)
            if token is None:
                continue
            topic0 = raw.topics[0] if raw.topics else None
            if topic0 in {V2_CURVE_BUY_TOPIC, V2_CURVE_SELL_TOPIC}:
                event = asdict(decode_v2_curve_trade(raw, token=token))
                event["event_type"] = (
                    "curve_buy" if event["side"] == "buy" else "curve_sell"
                )
            elif topic0 == V2_CURVE_BUYBACK_LOCKED_TOPIC:
                event = asdict(decode_v2_curve_buyback(raw))
                event["event_type"] = "curve_buyback"
            else:
                continue
            counters["matched_pons_curve_events"] += 1
            matched_curves.add(curve)
            yield event

    manifest = write_jsonl_snapshot(
        decoded(),
        output=Path(args.out),
        provenance={
            "source": "evm_json_rpc",
            "chain_id": 4663,
            "protocol": "pons_v2_shared_curve_tape",
            "registry": Path(args.registry).name,
            "registry_curves": len(curve_to_token),
            "event_topic0_or": topics,
            "from_block": args.from_block,
            "to_block": args.to_block,
            "initial_chunk_size": args.chunk_size,
            "min_chunk_size": args.min_chunk_size,
        },
    )
    print(
        json.dumps(
            {
                **manifest,
                **counters,
                "matched_curves": len(matched_curves),
                "requests_made": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_rpc_v2_registry_window(args: argparse.Namespace) -> int:
    """Build a point-in-time enriched Pons V2 launch-registry shard."""
    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    if args.from_block < PONS_V2_DEPLOYMENT_BLOCK:
        raise SystemExit(
            f"from-block cannot precede Pons V2 deployment {PONS_V2_DEPLOYMENT_BLOCK}"
        )

    started = time.monotonic()
    topic_or = [
        V2_TOKEN_LAUNCHED_TOPIC,
        V2_LAUNCH_CONFIG_ADDED_TOPIC,
        V2_LAUNCH_CONFIG_UPDATED_TOPIC,
        V2_PAIR_TOKEN_ECONOMICS_UPDATED_TOPIC,
    ]
    raw = list(
        rpc.iter_logs_chunked(
            args.from_block,
            args.to_block,
            address=PONS_V2_FACTORY,
            topics=[topic_or],
            chunk_size=args.chunk_size,
            min_chunk_size=args.min_chunk_size,
        )
    )
    launches = [
        decode_v2_launch(row)
        for row in raw
        if row.topics and row.topics[0] == V2_TOKEN_LAUNCHED_TOPIC
    ]
    config_ids = sorted(
        {
            launch.launch_config_id
            for launch in launches
            if launch.launch_config_id is not None
        }
    )
    pair_tokens = sorted(
        {
            launch.pair_token.lower()
            for launch in launches
            if launch.pair_token.lower() != ZERO_ADDRESS
        }
    )

    bootstrap_configs = []
    bootstrap_pair_economics = []
    if args.from_block > PONS_V2_DEPLOYMENT_BLOCK:
        for config_id in config_ids:
            try:
                bootstrap_configs.append(
                    read_v2_launch_config_state(
                        rpc,
                        config_id,
                        block=args.from_block - 1,
                    )
                )
            except Exception:
                # A config created inside this shard legitimately does not
                # exist at the prior block. Its event is resolved below.
                pass
        for pair in pair_tokens:
            economics = read_v2_pair_token_economics_state(
                rpc,
                pair,
                block=args.from_block - 1,
            )
            if economics.phantom_quote != 0:
                bootstrap_pair_economics.append(economics)

    config_events = []
    seen_config_block: set[tuple[int, int]] = set()
    for row in raw:
        if not row.topics or row.topics[0] not in {
            V2_LAUNCH_CONFIG_ADDED_TOPIC,
            V2_LAUNCH_CONFIG_UPDATED_TOPIC,
        }:
            continue
        action, config_id = decode_v2_launch_config_event_id(row)
        ambiguity = (row.block_number, config_id)
        if ambiguity in seen_config_block:
            raise RuntimeError(
                "multiple V2 config mutations for one id in one block; "
                "transaction-input decoding is required before proceeding"
            )
        seen_config_block.add(ambiguity)
        config_events.append((row, action, config_id))

    resolved = {}
    for row, action, config_id in config_events:
        order = (
            row.block_number,
            -1 if row.transaction_index is None else row.transaction_index,
            row.log_index,
        )
        resolved[order] = read_v2_launch_config_state(
            rpc,
            config_id,
            block=row.block_number,
            action=action,
            transaction_hash=row.transaction_hash,
            transaction_index=row.transaction_index,
            log_index=row.log_index,
        )

    rows = iter_enriched_v2_launches(
        raw,
        bootstrap_configs=bootstrap_configs,
        bootstrap_pair_economics=bootstrap_pair_economics,
        resolved_config_events=resolved,
    )
    manifest = write_jsonl_snapshot(
        rows,
        output=Path(args.out),
        provenance={
            "source": "evm_json_rpc",
            "chain_id": 4663,
            "protocol": "pons_v2_registry",
            "factory": PONS_V2_FACTORY.lower(),
            "from_block": args.from_block,
            "to_block": args.to_block,
            "topic0_or": topic_or,
            "bootstrap_config_ids": config_ids,
            "bootstrap_pair_tokens": pair_tokens,
            "initial_chunk_size": args.chunk_size,
            "min_chunk_size": args.min_chunk_size,
            "token_decimals_source": (
                "PonsV2LauncherToken inherits OpenZeppelin ERC20 default 18 decimals"
            ),
        },
    )
    print(
        json.dumps(
            {
                **manifest,
                "factory_events": len(raw),
                "bootstrap_configs": len(bootstrap_configs),
                "bootstrap_pair_economics": len(bootstrap_pair_economics),
                "resolved_config_events": len(resolved),
                "requests_made": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_rpc_v1_registry_window(args: argparse.Namespace) -> int:
    """Build an independently reproducible enriched Pons V1 launch shard."""
    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    if args.from_block < PONS_V1_DEPLOYMENT_BLOCK:
        raise SystemExit(
            f"from-block cannot precede Pons V1 deployment {PONS_V1_DEPLOYMENT_BLOCK}"
        )

    started = time.monotonic()
    topic_or = [
        V1_TOKEN_LAUNCHED_TOPIC,
        V1_LAUNCH_CONFIG_ADDED_TOPIC,
        V1_LAUNCH_CONFIG_UPDATED_TOPIC,
    ]
    raw = list(
        rpc.iter_logs_chunked(
            args.from_block,
            args.to_block,
            address=PONS_V1_FACTORY,
            topics=[topic_or],
            chunk_size=args.chunk_size,
            min_chunk_size=args.min_chunk_size,
        )
    )

    launch_config_ids = sorted(
        {
            decode_v1_launch(row).launch_config_id
            for row in raw
            if row.topics and row.topics[0] == V1_TOKEN_LAUNCHED_TOPIC
        }
    )
    bootstrap = []
    if args.from_block > PONS_V1_DEPLOYMENT_BLOCK:
        for config_id in launch_config_ids:
            if config_id is None:
                continue
            bootstrap.append(
                read_v1_launch_config_state(
                    rpc,
                    config_id,
                    block=args.from_block - 1,
                )
            )

    rows = iter_enriched_v1_launches(raw, bootstrap_configs=bootstrap)
    manifest = write_jsonl_snapshot(
        rows,
        output=Path(args.out),
        provenance={
            "source": "evm_json_rpc",
            "chain_id": 4663,
            "protocol": "pons_v1_registry",
            "factory": PONS_V1_FACTORY.lower(),
            "from_block": args.from_block,
            "to_block": args.to_block,
            "topic0_or": topic_or,
            "bootstrap_config_ids": launch_config_ids,
            "initial_chunk_size": args.chunk_size,
            "min_chunk_size": args.min_chunk_size,
            "token_decimals_source": "PonsLauncherToken inherits OpenZeppelin ERC20 default 18 decimals",
        },
    )
    print(
        json.dumps(
            {
                **manifest,
                "factory_events": len(raw),
                "bootstrap_configs": len(bootstrap),
                "requests_made": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0


def _iter_jsonl(path: str):
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _load_jsonl(path: str) -> list[dict]:
    return list(_iter_jsonl(path))




def _load_quote_oracle_inputs(args: argparse.Namespace):
    state_path = getattr(args, "oracle_state", None)
    event_path = getattr(args, "oracle_events", None)
    if bool(state_path) != bool(event_path):
        raise SystemExit(
            "--oracle-state and --oracle-events must be supplied together"
        )
    if not state_path:
        return {}, []
    states = _load_jsonl(state_path)
    updates = _load_jsonl(event_path)
    initial = {
        row["quote_token"].lower(): Decimal(row["usd_price"])
        for row in states
    }
    return initial, updates


def cmd_rpc_v3_pons_tape(args: argparse.Namespace) -> int:
    """Acquire one shared V3 Swap tape and keep only registered Pons pools."""
    registry = _load_jsonl(args.registry)
    pool_launch_block = {
        row["pool"].lower(): int(row["block_number"])
        for row in registry
        if row.get("pool")
    }
    if not pool_launch_block:
        raise SystemExit("registry contains no Pons V1 pools")

    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    started = time.monotonic()
    raw_tape = rpc.iter_logs_chunked(
        args.from_block,
        args.to_block,
        topics=[V3_SWAP_TOPIC],
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )

    counters = {"all_v3_swap_logs": 0, "matched_pons_swaps": 0}
    matched_pools: set[str] = set()

    def matched():
        for raw in raw_tape:
            counters["all_v3_swap_logs"] += 1
            pool = raw.address.lower()
            launch_block = pool_launch_block.get(pool)
            if launch_block is None:
                continue
            if raw.block_number < launch_block:
                raise RuntimeError(
                    f"swap for Pons pool {pool} predates recorded launch block"
                )
            swap = decode_v3_swap(raw)
            counters["matched_pons_swaps"] += 1
            matched_pools.add(pool)
            yield swap

    manifest = write_jsonl_snapshot(
        matched(),
        output=Path(args.out),
        provenance={
            "source": "evm_json_rpc",
            "chain_id": 4663,
            "protocol": "uniswap_v3_shared_swap_tape",
            "event_topic0": V3_SWAP_TOPIC,
            "registry": str(Path(args.registry).name),
            "registry_pools": len(pool_launch_block),
            "from_block": args.from_block,
            "to_block": args.to_block,
            "initial_chunk_size": args.chunk_size,
            "min_chunk_size": args.min_chunk_size,
        },
    )
    print(
        json.dumps(
            {
                **manifest,
                **counters,
                "matched_pools": len(matched_pools),
                "requests_made": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0



def cmd_rpc_v1_market_cap_window(args: argparse.Namespace) -> int:
    """Price a shared V1 swap shard and emit per-token $100k eligibility."""
    if args.from_block <= 0:
        raise SystemExit("from-block must be > 0 for point-in-time USD anchoring")

    registry = _load_jsonl(args.registry)
    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    started = time.monotonic()

    state_block = args.from_block - 1
    weth_state = read_erc20_static(rpc, ROBINHOOD_WETH, block=state_block)
    usdg_state = read_erc20_static(rpc, ROBINHOOD_USDG, block=state_block)
    initial_weth_usd = v3_quote_price_at_block(
        rpc,
        token=ROBINHOOD_WETH,
        quote_token=ROBINHOOD_USDG,
        pool=args.usd_anchor_pool,
        block=state_block,
    )
    anchor_points = reconstruct_v3_price_points(
        rpc,
        token=ROBINHOOD_WETH,
        quote_token=ROBINHOOD_USDG,
        pool=args.usd_anchor_pool,
        from_block=args.from_block,
        to_block=args.to_block,
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )
    points = build_v1_market_cap_points(
        registry,
        _iter_jsonl(args.swaps),
        anchor_points,
        initial_weth_usd=initial_weth_usd,
        weth_decimals=weth_state.decimals,
        usdg_decimals=usdg_state.decimals,
    )

    point_manifest = write_jsonl_snapshot(
        points,
        output=Path(args.out),
        provenance={
            "source": "derived_shared_tapes",
            "chain_id": 4663,
            "protocol": "pons_v1_uniswap_v3",
            "registry": Path(args.registry).name,
            "swaps": Path(args.swaps).name,
            "usd_anchor_pool": args.usd_anchor_pool.lower(),
            "usd_anchor_semantics": "USDG nominal USD 1; WETH/USDG latest already-observable V3 price",
            "from_block": args.from_block,
            "to_block": args.to_block,
            "weth_decimals": weth_state.decimals,
            "usdg_decimals": usdg_state.decimals,
        },
    )

    summary = summarize_v1_market_caps(_iter_jsonl(args.out))
    summary_manifest = write_jsonl_snapshot(
        summary,
        output=Path(args.summary_out),
        provenance={
            "source": "derived_market_cap_points",
            "market_cap_points_sha256": point_manifest["sha256"],
            "eligibility_threshold_usd": "100000",
            "threshold_semantics": "reached at least once in this observed swap window",
        },
    )
    priced = sum(row["priced_points"] > 0 for row in summary)
    crossed = sum(bool(row["crossed_100k"]) for row in summary)
    print(
        json.dumps(
            {
                "market_cap_points": point_manifest,
                "token_summary": summary_manifest,
                "tokens_with_swaps": len(summary),
                "tokens_priced": priced,
                "tokens_crossed_100k_in_window": crossed,
                "initial_weth_usd": str(initial_weth_usd),
                "weth_decimals": weth_state.decimals,
                "usdg_decimals": usdg_state.decimals,
                "requests_made": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_rpc_v1_usd_path(args: argparse.Namespace) -> int:
    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    if args.from_block <= 0:
        raise SystemExit("from-block must be > 0 for a point-in-time anchor")

    started = time.monotonic()
    initial_weth_usd = v3_quote_price_at_block(
        rpc,
        token=ROBINHOOD_WETH,
        quote_token=ROBINHOOD_USDG,
        pool=args.usd_anchor_pool,
        block=args.from_block - 1,
    )
    anchor_points = reconstruct_v3_price_points(
        rpc,
        token=ROBINHOOD_WETH,
        quote_token=ROBINHOOD_USDG,
        pool=args.usd_anchor_pool,
        from_block=args.from_block,
        to_block=args.to_block,
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )
    target_points = reconstruct_v3_price_points(
        rpc,
        token=args.token,
        quote_token=args.quote_token,
        pool=args.pool,
        from_block=args.from_block,
        to_block=args.to_block,
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )
    rows = attach_quote_usd_anchor(
        target_points,
        anchor_points,
        initial_quote_usd=initial_weth_usd,
    )
    manifest = write_jsonl_snapshot(
        rows,
        output=Path(args.out),
        provenance={
            "source": "evm_json_rpc",
            "chain_id": 4663,
            "protocol": "uniswap_v3",
            "token": args.token.lower(),
            "quote_token": args.quote_token.lower(),
            "pool": args.pool.lower(),
            "usd_anchor_token": ROBINHOOD_WETH.lower(),
            "usd_anchor_quote": ROBINHOOD_USDG.lower(),
            "usd_anchor_pool": args.usd_anchor_pool.lower(),
            "usd_anchor_semantics": "USDG nominal USD 1; WETH/USDG latest prior observable V3 price",
            "from_block": args.from_block,
            "to_block": args.to_block,
            "initial_chunk_size": args.chunk_size,
            "min_chunk_size": args.min_chunk_size,
        },
    )
    print(
        json.dumps(
            {
                **manifest,
                "initial_weth_usd": str(initial_weth_usd),
                "requests_made": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_rpc_v1_price_path(args: argparse.Namespace) -> int:
    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    started = time.monotonic()
    rows = reconstruct_v3_price_points(
        rpc,
        token=args.token,
        quote_token=args.quote_token,
        pool=args.pool,
        from_block=args.from_block,
        to_block=args.to_block,
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )
    manifest = write_jsonl_snapshot(
        rows,
        output=Path(args.out),
        provenance={
            "source": "evm_json_rpc",
            "chain_id": 4663,
            "protocol": "uniswap_v3",
            "token": args.token.lower(),
            "quote_token": args.quote_token.lower(),
            "pool": args.pool.lower(),
            "from_block": args.from_block,
            "to_block": args.to_block,
            "initial_chunk_size": args.chunk_size,
            "min_chunk_size": args.min_chunk_size,
        },
    )
    print(
        json.dumps(
            {
                **manifest,
                "requests_made": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_rpc_pons_sample(args: argparse.Namespace) -> int:
    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    if args.version == "v1":
        address = PONS_V1_FACTORY
        topic = V1_TOKEN_LAUNCHED_TOPIC
        decoder = decode_v1_launch
    else:
        address = PONS_V2_FACTORY
        topic = V2_TOKEN_LAUNCHED_TOPIC
        decoder = decode_v2_launch

    started = time.monotonic()
    from_block = args.from_block
    if from_block is None:
        from_block = rpc.find_first_code_block(address)
    to_block = args.to_block if args.to_block is not None else rpc.block_number()

    raw_logs = rpc.iter_logs_chunked(
        from_block,
        to_block,
        address=address,
        topics=[topic],
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )

    def limited():
        count = 0
        for log in raw_logs:
            yield decoder(log)
            count += 1
            if args.limit is not None and count >= args.limit:
                return

    output = Path(args.out)
    manifest = write_jsonl_snapshot(
        limited(),
        output=output,
        provenance={
            "source": "evm_json_rpc",
            "chain_id": 4663,
            "protocol": "pons",
            "protocol_version": args.version,
            "factory": address.lower(),
            "event_topic0": topic,
            "from_block": from_block,
            "to_block": to_block,
            "requested_limit": args.limit,
            "initial_chunk_size": args.chunk_size,
            "min_chunk_size": args.min_chunk_size,
        },
    )
    print(
        json.dumps(
            {
                **manifest,
                "requests_made": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_pons_scan(args: argparse.Namespace) -> int:
    rpc = _rpc(args)
    rpc.assert_robinhood()
    if args.version == "v1":
        address = PONS_V1_FACTORY
        topic = V1_TOKEN_LAUNCHED_TOPIC
        decoder = decode_v1_launch
    else:
        address = PONS_V2_FACTORY
        topic = V2_TOKEN_LAUNCHED_TOPIC
        decoder = decode_v2_launch

    logs = rpc.get_logs(
        args.from_block,
        args.to_block,
        address=address,
        topics=[topic],
    )
    launches = [asdict(decoder(log)) for log in logs]
    print(json.dumps({"count": len(launches), "launches": launches}, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hlp")
    parser.add_argument("--rpc-url", default=DEFAULT_RPC_URL)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument(
        "--min-interval",
        type=float,
        default=0.0,
        help="minimum seconds between RPC attempts for provider pacing",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    smoke = sub.add_parser("network-smoke")
    smoke.set_defaults(func=cmd_network_smoke)

    hood = sub.add_parser("hood-smoke")
    hood.set_defaults(func=cmd_hood_smoke)

    creation = sub.add_parser("contract-creation")
    creation.add_argument("address")
    creation.set_defaults(func=cmd_contract_creation)

    deploy = sub.add_parser("deployment-block")
    deploy.add_argument("address")
    deploy.add_argument("--low", type=int, default=0)
    deploy.add_argument("--high", type=int)
    deploy.set_defaults(func=cmd_deployment_block)

    blockscout_sample = sub.add_parser("blockscout-pons-sample")
    blockscout_sample.add_argument("--version", choices=("v1", "v2"), required=True)
    blockscout_sample.add_argument("--limit", type=int, default=100)
    blockscout_sample.add_argument("--out", required=True)
    blockscout_sample.set_defaults(func=cmd_blockscout_pons_sample)

    sample = sub.add_parser("hood-pons-sample")
    sample.add_argument("--version", choices=("v1", "v2"), required=True)
    sample.add_argument("--limit", type=int, default=100)
    sample.add_argument("--page-size", type=int, default=1000)
    sample.add_argument("--out", required=True)
    sample.set_defaults(func=cmd_hood_pons_sample)



    v2_registry = sub.add_parser("rpc-v2-registry-window")
    v2_registry.add_argument("--from-block", type=int, required=True)
    v2_registry.add_argument("--to-block", type=int, required=True)
    v2_registry.add_argument("--chunk-size", type=int, default=100_000)
    v2_registry.add_argument("--min-chunk-size", type=int, default=1)
    v2_registry.add_argument("--out", required=True)
    v2_registry.set_defaults(func=cmd_rpc_v2_registry_window)

    v2_tape = sub.add_parser("rpc-v2-curve-tape")
    v2_tape.add_argument("--registry", required=True)
    v2_tape.add_argument("--from-block", type=int, required=True)
    v2_tape.add_argument("--to-block", type=int, required=True)
    v2_tape.add_argument("--chunk-size", type=int, default=100_000)
    v2_tape.add_argument("--min-chunk-size", type=int, default=1)
    v2_tape.add_argument("--out", required=True)
    v2_tape.set_defaults(func=cmd_rpc_v2_curve_tape)


    v2_graduations = sub.add_parser("rpc-v2-graduation-tape")
    v2_graduations.add_argument("--registry", required=True)
    v2_graduations.add_argument("--from-block", type=int, required=True)
    v2_graduations.add_argument("--to-block", type=int, required=True)
    v2_graduations.add_argument("--chunk-size", type=int, default=100_000)
    v2_graduations.add_argument("--min-chunk-size", type=int, default=1)
    v2_graduations.add_argument("--out", required=True)
    v2_graduations.set_defaults(func=cmd_rpc_v2_graduation_tape)

    v2_registrations = sub.add_parser("rpc-v2-registration-tape")
    v2_registrations.add_argument("--registry", required=True)
    v2_registrations.add_argument("--from-block", type=int, required=True)
    v2_registrations.add_argument("--to-block", type=int, required=True)
    v2_registrations.add_argument("--chunk-size", type=int, default=100_000)
    v2_registrations.add_argument("--min-chunk-size", type=int, default=1)
    v2_registrations.add_argument("--out", required=True)
    v2_registrations.set_defaults(func=cmd_rpc_v2_registration_tape)

    v2_v4 = sub.add_parser("rpc-v2-v4-tape")
    v2_v4.add_argument("--registrations", required=True)
    v2_v4.add_argument("--from-block", type=int, required=True)
    v2_v4.add_argument("--to-block", type=int, required=True)
    v2_v4.add_argument("--chunk-size", type=int, default=100_000)
    v2_v4.add_argument("--min-chunk-size", type=int, default=1)
    v2_v4.add_argument("--out", required=True)
    v2_v4.set_defaults(func=cmd_rpc_v2_v4_tape)



    v2_stock_oracle = sub.add_parser("rpc-v2-stock-oracle-window")
    v2_stock_oracle.add_argument("--registry", required=True)
    v2_stock_oracle.add_argument("--from-block", type=int, required=True)
    v2_stock_oracle.add_argument("--to-block", type=int, required=True)
    v2_stock_oracle.add_argument("--chunk-size", type=int, default=100_000)
    v2_stock_oracle.add_argument("--min-chunk-size", type=int, default=1)
    v2_stock_oracle.add_argument("--feed-out", required=True)
    v2_stock_oracle.add_argument("--state-out", required=True)
    v2_stock_oracle.add_argument("--out", required=True)
    v2_stock_oracle.set_defaults(func=cmd_rpc_v2_stock_oracle_window)

    v2_v4_mcap = sub.add_parser("rpc-v2-v4-market-cap-window")
    v2_v4_mcap.add_argument("--registry", required=True)
    v2_v4_mcap.add_argument("--curve-points", required=True)
    v2_v4_mcap.add_argument("--graduations", required=True)
    v2_v4_mcap.add_argument("--registrations", required=True)
    v2_v4_mcap.add_argument("--v4-swaps", required=True)
    v2_v4_mcap.add_argument("--from-block", type=int, required=True)
    v2_v4_mcap.add_argument("--to-block", type=int, required=True)
    v2_v4_mcap.add_argument("--chunk-size", type=int, default=100_000)
    v2_v4_mcap.add_argument("--min-chunk-size", type=int, default=1)
    v2_v4_mcap.add_argument(
        "--usd-anchor-pool",
        default=UNISWAP_V3_WETH_USDG_ANCHOR_POOL,
    )
    v2_v4_mcap.add_argument("--oracle-state")
    v2_v4_mcap.add_argument("--oracle-events")
    v2_v4_mcap.add_argument("--seed-out", required=True)
    v2_v4_mcap.add_argument("--out", required=True)
    v2_v4_mcap.add_argument("--transition-out", required=True)
    v2_v4_mcap.add_argument("--summary-out", required=True)
    v2_v4_mcap.set_defaults(func=cmd_rpc_v2_v4_market_cap_window)

    v2_mcap = sub.add_parser("rpc-v2-curve-market-cap-window")
    v2_mcap.add_argument("--registry", required=True)
    v2_mcap.add_argument("--curve-events", required=True)
    v2_mcap.add_argument("--from-block", type=int, required=True)
    v2_mcap.add_argument("--to-block", type=int, required=True)
    v2_mcap.add_argument("--chunk-size", type=int, default=100_000)
    v2_mcap.add_argument("--min-chunk-size", type=int, default=1)
    v2_mcap.add_argument(
        "--usd-anchor-pool",
        default=UNISWAP_V3_WETH_USDG_ANCHOR_POOL,
    )
    v2_mcap.add_argument("--oracle-state")
    v2_mcap.add_argument("--oracle-events")
    v2_mcap.add_argument("--out", required=True)
    v2_mcap.add_argument("--summary-out", required=True)
    v2_mcap.set_defaults(func=cmd_rpc_v2_curve_market_cap_window)

    registry = sub.add_parser("rpc-v1-registry-window")
    registry.add_argument("--from-block", type=int, required=True)
    registry.add_argument("--to-block", type=int, required=True)
    registry.add_argument("--chunk-size", type=int, default=100_000)
    registry.add_argument("--min-chunk-size", type=int, default=1)
    registry.add_argument("--out", required=True)
    registry.set_defaults(func=cmd_rpc_v1_registry_window)

    tape = sub.add_parser("rpc-v3-pons-tape")
    tape.add_argument("--registry", required=True)
    tape.add_argument("--from-block", type=int, required=True)
    tape.add_argument("--to-block", type=int, required=True)
    tape.add_argument("--chunk-size", type=int, default=100_000)
    tape.add_argument("--min-chunk-size", type=int, default=1)
    tape.add_argument("--out", required=True)
    tape.set_defaults(func=cmd_rpc_v3_pons_tape)


    market_caps = sub.add_parser("rpc-v1-market-cap-window")
    market_caps.add_argument("--registry", required=True)
    market_caps.add_argument("--swaps", required=True)
    market_caps.add_argument("--from-block", type=int, required=True)
    market_caps.add_argument("--to-block", type=int, required=True)
    market_caps.add_argument("--chunk-size", type=int, default=100_000)
    market_caps.add_argument("--min-chunk-size", type=int, default=1)
    market_caps.add_argument(
        "--usd-anchor-pool",
        default=UNISWAP_V3_WETH_USDG_ANCHOR_POOL,
    )
    market_caps.add_argument("--out", required=True)
    market_caps.add_argument("--summary-out", required=True)
    market_caps.set_defaults(func=cmd_rpc_v1_market_cap_window)

    usd_path = sub.add_parser("rpc-v1-usd-path")
    usd_path.add_argument("--token", required=True)
    usd_path.add_argument("--quote-token", default=ROBINHOOD_WETH)
    usd_path.add_argument("--pool", required=True)
    usd_path.add_argument(
        "--usd-anchor-pool",
        default=UNISWAP_V3_WETH_USDG_ANCHOR_POOL,
    )
    usd_path.add_argument("--from-block", type=int, required=True)
    usd_path.add_argument("--to-block", type=int, required=True)
    usd_path.add_argument("--chunk-size", type=int, default=100_000)
    usd_path.add_argument("--min-chunk-size", type=int, default=1)
    usd_path.add_argument("--out", required=True)
    usd_path.set_defaults(func=cmd_rpc_v1_usd_path)

    price_path = sub.add_parser("rpc-v1-price-path")
    price_path.add_argument("--token", required=True)
    price_path.add_argument("--quote-token", required=True)
    price_path.add_argument("--pool", required=True)
    price_path.add_argument("--from-block", type=int, required=True)
    price_path.add_argument("--to-block", type=int, required=True)
    price_path.add_argument("--chunk-size", type=int, default=100_000)
    price_path.add_argument("--min-chunk-size", type=int, default=1)
    price_path.add_argument("--out", required=True)
    price_path.set_defaults(func=cmd_rpc_v1_price_path)

    rpc_sample = sub.add_parser("rpc-pons-sample")
    rpc_sample.add_argument("--version", choices=("v1", "v2"), required=True)
    rpc_sample.add_argument("--from-block", type=int)
    rpc_sample.add_argument("--to-block", type=int)
    rpc_sample.add_argument("--limit", type=int, default=100)
    rpc_sample.add_argument("--chunk-size", type=int, default=100000)
    rpc_sample.add_argument("--min-chunk-size", type=int, default=1)
    rpc_sample.add_argument("--out", required=True)
    rpc_sample.set_defaults(func=cmd_rpc_pons_sample)

    scan = sub.add_parser("pons-scan")
    scan.add_argument("--version", choices=("v1", "v2"), required=True)
    scan.add_argument("--from-block", type=int, required=True)
    scan.add_argument("--to-block", type=int, required=True)
    scan.set_defaults(func=cmd_pons_scan)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
