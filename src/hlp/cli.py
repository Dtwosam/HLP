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
    SOLIDRPC_AUTH_RPC_URL,
    ROBINHOOD_USDG,
    ROBINHOOD_WETH,
    UNISWAP_V3_WETH_USDG_ANCHOR_POOL,
    UNISWAP_V3_FACTORY,
    PONS_V1_FACTORY,
    PONS_V1_FACTORIES,
    PONS_V1_FACTORY_DEPLOYMENT_BLOCKS,
    PONS_V1_FIRST_DEPLOYMENT_BLOCK,
    PONS_V2_FACTORY,
    PONS_V1_DEPLOYMENT_BLOCK,
    PONS_V2_DEPLOYMENT_BLOCK,
    PONS_V2_MEME_HOOK,
    POOLS_TRADE_INSTANT_STRATEGIES,
    POOLS_TRADE_LAUNCHER_CURRENT,
    POOLS_TRADE_LAUNCHER_ORIGINAL,
    POOLS_FUN_FACTORY,
    FLAP_PORTAL,
    HOOD_FUN_CURRENT,
    TRENCH_MANAGER,
    UNISWAP_V4_POOL_MANAGER,
)
from hlp.protocols.uniswap import (
    PONS_V2_POOL_REGISTERED_TOPIC,
    V3_POOL_CREATED_TOPIC,
    V3_INITIALIZE_TOPIC,
    V3_SWAP_TOPIC,
    V4_INITIALIZE_TOPIC,
    V4_SWAP_TOPIC,
    decode_pons_v2_pool_registered,
    decode_v3_pool_created,
    decode_v3_pool_initialized,
    decode_v3_swap,
    decode_v4_pool_initialized,
    decode_v4_swap,
)
from hlp.data.blockscout import BlockscoutClient
from hlp.data.chainlink_directory import ChainlinkDirectoryClient
from hlp.data.hoodexplorer import HoodExplorerClient
from hlp.data.hood_fun_curve import (
    build_hood_fun_curve_market_cap_points,
    summarize_hood_fun_curve_market_caps,
)
from hlp.data.hood_fun_registry import build_hood_fun_launch_registry
from hlp.data.flap_curve import (
    build_flap_curve_market_cap_points,
    summarize_flap_curve_market_caps,
)
from hlp.data.flap_registry import build_flap_launch_registry
from hlp.data.oracle_registry import resolve_stock_quote_feed_specs
from hlp.data.quote_registry import (
    CHAINLINK_PRICED_STATUSES,
    build_pons_quote_registry,
)
from hlp.data.quote_routes import (
    audit_unpriced_v3_quote_routes,
    build_v3_route_initial_usd_states,
    build_v3_route_usd_updates,
    select_v3_quote_routes,
)
from hlp.data.quote_usd import prepare_quote_usd_inputs
from hlp.data.quote_causality import audit_pons_quote_causality
from hlp.data.oracles import (
    reconstruct_chainlink_usd_tapes,
    reconstruct_staggered_chainlink_usd_tapes,
)
from hlp.data.pools_fun_registry import build_pools_fun_registry
from hlp.data.pools_trade_registry import build_pools_trade_instant_registry
from hlp.data.pools_trade_v4 import (
    build_pools_trade_v4_market_cap_points,
    summarize_pools_trade_market_caps,
)
from hlp.data.pons_v1 import iter_enriched_v1_launches
from hlp.data.pons_v2 import (
    ZERO_ADDRESS,
    filter_v2_registry_to_graduated,
    iter_enriched_v2_launches,
)
from hlp.data.pons_trade_features import build_pons_causal_trade_features
from hlp.data.pons_trades import normalize_pons_trades
from hlp.data.pons_transactions import (
    attach_pons_transaction_identities,
    fetch_transaction_identity_rows,
)
from hlp.data.pons_time import (
    enrich_pons_episodes_with_time,
    enrich_pons_points_with_time,
    fetch_block_timestamp_rows,
)
from hlp.data.pons_research import (
    annotate_pons_drawdowns_and_future_returns,
    build_pons_market_path,
    eligible_pons_tokens,
    extract_pons_drawdown_episodes,
    summarize_pons_eligibility,
)
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
from hlp.data.trench_curve import (
    build_trench_curve_market_cap_points,
    summarize_trench_curve_market_caps,
)
from hlp.data.trench_registry import build_trench_launch_registry
from hlp.data.types import FlapEvent, HoodFunEvent, TrenchEvent
from hlp.data.v3_launchpad import (
    build_v3_launchpad_market_cap_points,
    summarize_v3_launchpad_market_caps,
)
from hlp.data.v2_curve import (
    build_v2_curve_market_cap_points,
    merge_v2_lifecycle_market_cap_summaries,
    summarize_v2_curve_market_caps,
)
from hlp.data.v4 import (
    build_v2_graduation_seed_points,
    build_v2_v4_market_cap_points,
)
from hlp.protocols.erc20 import read_erc20_static
from hlp.protocols.flap import FLAP_RECONSTRUCTION_TOPICS, decode_flap_event
from hlp.protocols.hood_fun import HOOD_FUN_CURVE_TOPICS, decode_hood_fun_event
from hlp.protocols.trench import TRENCH_CURVE_TOPICS, decode_trench_event
from hlp.protocols.pons_state import (
    read_v1_launch_config_state,
    read_v2_launch_config_state,
    read_v2_pair_token_economics_state,
)
from hlp.protocols.pools_fun import TOKEN_LAUNCHED_TOPIC as POOLS_FUN_TOKEN_LAUNCHED_TOPIC, decode_pools_fun_launch
from hlp.protocols.pools_trade import (
    TOKEN_CREATED_TOPIC as POOLS_TRADE_TOKEN_CREATED_TOPIC,
    TOKEN_DISTRIBUTED_TOPIC as POOLS_TRADE_TOKEN_DISTRIBUTED_TOPIC,
    TOKEN_LAUNCHED_TOPIC as POOLS_TRADE_TOKEN_LAUNCHED_TOPIC,
    decode_pools_trade_token_created,
    decode_pools_trade_token_distributed,
    decode_pools_trade_token_launched,
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
    key = os.environ.get("ROBINHOOD_ARCHIVE_RPC_API_KEY")
    url = os.environ.get("ROBINHOOD_ARCHIVE_RPC_URL")
    if not url:
        url = SOLIDRPC_AUTH_RPC_URL if key else SOLIDRPC_PUBLIC_RPC_URL
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
        ("flap_portal", FLAP_PORTAL),
        ("hood_fun_current", HOOD_FUN_CURRENT),
        ("trench_manager", TRENCH_MANAGER),
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










def cmd_rpc_dex_pool_window(args: argparse.Namespace) -> int:
    """Acquire chain-wide canonical Uniswap V3/V4 pool-creation tapes."""
    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    started = time.monotonic()

    v3_raw = rpc.iter_logs_chunked(
        args.from_block,
        args.to_block,
        address=UNISWAP_V3_FACTORY,
        topics=[V3_POOL_CREATED_TOPIC],
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )
    v3_manifest = write_jsonl_snapshot(
        (decode_v3_pool_created(row) for row in v3_raw),
        output=Path(args.v3_out),
        provenance={
            "source": "evm_json_rpc",
            "chain_id": 4663,
            "protocol": "uniswap_v3_pool_census",
            "factory": UNISWAP_V3_FACTORY.lower(),
            "event_topic0": V3_POOL_CREATED_TOPIC,
            "from_block": args.from_block,
            "to_block": args.to_block,
            "initial_chunk_size": args.chunk_size,
            "min_chunk_size": args.min_chunk_size,
        },
    )

    v4_raw = rpc.iter_logs_chunked(
        args.from_block,
        args.to_block,
        address=UNISWAP_V4_POOL_MANAGER,
        topics=[V4_INITIALIZE_TOPIC],
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )
    v4_manifest = write_jsonl_snapshot(
        (decode_v4_pool_initialized(row) for row in v4_raw),
        output=Path(args.v4_out),
        provenance={
            "source": "evm_json_rpc",
            "chain_id": 4663,
            "protocol": "uniswap_v4_pool_census",
            "pool_manager": UNISWAP_V4_POOL_MANAGER.lower(),
            "event_topic0": V4_INITIALIZE_TOPIC,
            "from_block": args.from_block,
            "to_block": args.to_block,
            "initial_chunk_size": args.chunk_size,
            "min_chunk_size": args.min_chunk_size,
        },
    )

    print(
        json.dumps(
            {
                "v3": v3_manifest,
                "v4": v4_manifest,
                "requests_made": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0




def cmd_flap_registry(args: argparse.Namespace) -> int:
    """Build a persistent Flap launch/config registry from a Portal tape."""
    events = [FlapEvent(**row) for row in _load_jsonl(args.events)]
    rows = build_flap_launch_registry(events)
    manifest = write_jsonl_snapshot(
        rows,
        output=Path(args.out),
        provenance={
            "source": "derived_flap_portal_launch_config_events",
            "chain_id": 4663,
            "portal": FLAP_PORTAL.lower(),
            "events": Path(args.events).name,
            "fixed_supply_raw": str(1_000_000_000 * 10**18),
            "token_decimals": 18,
        },
    )
    incomplete_quotes = sum(row["quote_token"] is None for row in rows)
    print(
        json.dumps(
            {
                **manifest,
                "tokens": len(rows),
                "tokens_missing_quote_event": incomplete_quotes,
            },
            sort_keys=True,
        )
    )
    return 0





def cmd_rpc_pools_fun_registry_window(args: argparse.Namespace) -> int:
    """Build pools.fun launch registry from PartyFactory events."""
    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    started = time.monotonic()
    raw = rpc.iter_logs_chunked(
        args.from_block,
        args.to_block,
        address=POOLS_FUN_FACTORY,
        topics=[POOLS_FUN_TOKEN_LAUNCHED_TOPIC],
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )
    launches = [decode_pools_fun_launch(row) for row in raw]
    registry = build_pools_fun_registry(launches)
    manifest = write_jsonl_snapshot(
        registry,
        output=Path(args.out),
        provenance={
            "source": "pools_fun_party_factory_events",
            "chain_id": 4663,
            "factory": POOLS_FUN_FACTORY.lower(),
            "from_block": args.from_block,
            "to_block": args.to_block,
            "event_topic0": POOLS_FUN_TOKEN_LAUNCHED_TOPIC,
            "fixed_supply_raw": str(1_000_000_000 * 10**18),
            "token_decimals": 18,
        },
    )
    print(json.dumps({
        **manifest,
        "launches": len(registry),
        "quote_tokens": sorted({row["quote_token"] for row in registry}),
        "requests_made": rpc.requests_made,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }, sort_keys=True))
    return 0


def cmd_rpc_pools_fun_v3_tape(args: argparse.Namespace) -> int:
    """Acquire shared V3 Initialize/Swap tape for pools.fun pools."""
    registry = _load_jsonl(args.registry)
    pools = sorted({row["pool"].lower() for row in registry})
    if not pools:
        raise SystemExit("pools.fun registry contains no pools")
    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    started = time.monotonic()
    raw = rpc.iter_logs_chunked(
        args.from_block,
        args.to_block,
        address=pools,
        topics=[[V3_INITIALIZE_TOPIC, V3_SWAP_TOPIC]],
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )
    initializes = []
    swaps = []
    for log in raw:
        if log.topics[0] == V3_INITIALIZE_TOPIC:
            initializes.append(decode_v3_pool_initialized(log))
        elif log.topics[0] == V3_SWAP_TOPIC:
            swaps.append(decode_v3_swap(log))

    init_manifest = write_jsonl_snapshot(
        initializes,
        output=Path(args.initialize_out),
        provenance={
            "source": "evm_json_rpc",
            "chain_id": 4663,
            "venue": "pools.fun",
            "registry": Path(args.registry).name,
            "registered_pools": len(pools),
            "from_block": args.from_block,
            "to_block": args.to_block,
            "event_topic0": V3_INITIALIZE_TOPIC,
        },
    )
    swap_manifest = write_jsonl_snapshot(
        swaps,
        output=Path(args.swap_out),
        provenance={
            "source": "evm_json_rpc",
            "chain_id": 4663,
            "venue": "pools.fun",
            "registry": Path(args.registry).name,
            "registered_pools": len(pools),
            "from_block": args.from_block,
            "to_block": args.to_block,
            "event_topic0_or": [V3_INITIALIZE_TOPIC, V3_SWAP_TOPIC],
        },
    )
    print(json.dumps({
        "initializes": init_manifest,
        "swaps": swap_manifest,
        "registered_pools": len(pools),
        "initialized_pools": len({row.pool for row in initializes}),
        "swapped_pools": len({row.pool for row in swaps}),
        "requests_made": rpc.requests_made,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }, sort_keys=True))
    return 0


def cmd_rpc_pools_fun_market_cap_window(args: argparse.Namespace) -> int:
    """Price pools.fun V3 launches and emit $100k eligibility."""
    if args.from_block <= 0:
        raise SystemExit("from-block must be > 0")
    registry = _load_jsonl(args.registry)
    initializes = _load_jsonl(args.initializes)
    swaps = _load_jsonl(args.swaps)
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
    anchors = list(reconstruct_v3_price_points(
        rpc,
        token=ROBINHOOD_WETH,
        quote_token=ROBINHOOD_USDG,
        pool=args.usd_anchor_pool,
        from_block=args.from_block,
        to_block=args.to_block,
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    ))
    quote_tokens = {row["quote_token"].lower() for row in registry}
    quote_decimals = {
        ROBINHOOD_WETH.lower(): 18,
        ROBINHOOD_USDG.lower(): 18,
    }
    for quote in sorted(quote_tokens):
        if quote not in quote_decimals:
            quote_decimals[quote] = read_erc20_static(
                rpc, quote, block=args.from_block - 1
            ).decimals

    points = build_v3_launchpad_market_cap_points(
        registry,
        initializes,
        swaps,
        anchors,
        initial_weth_usd=initial_weth_usd,
        quote_decimals=quote_decimals,
        initial_quote_usd=initial_quote_usd,
        quote_usd_updates=quote_usd_updates,
    )
    point_manifest = write_jsonl_snapshot(
        points,
        output=Path(args.out),
        provenance={
            "source": "derived_pools_fun_v3_initialize_and_swaps",
            "chain_id": 4663,
            "registry": Path(args.registry).name,
            "initializes": Path(args.initializes).name,
            "swaps": Path(args.swaps).name,
            "from_block": args.from_block,
            "to_block": args.to_block,
            "usd_anchor_pool": args.usd_anchor_pool.lower(),
            "market_cap_math": "raw_quote_per_raw_token * supply_raw / 10**quote_decimals",
        },
    )
    summary = summarize_v3_launchpad_market_caps(points)
    summary_manifest = write_jsonl_snapshot(
        summary,
        output=Path(args.summary_out),
        provenance={
            "source": "derived_pools_fun_v3_market_cap_points",
            "market_cap_points_sha256": point_manifest["sha256"],
            "eligibility_threshold_usd": "100000",
            "threshold_semantics": "reached at least once from V3 initialization onward",
        },
    )
    print(json.dumps({
        "market_cap_points": point_manifest,
        "token_summary": summary_manifest,
        "launches": len(registry),
        "tokens_with_price_points": len(summary),
        "tokens_priced": sum(row["priced_points"] > 0 for row in summary),
        "tokens_crossed_100k": sum(bool(row["crossed_100k"]) for row in summary),
        "initial_weth_usd": str(initial_weth_usd),
        "requests_made": rpc.requests_made,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }, sort_keys=True))
    return 0


def cmd_rpc_pools_trade_registry_window(args: argparse.Namespace) -> int:
    """Build pools.trade instant-launch registry from upstream event tapes."""
    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    started = time.monotonic()

    launchers = [
        POOLS_TRADE_LAUNCHER_CURRENT,
        POOLS_TRADE_LAUNCHER_ORIGINAL,
    ]
    launcher_logs = list(
        rpc.iter_logs_chunked(
            args.from_block,
            args.to_block,
            address=launchers,
            topics=[[
                POOLS_TRADE_TOKEN_CREATED_TOPIC,
                POOLS_TRADE_TOKEN_DISTRIBUTED_TOPIC,
            ]],
            chunk_size=args.chunk_size,
            min_chunk_size=args.min_chunk_size,
        )
    )
    created = [
        decode_pools_trade_token_created(row)
        for row in launcher_logs
        if row.topics[0] == POOLS_TRADE_TOKEN_CREATED_TOPIC
    ]
    distributed = [
        decode_pools_trade_token_distributed(row)
        for row in launcher_logs
        if row.topics[0] == POOLS_TRADE_TOKEN_DISTRIBUTED_TOPIC
    ]

    strategy_logs = list(
        rpc.iter_logs_chunked(
            args.from_block,
            args.to_block,
            address=list(POOLS_TRADE_INSTANT_STRATEGIES),
            topics=[POOLS_TRADE_TOKEN_LAUNCHED_TOPIC],
            chunk_size=args.chunk_size,
            min_chunk_size=args.min_chunk_size,
        )
    )
    launched = [
        decode_pools_trade_token_launched(row)
        for row in strategy_logs
    ]
    registry = build_pools_trade_instant_registry(
        created,
        distributed,
        launched,
    )
    instant_tokens = {row["token"] for row in registry}
    created_tokens = {row.token for row in created}
    crowd_or_other = sorted(created_tokens - instant_tokens)

    manifest = write_jsonl_snapshot(
        registry,
        output=Path(args.out),
        provenance={
            "source": "uniswap_liquidity_launcher_events",
            "chain_id": 4663,
            "venue": "pools.trade",
            "launchers": [address.lower() for address in launchers],
            "instant_strategies": [
                address.lower() for address in POOLS_TRADE_INSTANT_STRATEGIES
            ],
            "from_block": args.from_block,
            "to_block": args.to_block,
            "token_created_topic": POOLS_TRADE_TOKEN_CREATED_TOPIC,
            "token_distributed_topic": POOLS_TRADE_TOKEN_DISTRIBUTED_TOPIC,
            "token_launched_topic": POOLS_TRADE_TOKEN_LAUNCHED_TOPIC,
        },
    )
    print(
        json.dumps(
            {
                **manifest,
                "created_tokens": len(created_tokens),
                "instant_launches": len(registry),
                "non_instant_creations": len(crowd_or_other),
                "non_instant_examples": crowd_or_other[:20],
                "requests_made": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_rpc_pools_trade_v4_tape(args: argparse.Namespace) -> int:
    """Acquire V4 Initialize + Swap tapes for pools.trade instant pools."""
    registry = _load_jsonl(args.registry)
    pool_ids = {row["pool_id"].lower() for row in registry}
    if not pool_ids:
        raise SystemExit("pools.trade registry contains no pool ids")

    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    started = time.monotonic()
    raw = rpc.iter_logs_chunked(
        args.from_block,
        args.to_block,
        address=UNISWAP_V4_POOL_MANAGER,
        topics=[[V4_INITIALIZE_TOPIC, V4_SWAP_TOPIC]],
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )
    initializes = []
    swaps = []
    all_initialize = 0
    all_swaps = 0
    for log in raw:
        if log.topics[0] == V4_INITIALIZE_TOPIC:
            all_initialize += 1
            row = decode_v4_pool_initialized(log)
            if row.pool_id in pool_ids:
                initializes.append(row)
        elif log.topics[0] == V4_SWAP_TOPIC:
            all_swaps += 1
            row = decode_v4_swap(log)
            if row.pool_id in pool_ids:
                swaps.append(row)

    init_manifest = write_jsonl_snapshot(
        initializes,
        output=Path(args.initialize_out),
        provenance={
            "source": "evm_json_rpc",
            "chain_id": 4663,
            "venue": "pools.trade",
            "pool_manager": UNISWAP_V4_POOL_MANAGER.lower(),
            "registry": Path(args.registry).name,
            "registered_pool_ids": len(pool_ids),
            "from_block": args.from_block,
            "to_block": args.to_block,
            "event_topic0": V4_INITIALIZE_TOPIC,
        },
    )
    swap_manifest = write_jsonl_snapshot(
        swaps,
        output=Path(args.swap_out),
        provenance={
            "source": "evm_json_rpc",
            "chain_id": 4663,
            "venue": "pools.trade",
            "pool_manager": UNISWAP_V4_POOL_MANAGER.lower(),
            "registry": Path(args.registry).name,
            "registered_pool_ids": len(pool_ids),
            "from_block": args.from_block,
            "to_block": args.to_block,
            "event_topic0_or": [V4_INITIALIZE_TOPIC, V4_SWAP_TOPIC],
        },
    )
    print(
        json.dumps(
            {
                "initializes": init_manifest,
                "swaps": swap_manifest,
                "all_v4_initializes": all_initialize,
                "all_v4_swaps": all_swaps,
                "matched_pool_ids_initialized": len({
                    row.pool_id for row in initializes
                }),
                "matched_pool_ids_swapped": len({
                    row.pool_id for row in swaps
                }),
                "requests_made": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_rpc_pools_trade_market_cap_window(args: argparse.Namespace) -> int:
    """Price pools.trade instant V4 launches and emit $100k eligibility."""
    if args.from_block <= 0:
        raise SystemExit("from-block must be > 0")
    registry = _load_jsonl(args.registry)
    initializes = _load_jsonl(args.initializes)
    swaps = _load_jsonl(args.swaps)
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

    zero = "0x" + "00" * 20
    quote_tokens = {row["quote_token"].lower() for row in registry}
    quote_decimals = {zero: 18, ROBINHOOD_WETH.lower(): 18}
    for quote in sorted(quote_tokens):
        if quote in quote_decimals:
            continue
        quote_decimals[quote] = read_erc20_static(
            rpc, quote, block=args.from_block - 1
        ).decimals

    points = build_pools_trade_v4_market_cap_points(
        registry,
        initializes,
        swaps,
        anchor_points,
        initial_weth_usd=initial_weth_usd,
        quote_decimals=quote_decimals,
        initial_quote_usd=initial_quote_usd,
        quote_usd_updates=quote_usd_updates,
    )
    point_manifest = write_jsonl_snapshot(
        points,
        output=Path(args.out),
        provenance={
            "source": "derived_pools_trade_v4_initialize_and_swaps",
            "chain_id": 4663,
            "registry": Path(args.registry).name,
            "initializes": Path(args.initializes).name,
            "swaps": Path(args.swaps).name,
            "from_block": args.from_block,
            "to_block": args.to_block,
            "usd_anchor_pool": args.usd_anchor_pool.lower(),
            "market_cap_math": "raw_quote_per_raw_token * supply_raw / 10**quote_decimals",
        },
    )
    summary = summarize_pools_trade_market_caps(points)
    summary_manifest = write_jsonl_snapshot(
        summary,
        output=Path(args.summary_out),
        provenance={
            "source": "derived_pools_trade_v4_market_cap_points",
            "market_cap_points_sha256": point_manifest["sha256"],
            "eligibility_threshold_usd": "100000",
            "threshold_semantics": "reached at least once from V4 initialization onward",
        },
    )
    print(
        json.dumps(
            {
                "market_cap_points": point_manifest,
                "token_summary": summary_manifest,
                "instant_launches": len(registry),
                "tokens_with_price_points": len(summary),
                "tokens_priced": sum(row["priced_points"] > 0 for row in summary),
                "tokens_crossed_100k": sum(
                    bool(row["crossed_100k"]) for row in summary
                ),
                "quote_decimals": quote_decimals,
                "initial_weth_usd": str(initial_weth_usd),
                "requests_made": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0



def cmd_rpc_hood_fun_tape(args: argparse.Namespace) -> int:
    """Acquire one shared current-generation hood.fun launch/curve tape."""
    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    started = time.monotonic()
    raw = rpc.iter_logs_chunked(
        args.from_block,
        args.to_block,
        address=HOOD_FUN_CURRENT,
        topics=[list(HOOD_FUN_CURVE_TOPICS)],
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )
    counters: dict[str, int] = {}

    def decoded():
        for log in raw:
            row = decode_hood_fun_event(log)
            counters[row.event_type] = counters.get(row.event_type, 0) + 1
            yield row

    manifest = write_jsonl_snapshot(
        decoded(),
        output=Path(args.out),
        provenance={
            "source": "evm_json_rpc",
            "chain_id": 4663,
            "protocol": "hood_fun_current_curve_tape",
            "contract": HOOD_FUN_CURRENT.lower(),
            "event_topic0_or": list(HOOD_FUN_CURVE_TOPICS),
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
                "event_counts": counters,
                "requests_made": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_hood_fun_registry(args: argparse.Namespace) -> int:
    """Build a persistent current-generation hood.fun launch registry."""
    events = [HoodFunEvent(**row) for row in _load_jsonl(args.events)]
    rows = build_hood_fun_launch_registry(events)
    manifest = write_jsonl_snapshot(
        rows,
        output=Path(args.out),
        provenance={
            "source": "derived_hood_fun_token_created",
            "chain_id": 4663,
            "contract": HOOD_FUN_CURRENT.lower(),
            "events": Path(args.events).name,
            "supply_semantics": (
                "TokenCreated curve inventory is 80% of chosen total supply; "
                "supply_raw = curve_inventory_raw * 5 / 4"
            ),
            "token_decimals": 18,
        },
    )
    print(
        json.dumps(
            {
                **manifest,
                "tokens": len(rows),
                "supply_shapes": len({row["supply_raw"] for row in rows}),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_rpc_hood_fun_curve_market_cap_window(args: argparse.Namespace) -> int:
    """Price hood.fun virtual reserves and emit $100k eligibility."""
    if args.from_block <= 0:
        raise SystemExit("from-block must be > 0")
    events = [HoodFunEvent(**row) for row in _load_jsonl(args.events)]
    registry = _load_jsonl(args.registry)

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
    points = build_hood_fun_curve_market_cap_points(
        events,
        registry,
        anchor_points,
        initial_weth_usd=initial_weth_usd,
    )
    point_manifest = write_jsonl_snapshot(
        points,
        output=Path(args.out),
        provenance={
            "source": "derived_hood_fun_virtual_reserves",
            "chain_id": 4663,
            "contract": HOOD_FUN_CURRENT.lower(),
            "events": Path(args.events).name,
            "registry": Path(args.registry).name,
            "from_block": args.from_block,
            "to_block": args.to_block,
            "usd_anchor_pool": args.usd_anchor_pool.lower(),
            "price_semantics": (
                "authoritative post-trade virtual ETH / virtual token reserve"
            ),
        },
    )
    summary = summarize_hood_fun_curve_market_caps(points)
    summary_manifest = write_jsonl_snapshot(
        summary,
        output=Path(args.summary_out),
        provenance={
            "source": "derived_hood_fun_curve_market_cap_points",
            "market_cap_points_sha256": point_manifest["sha256"],
            "eligibility_threshold_usd": "100000",
            "threshold_semantics": "reached at least once on hood.fun bonding curve",
        },
    )
    print(
        json.dumps(
            {
                "market_cap_points": point_manifest,
                "token_summary": summary_manifest,
                "registry_tokens": len(registry),
                "tokens_with_price_points": len(summary),
                "tokens_priced": sum(row["priced_points"] > 0 for row in summary),
                "tokens_crossed_100k": sum(
                    bool(row["crossed_100k"]) for row in summary
                ),
                "initial_weth_usd": str(initial_weth_usd),
                "requests_made": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_rpc_trench_tape(args: argparse.Namespace) -> int:
    """Acquire one shared trench.today launch/bonding-curve tape."""
    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    started = time.monotonic()
    raw = rpc.iter_logs_chunked(
        args.from_block,
        args.to_block,
        address=TRENCH_MANAGER,
        topics=[list(TRENCH_CURVE_TOPICS)],
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )
    counters: dict[str, int] = {}

    def decoded():
        for log in raw:
            row = decode_trench_event(log)
            counters[row.event_type] = counters.get(row.event_type, 0) + 1
            yield row

    manifest = write_jsonl_snapshot(
        decoded(),
        output=Path(args.out),
        provenance={
            "source": "evm_json_rpc",
            "chain_id": 4663,
            "protocol": "trench_today_shared_curve_tape",
            "manager": TRENCH_MANAGER.lower(),
            "event_topic0_or": list(TRENCH_CURVE_TOPICS),
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
                "event_counts": counters,
                "requests_made": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_trench_registry(args: argparse.Namespace) -> int:
    """Build a persistent trench.today launch registry from a raw tape."""
    events = [TrenchEvent(**row) for row in _load_jsonl(args.events)]
    rows = build_trench_launch_registry(events)
    manifest = write_jsonl_snapshot(
        rows,
        output=Path(args.out),
        provenance={
            "source": "derived_trench_today_token_create",
            "chain_id": 4663,
            "manager": TRENCH_MANAGER.lower(),
            "events": Path(args.events).name,
            "fixed_supply_raw": str(1_000_000_000 * 10**18),
            "token_decimals": 18,
        },
    )
    print(
        json.dumps(
            {
                **manifest,
                "tokens": len(rows),
                "quote_tokens": sorted({row["quote_token"] for row in rows}),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_rpc_trench_curve_market_cap_window(args: argparse.Namespace) -> int:
    """Price trench.today Sync reserves and emit $100k eligibility."""
    if args.from_block <= 0:
        raise SystemExit("from-block must be > 0")
    events = [TrenchEvent(**row) for row in _load_jsonl(args.events)]
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
    points = list(
        build_trench_curve_market_cap_points(
            events,
            registry,
            anchor_points,
            initial_weth_usd=initial_weth_usd,
            initial_quote_usd=initial_quote_usd,
            quote_usd_updates=quote_usd_updates,
        )
    )
    point_manifest = write_jsonl_snapshot(
        points,
        output=Path(args.out),
        provenance={
            "source": "derived_trench_today_sync_virtual_reserves",
            "chain_id": 4663,
            "manager": TRENCH_MANAGER.lower(),
            "events": Path(args.events).name,
            "registry": Path(args.registry).name,
            "from_block": args.from_block,
            "to_block": args.to_block,
            "usd_anchor_pool": args.usd_anchor_pool.lower(),
            "price_semantics": "virtualQuote / virtualToken from authoritative post-trade Sync",
            "supply_semantics": "fixed 1B supply, 18 decimals, validated on Robinhood mainnet launch samples",
        },
    )
    summary = summarize_trench_curve_market_caps(points)
    summary_manifest = write_jsonl_snapshot(
        summary,
        output=Path(args.summary_out),
        provenance={
            "source": "derived_trench_today_curve_market_cap_points",
            "market_cap_points_sha256": point_manifest["sha256"],
            "eligibility_threshold_usd": "100000",
            "threshold_semantics": "reached at least once on trench.today bonding curve",
        },
    )
    print(
        json.dumps(
            {
                "market_cap_points": point_manifest,
                "token_summary": summary_manifest,
                "tokens_with_syncs": len(summary),
                "tokens_priced": sum(row["priced_points"] > 0 for row in summary),
                "tokens_crossed_100k_on_curve": sum(
                    bool(row["crossed_100k"]) for row in summary
                ),
                "initial_weth_usd": str(initial_weth_usd),
                "requests_made": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_rpc_flap_tape(args: argparse.Namespace) -> int:
    """Acquire one shared Flap launch/bonding-curve lifecycle tape."""
    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    started = time.monotonic()
    raw = rpc.iter_logs_chunked(
        args.from_block,
        args.to_block,
        address=FLAP_PORTAL,
        topics=[list(FLAP_RECONSTRUCTION_TOPICS)],
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )
    counters: dict[str, int] = {}

    def decoded():
        for log in raw:
            row = decode_flap_event(log)
            counters[row.event_type] = counters.get(row.event_type, 0) + 1
            yield row

    manifest = write_jsonl_snapshot(
        decoded(),
        output=Path(args.out),
        provenance={
            "source": "evm_json_rpc",
            "chain_id": 4663,
            "protocol": "flap_portal_shared_tape",
            "portal": FLAP_PORTAL.lower(),
            "event_topic0_or": list(FLAP_RECONSTRUCTION_TOPICS),
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
                "event_counts": counters,
                "requests_made": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_rpc_flap_curve_market_cap_window(args: argparse.Namespace) -> int:
    """Price Flap bonding-curve trades and emit $100k eligibility."""
    if args.from_block <= 0:
        raise SystemExit("from-block must be > 0")
    event_rows = _load_jsonl(args.events)
    events = [FlapEvent(**row) for row in event_rows]
    launch_registry = _load_jsonl(args.registry)
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
    points = list(
        build_flap_curve_market_cap_points(
            events,
            anchor_points,
            initial_weth_usd=initial_weth_usd,
            initial_quote_usd=initial_quote_usd,
            quote_usd_updates=quote_usd_updates,
            launch_registry=launch_registry,
        )
    )
    point_manifest = write_jsonl_snapshot(
        points,
        output=Path(args.out),
        provenance={
            "source": "derived_flap_portal_trade_post_price",
            "chain_id": 4663,
            "portal": FLAP_PORTAL.lower(),
            "events": Path(args.events).name,
            "registry": Path(args.registry).name,
            "from_block": args.from_block,
            "to_block": args.to_block,
            "usd_anchor_pool": args.usd_anchor_pool.lower(),
            "price_semantics": "postPrice is quote-token units with 18 decimals",
            "supply_semantics": "fixed 1B supply, 18 decimals, validated on Robinhood mainnet launch samples",
            "oracle_state": (
                Path(args.oracle_state).name if args.oracle_state else None
            ),
            "oracle_events": (
                Path(args.oracle_events).name if args.oracle_events else None
            ),
        },
    )
    summary = summarize_flap_curve_market_caps(points)
    summary_manifest = write_jsonl_snapshot(
        summary,
        output=Path(args.summary_out),
        provenance={
            "source": "derived_flap_curve_market_cap_points",
            "market_cap_points_sha256": point_manifest["sha256"],
            "eligibility_threshold_usd": "100000",
            "threshold_semantics": "reached at least once on Flap bonding curve",
        },
    )
    print(
        json.dumps(
            {
                "market_cap_points": point_manifest,
                "token_summary": summary_manifest,
                "tokens_with_curve_trades": len(summary),
                "tokens_priced": sum(r["priced_points"] > 0 for r in summary),
                "tokens_crossed_100k_on_curve": sum(
                    bool(r["crossed_100k"]) for r in summary
                ),
                "unpriced_tokens": sum(r["priced_points"] == 0 for r in summary),
                "initial_weth_usd": str(initial_weth_usd),
                "requests_made": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_rpc_pons_quote_causality(args: argparse.Namespace) -> int:
    """Check Stock Token USD feed state immediately before first Pons use."""
    quote_rows = _load_jsonl(args.quote_registry)
    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    started = time.monotonic()
    rows = audit_pons_quote_causality(rpc, quote_rows)
    manifest = write_jsonl_snapshot(
        rows,
        output=Path(args.out),
        provenance={
            "source": "archive_chainlink_state_before_first_pons_quote_use",
            "chain_id": 4663,
            "quote_registry": Path(args.quote_registry).name,
        },
    )
    ready = sum(bool(row["causal_ready"]) for row in rows)
    print(json.dumps({
        **manifest,
        "stock_quote_assets": len(rows),
        "causal_ready": ready,
        "blocked": len(rows) - ready,
        "blocked_tokens": [
            row["quote_token"] for row in rows if not row["causal_ready"]
        ],
        "requests_made": rpc.requests_made,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }, sort_keys=True))
    return 0


def cmd_rpc_pons_unpriced_quote_v3_routes(
    args: argparse.Namespace,
) -> int:
    """Audit causal V3 USDG/WETH routes for feedless Pons quote assets."""
    quote_rows = _load_jsonl(args.quote_registry)
    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    started = time.monotonic()
    rows = audit_unpriced_v3_quote_routes(rpc, quote_rows)
    manifest = write_jsonl_snapshot(
        rows,
        output=Path(args.out),
        provenance={
            "source": "point_in_time_uniswap_v3_factory_route_audit",
            "chain_id": 4663,
            "quote_registry": Path(args.quote_registry).name,
            "factory": UNISWAP_V3_FACTORY.lower(),
            "anchors": [
                ROBINHOOD_USDG.lower(),
                ROBINHOOD_WETH.lower(),
            ],
            "fee_tiers": [100, 500, 3000, 10000],
            "causal_semantics": (
                "factory/pool state read at first Pons use block minus one"
            ),
        },
    )
    ready = [row for row in rows if row["v3_causal_ready"]]
    print(json.dumps({
        **manifest,
        "unpriced_quote_assets": len(rows),
        "v3_causal_ready": len(ready),
        "direct_usdg_ready": sum(
            bool(row["direct_usdg_ready"]) for row in rows
        ),
        "direct_weth_ready": sum(
            bool(row["direct_weth_ready"]) for row in rows
        ),
        "still_unresolved": len(rows) - len(ready),
        "unresolved_tokens": [
            row["quote_token"]
            for row in rows
            if not row["v3_causal_ready"]
        ],
        "requests_made": rpc.requests_made,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }, sort_keys=True))
    return 0


def cmd_pons_select_v3_quote_routes(args: argparse.Namespace) -> int:
    """Freeze one deterministic V3 fallback route per covered quote asset."""
    audit = _load_jsonl(args.audit)
    routes = select_v3_quote_routes(audit)
    manifest = write_jsonl_snapshot(
        routes,
        output=Path(args.out),
        provenance={
            "source": "deterministic_selection_from_v3_quote_route_audit",
            "chain_id": 4663,
            "audit": Path(args.audit).name,
            "selection_policy": (
                "prefer direct USDG; otherwise WETH; within pair choose "
                "highest activation liquidity then lower fee"
            ),
        },
    )
    print(json.dumps({
        **manifest,
        "selected_routes": len(routes),
        "covered_launches": sum(int(row["launches"]) for row in routes),
        "direct_usdg_routes": sum(
            row["route_type"] == "uniswap_v3_direct_usdg"
            for row in routes
        ),
        "direct_weth_routes": sum(
            row["route_type"] == "uniswap_v3_direct_weth"
            for row in routes
        ),
    }, sort_keys=True))
    return 0


def cmd_pons_v3_quote_usd_tape(args: argparse.Namespace) -> int:
    """Convert selected V3 fallback routes into generic causal USD state/tape."""
    routes = _load_jsonl(args.routes)
    initial = json.loads(Path(args.anchor_initial).read_text())
    initial_weth_usd = Decimal(initial["weth_usd"])
    if initial_weth_usd <= 0:
        raise SystemExit("anchor initial WETH/USD must be positive")

    states = build_v3_route_initial_usd_states(routes)
    state_manifest = write_jsonl_snapshot(
        states,
        output=Path(args.state_out),
        provenance={
            "source": "selected_v3_route_state_before_first_pons_use",
            "chain_id": 4663,
            "routes": Path(args.routes).name,
            "anchor_initial": Path(args.anchor_initial).name,
        },
    )
    updates = build_v3_route_usd_updates(
        routes,
        _iter_jsonl(args.v3_events),
        _iter_jsonl(args.anchor_events),
        initial_weth_usd=initial_weth_usd,
    )
    update_manifest = write_jsonl_snapshot(
        updates,
        output=Path(args.out),
        provenance={
            "source": "selected_v3_route_swap_close_usd_tape",
            "chain_id": 4663,
            "routes": Path(args.routes).name,
            "v3_events": Path(args.v3_events).name,
            "anchor_events": Path(args.anchor_events).name,
            "anchor_initial": Path(args.anchor_initial).name,
        },
    )
    print(json.dumps({
        "initial_states": state_manifest,
        "updates": update_manifest,
        "selected_routes": len(routes),
    }, sort_keys=True))
    return 0


def cmd_pons_quote_audit(args: argparse.Namespace) -> int:
    """Classify every Pons pair token against canonical USD pricing sources."""
    registry = _load_jsonl(args.registry)
    assets = RobinhoodAssetsClient(timeout=args.timeout, attempts=args.attempts)
    directory = ChainlinkDirectoryClient(
        timeout=args.timeout,
        attempts=args.attempts,
    )
    rows = build_pons_quote_registry(
        registry,
        assets_client=assets,
        directory_client=directory,
    )
    manifest = write_jsonl_snapshot(
        rows,
        output=Path(args.out),
        provenance={
            "source": "pons_registry_plus_robinhood_assets_plus_chainlink_directory",
            "chain_id": 4663,
            "registry": Path(args.registry).name,
            "robinhood_assets_url": assets.url,
            "chainlink_directory_url": directory.url,
            "chainlink_directory_sha256": directory.last_sha256,
        },
    )
    status_counts: dict[str, int] = {}
    launches_by_status: dict[str, int] = {}
    for row in rows:
        status = row["pricing_status"]
        status_counts[status] = status_counts.get(status, 0) + 1
        launches_by_status[status] = (
            launches_by_status.get(status, 0) + int(row["launches"])
        )
    blocking = [
        row for row in rows
        if row["pricing_status"] in {
            "unsupported_quote",
            "missing_chainlink_feed",
        }
    ]
    print(json.dumps({
        **manifest,
        "quote_assets": len(rows),
        "status_counts": status_counts,
        "launches_by_status": launches_by_status,
        "blocking_quote_assets": len(blocking),
        "blocking_tokens": [row["quote_token"] for row in blocking],
        "rhj_requests": assets.requests_made,
        "chainlink_directory_requests": directory.requests_made,
    }, sort_keys=True))
    return 0


def cmd_rpc_pons_stock_oracle_lifecycle(args: argparse.Namespace) -> int:
    """Build one shared Chainlink USD tape from each quote's first Pons use."""
    quote_rows = _load_jsonl(args.quote_registry)
    specs = []
    for source in quote_rows:
        if source["pricing_status"] not in CHAINLINK_PRICED_STATUSES:
            continue
        actual_first = int(source["first_launch_block"])
        if actual_first > args.to_block:
            continue
        row = dict(source)
        if args.from_block is not None:
            row["first_launch_block"] = max(actual_first, args.from_block)
        specs.append(row)
    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    started = time.monotonic()
    states, updates = reconstruct_staggered_chainlink_usd_tapes(
        rpc,
        feeds=specs,
        to_block=args.to_block,
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )
    state_manifest = write_jsonl_snapshot(
        states,
        output=Path(args.state_out),
        provenance={
            "source": "chainlink_state_before_each_quote_first_pons_use",
            "chain_id": 4663,
            "quote_registry": Path(args.quote_registry).name,
            "from_block": args.from_block,
            "to_block": args.to_block,
        },
    )
    update_manifest = write_jsonl_snapshot(
        updates,
        output=Path(args.out),
        provenance={
            "source": "shared_staggered_chainlink_answer_updated_tape",
            "chain_id": 4663,
            "quote_registry": Path(args.quote_registry).name,
            "from_block": args.from_block,
            "to_block": args.to_block,
            "event_topic0": "0x0559884fd3a460db3073b7fc896cc77986f16e378210ded43186175bf646fc5f",
            "initial_chunk_size": args.chunk_size,
            "min_chunk_size": args.min_chunk_size,
        },
    )
    print(json.dumps({
        "initial_states": state_manifest,
        "updates": update_manifest,
        "stock_quote_assets": len(specs),
        "from_block": args.from_block,
        "first_activation_block": (
            min((int(row["first_launch_block"]) for row in specs), default=None)
        ),
        "requests_made": rpc.requests_made,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }, sort_keys=True))
    return 0


def cmd_rpc_v2_stock_oracle_window(args: argparse.Namespace) -> int:
    """Build official Pons Stock Token/USD initial states and update tape."""
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


def cmd_rpc_v2_transition_tape(args: argparse.Namespace) -> int:
    """Acquire V2 graduation and V4 registration control events in one scan."""
    registry = _load_jsonl(args.registry)
    tokens = {row["token"].lower() for row in registry}
    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    started = time.monotonic()

    raw = rpc.iter_logs_chunked(
        args.from_block,
        args.to_block,
        address=[PONS_V2_FACTORY, PONS_V2_MEME_HOOK],
        topics=[[V2_POOL_GRADUATED_TOPIC, PONS_V2_POOL_REGISTERED_TOPIC]],
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )

    graduations = []
    registrations = []
    unmatched = {"graduations": 0, "registrations": 0}
    for log in raw:
        topic0 = log.topics[0] if log.topics else None
        if topic0 == V2_POOL_GRADUATED_TOPIC:
            row = asdict(decode_v2_pool_graduation(log))
            if row["token"].lower() in tokens:
                graduations.append(row)
            else:
                unmatched["graduations"] += 1
        elif topic0 == PONS_V2_POOL_REGISTERED_TOPIC:
            row = asdict(decode_pons_v2_pool_registered(log))
            if row["token"].lower() in tokens:
                registrations.append(row)
            else:
                unmatched["registrations"] += 1
        else:
            raise ValueError(
                f"transition tape returned unexpected topic0 {topic0}"
            )

    graduations.sort(key=event_order)
    registrations.sort(key=event_order)
    graduation_manifest = write_jsonl_snapshot(
        graduations,
        output=Path(args.graduations_out),
        provenance={
            "source": "shared_v2_transition_raw_rpc_scan",
            "chain_id": 4663,
            "protocol": "pons_v2_graduations",
            "registry": Path(args.registry).name,
            "from_block": args.from_block,
            "to_block": args.to_block,
            "addresses": [
                PONS_V2_FACTORY.lower(),
                PONS_V2_MEME_HOOK.lower(),
            ],
            "topic0_or": [
                V2_POOL_GRADUATED_TOPIC,
                PONS_V2_POOL_REGISTERED_TOPIC,
            ],
        },
    )
    registration_manifest = write_jsonl_snapshot(
        registrations,
        output=Path(args.registrations_out),
        provenance={
            "source": "shared_v2_transition_raw_rpc_scan",
            "chain_id": 4663,
            "protocol": "pons_v2_v4_pool_registrations",
            "registry": Path(args.registry).name,
            "from_block": args.from_block,
            "to_block": args.to_block,
            "addresses": [
                PONS_V2_FACTORY.lower(),
                PONS_V2_MEME_HOOK.lower(),
            ],
            "topic0_or": [
                V2_POOL_GRADUATED_TOPIC,
                PONS_V2_POOL_REGISTERED_TOPIC,
            ],
        },
    )
    print(json.dumps({
        "graduations": graduation_manifest,
        "registrations": registration_manifest,
        "matched_graduations": len(graduations),
        "matched_registrations": len(registrations),
        "unmatched": unmatched,
        "requests_made": rpc.requests_made,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }, sort_keys=True))
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
                "protocol": "pons_v2_v4_price_events",
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
    # V4 Initialize and Swap both index poolId in topic1. Keep the exact
    # initialized price as part of the lifecycle instead of assuming the
    # PoolGraduated seed ratio is identical to the initialized pool price.
    global_pool_scan = bool(getattr(args, "global_pool_scan", False))
    topics = [[V4_INITIALIZE_TOPIC, V4_SWAP_TOPIC]]
    if not global_pool_scan:
        topics.append(sorted(pool_ids))
    raw = rpc.iter_logs_chunked(
        args.from_block,
        args.to_block,
        address=UNISWAP_V4_POOL_MANAGER,
        topics=topics,
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )
    counters = {
        "poolmanager_price_events_scanned": 0,
        "unmatched_pool_ids": 0,
        "matched_pons_v4_initializes": 0,
        "matched_pons_v4_swaps": 0,
    }
    matched_ids: set[str] = set()

    def decoded():
        for log in raw:
            counters["poolmanager_price_events_scanned"] += 1
            topic0 = log.topics[0] if log.topics else None
            if topic0 == V4_INITIALIZE_TOPIC:
                event = asdict(decode_v4_pool_initialized(log))
                event["event_type"] = "v4_initialize"
            elif topic0 == V4_SWAP_TOPIC:
                event = asdict(decode_v4_swap(log))
                event["event_type"] = "v4_swap"
            else:
                continue

            pool_id = event["pool_id"]
            if pool_id not in pool_ids:
                if not global_pool_scan:
                    raise ValueError(
                        "V4 server-side pool filter returned unknown id "
                        f"{pool_id}"
                    )
                counters["unmatched_pool_ids"] += 1
                continue

            if topic0 == V4_INITIALIZE_TOPIC:
                counters["matched_pons_v4_initializes"] += 1
            else:
                counters["matched_pons_v4_swaps"] += 1
            matched_ids.add(pool_id)
            yield event

    manifest = write_jsonl_snapshot(
        decoded(),
        output=Path(args.out),
        provenance={
            "source": "evm_json_rpc",
            "chain_id": 4663,
            "protocol": "pons_v2_v4_price_events",
            "pool_manager": UNISWAP_V4_POOL_MANAGER.lower(),
            "registrations": Path(args.registrations).name,
            "registered_pool_ids": len(pool_ids),
            "from_block": args.from_block,
            "to_block": args.to_block,
            "event_topic0_or": [V4_INITIALIZE_TOPIC, V4_SWAP_TOPIC],
            "event_topic1_pool_ids": (
                None if global_pool_scan else sorted(pool_ids)
            ),
            "pool_filter_mode": (
                "global_poolmanager_topic_then_registry"
                if global_pool_scan
                else "server_side_topic1_registered_pool_ids"
            ),
            "filter_semantics": (
                "single PoolManager + Initialize/Swap topic scan, then "
                "client-side frozen Pons registration membership"
                if global_pool_scan
                else "server-side topic0 Initialize/Swap OR and topic1 OR "
                "over registered Pons V2 pool ids"
            ),
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


def cmd_pons_v1_lifecycle_eligibility(args: argparse.Namespace) -> int:
    """Replay the full V1 V3 tape and keep per-token eligibility maxima."""
    registry = [
        row
        for row in _load_jsonl(args.registry)
        if row.get("version") == "v1"
    ]
    if not registry:
        raise SystemExit("registry contains no Pons V1 launches")

    initial = json.loads(Path(args.anchor_initial).read_text())
    initial_weth_usd = Decimal(initial["weth_usd"])
    if initial_weth_usd <= 0:
        raise SystemExit("anchor initial WETH/USD must be positive")

    quote_rows = _load_jsonl(args.quote_registry)
    quote_decimals_by_token = {
        row["quote_token"].lower(): int(row["quote_decimals"])
        for row in quote_rows
        if row.get("quote_decimals") is not None
    }
    weth_decimals = quote_decimals_by_token.get(ROBINHOOD_WETH.lower())
    usdg_decimals = quote_decimals_by_token.get(ROBINHOOD_USDG.lower())
    if weth_decimals is None or usdg_decimals is None:
        raise SystemExit("quote registry is missing WETH/USDG decimals")

    initial_quote_usd, quote_updates = _load_quote_usd_inputs(args)
    points = build_v1_market_cap_points(
        registry,
        _iter_jsonl(args.v3_events),
        _iter_jsonl(args.anchor_events),
        initial_weth_usd=initial_weth_usd,
        weth_decimals=weth_decimals,
        usdg_decimals=usdg_decimals,
        initial_quote_usd=initial_quote_usd,
        quote_usd_updates=quote_updates,
        quote_decimals_by_token=quote_decimals_by_token,
    )
    summary = summarize_v1_market_caps(points)

    registry_tokens = {row["token"].lower() for row in registry}
    summary_tokens = {row["token"].lower() for row in summary}
    missing = sorted(registry_tokens - summary_tokens)
    unexpected = sorted(summary_tokens - registry_tokens)
    if missing or unexpected:
        raise SystemExit(
            "V1 lifecycle summary does not exactly cover the frozen registry: "
            f"missing={len(missing)} unexpected={len(unexpected)} "
            f"missing_sample={missing[:10]} unexpected_sample={unexpected[:10]}"
        )

    manifest = write_jsonl_snapshot(
        summary,
        output=Path(args.out),
        provenance={
            "source": "streamed_full_v1_v3_replay_summary_only",
            "chain_id": 4663,
            "registry": Path(args.registry).name,
            "v3_events": Path(args.v3_events).name,
            "quote_registry": Path(args.quote_registry).name,
            "anchor_events": Path(args.anchor_events).name,
            "anchor_initial": Path(args.anchor_initial).name,
            "oracle_state": (
                None if not args.oracle_state
                else Path(args.oracle_state).name
            ),
            "oracle_events": (
                None if not args.oracle_events
                else Path(args.oracle_events).name
            ),
            "snapshot_head_block": args.snapshot_head,
            "eligibility_threshold_usd": "100000",
            "threshold_semantics": (
                "reached >=$100k market-cap proxy at least once in the "
                "complete observed Pons V1 V3 lifecycle"
            ),
        },
    )
    unpriced = [row for row in summary if int(row["priced_points"]) == 0]
    print(json.dumps({
        **manifest,
        "registry_tokens": len(registry),
        "tokens_priced": len(summary) - len(unpriced),
        "tokens_without_priced_points": len(unpriced),
        "tokens_crossed_100k": sum(
            bool(row["crossed_100k"]) for row in summary
        ),
        "unpriced_sample": [row["token"] for row in unpriced[:20]],
    }, sort_keys=True))
    return 0


def cmd_pons_v2_curve_eligibility(args: argparse.Namespace) -> int:
    """Replay the full V2 curve tape and keep only per-token eligibility maxima."""
    registry = _load_jsonl(args.registry)
    initial = json.loads(Path(args.anchor_initial).read_text())
    initial_weth_usd = Decimal(initial["weth_usd"])
    if initial_weth_usd <= 0:
        raise SystemExit("anchor initial WETH/USD must be positive")

    initial_quote_usd, quote_usd_updates = _load_quote_usd_inputs(args)
    points = build_v2_curve_market_cap_points(
        registry,
        _iter_jsonl(args.curve_events),
        _iter_jsonl(args.anchor_events),
        initial_weth_usd=initial_weth_usd,
        initial_quote_usd=initial_quote_usd,
        quote_usd_updates=quote_usd_updates,
    )
    summary = summarize_v2_curve_market_caps(points)
    manifest = write_jsonl_snapshot(
        summary,
        output=Path(args.out),
        provenance={
            "source": "streamed_full_v2_curve_replay_summary_only",
            "chain_id": 4663,
            "registry": Path(args.registry).name,
            "curve_events": Path(args.curve_events).name,
            "anchor_events": Path(args.anchor_events).name,
            "anchor_initial": Path(args.anchor_initial).name,
            "oracle_state": (
                None if not args.oracle_state else Path(args.oracle_state).name
            ),
            "oracle_events": (
                None if not args.oracle_events else Path(args.oracle_events).name
            ),
            "eligibility_threshold_usd": "100000",
            "threshold_semantics": (
                "reached at least once on complete reconstructed V2 curve path"
            ),
            "snapshot_head_block": args.snapshot_head,
            "materialization": "one summary row per token; no full point tape",
        },
    )
    priced = sum(row["priced_points"] > 0 for row in summary)
    crossed = sum(bool(row["crossed_100k"]) for row in summary)
    unsupported = [
        row["token"]
        for row in summary
        if row["priced_points"] == 0
    ]
    print(json.dumps({
        **manifest,
        "registry_tokens": len(registry),
        "summary_tokens": len(summary),
        "tokens_priced": priced,
        "tokens_crossed_100k_on_curve": crossed,
        "tokens_without_priced_points": len(unsupported),
        "unsupported_sample": unsupported[:20],
    }, sort_keys=True))
    return 0


def cmd_pons_v2_lifecycle_eligibility(args: argparse.Namespace) -> int:
    """Reduce the complete V2 curve -> graduation -> V4 path to token maxima."""
    registry = _load_jsonl(args.registry)
    curve_summary = _load_jsonl(args.curve_summary)
    graduations = _load_jsonl(args.graduations)
    registrations = _load_jsonl(args.registrations)
    initial = json.loads(Path(args.anchor_initial).read_text())
    initial_weth_usd = Decimal(initial["weth_usd"])
    if initial_weth_usd <= 0:
        raise SystemExit("anchor initial WETH/USD must be positive")

    seed_initial_quote_usd, seed_quote_updates = (
        _load_quote_usd_inputs(args)
    )

    seed_points = build_v2_graduation_seed_points(
        registry,
        graduations,
        _iter_jsonl(args.anchor_events),
        initial_weth_usd=initial_weth_usd,
        initial_quote_usd=seed_initial_quote_usd,
        quote_usd_updates=seed_quote_updates,
    )
    seed_summary = summarize_v2_curve_market_caps(seed_points)

    # The V4 builder needs an independent point-in-time USD timeline, so load
    # fresh iterators over the immutable quote source tapes.
    v4_initial_quote_usd, v4_quote_updates = _load_quote_usd_inputs(args)
    v4_points = build_v2_v4_market_cap_points(
        registry,
        registrations,
        _iter_jsonl(args.v4_events),
        _iter_jsonl(args.anchor_events),
        initial_weth_usd=initial_weth_usd,
        initial_quote_usd=v4_initial_quote_usd,
        quote_usd_updates=v4_quote_updates,
    )
    v4_summary = summarize_v2_curve_market_caps(v4_points)

    summary = merge_v2_lifecycle_market_cap_summaries(
        registry,
        curve_summary=curve_summary,
        seed_summary=seed_summary,
        v4_summary=v4_summary,
    )
    manifest = write_jsonl_snapshot(
        summary,
        output=Path(args.out),
        provenance={
            "source": "summary_only_complete_v2_lifecycle_replay",
            "chain_id": 4663,
            "snapshot_head_block": args.snapshot_head,
            "registry": Path(args.registry).name,
            "curve_summary": Path(args.curve_summary).name,
            "graduations": Path(args.graduations).name,
            "registrations": Path(args.registrations).name,
            "v4_events": Path(args.v4_events).name,
            "anchor_events": Path(args.anchor_events).name,
            "anchor_initial": Path(args.anchor_initial).name,
            "oracle_state": (
                None if not args.oracle_state else Path(args.oracle_state).name
            ),
            "oracle_events": (
                None if not args.oracle_events else Path(args.oracle_events).name
            ),
            "eligibility_threshold_usd": "100000",
            "threshold_semantics": (
                "reached at least once across complete V2 curve, graduation "
                "seed, V4 Initialize, or V4 Swap path"
            ),
            "materialization": "one final summary row per V2 launch",
        },
    )
    eligible = [row for row in summary if row["crossed_100k"]]
    phases = {}
    for row in eligible:
        phase = row["max_market_cap_phase"]
        phases[phase] = phases.get(phase, 0) + 1
    unpriced = [row for row in summary if row["priced_points"] == 0]
    print(json.dumps({
        **manifest,
        "registry_tokens": len(registry),
        "summary_tokens": len(summary),
        "graduated_tokens": len(seed_summary),
        "tokens_with_v4_points": len(v4_summary),
        "tokens_crossed_100k_full_lifecycle": len(eligible),
        "eligible_max_phase_counts": phases,
        "tokens_without_priced_points": len(unpriced),
        "unpriced_sample": [row["token"] for row in unpriced[:20]],
    }, sort_keys=True))
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
    curve_address_filter = (
        None if args.global_topic_scan else sorted(curve_to_token)
    )
    raw_tape = rpc.iter_logs_chunked(
        args.from_block,
        args.to_block,
        address=curve_address_filter,
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
            "server_side_curve_address_filter": curve_address_filter is not None,
            "curve_filter_mode": (
                "address_plus_topic"
                if curve_address_filter is not None
                else "global_topic_then_registry"
            ),
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
    """Build a reproducible Pons V1 registry across all factory generations."""
    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    if args.from_block < PONS_V1_FIRST_DEPLOYMENT_BLOCK:
        raise SystemExit(
            "from-block cannot precede first known Pons V1 deployment "
            f"{PONS_V1_FIRST_DEPLOYMENT_BLOCK}"
        )

    started = time.monotonic()
    factories = [address.lower() for address in PONS_V1_FACTORIES]
    topic_or = [
        V1_TOKEN_LAUNCHED_TOPIC,
        V1_LAUNCH_CONFIG_ADDED_TOPIC,
        V1_LAUNCH_CONFIG_UPDATED_TOPIC,
    ]
    raw = list(
        rpc.iter_logs_chunked(
            args.from_block,
            args.to_block,
            address=factories,
            topics=[topic_or],
            chunk_size=args.chunk_size,
            min_chunk_size=args.min_chunk_size,
        )
    )

    launch_config_ids_by_factory: dict[str, set[int]] = {}
    for row in raw:
        if not row.topics or row.topics[0] != V1_TOKEN_LAUNCHED_TOPIC:
            continue
        launch = decode_v1_launch(row)
        if launch.launch_config_id is None:
            continue
        launch_config_ids_by_factory.setdefault(
            row.address.lower(), set()
        ).add(launch.launch_config_id)

    bootstrap = []
    for factory, config_ids in sorted(launch_config_ids_by_factory.items()):
        deployment = PONS_V1_FACTORY_DEPLOYMENT_BLOCKS[factory]
        if args.from_block <= deployment:
            continue
        for config_id in sorted(config_ids):
            bootstrap.append(
                read_v1_launch_config_state(
                    rpc,
                    config_id,
                    block=args.from_block - 1,
                    factory=factory,
                )
            )

    rows = iter_enriched_v1_launches(raw, bootstrap_configs=bootstrap)
    manifest = write_jsonl_snapshot(
        rows,
        output=Path(args.out),
        provenance={
            "source": "evm_json_rpc",
            "chain_id": 4663,
            "protocol": "pons_v1_registry_multi_generation",
            "factories": factories,
            "factory_deployment_blocks": PONS_V1_FACTORY_DEPLOYMENT_BLOCKS,
            "from_block": args.from_block,
            "to_block": args.to_block,
            "topic0_or": topic_or,
            "bootstrap_config_ids_by_factory": {
                factory: sorted(ids)
                for factory, ids in launch_config_ids_by_factory.items()
            },
            "initial_chunk_size": args.chunk_size,
            "min_chunk_size": args.min_chunk_size,
            "token_decimals_source": (
                "PonsLauncherToken inherits OpenZeppelin ERC20 default 18 decimals"
            ),
        },
    )
    print(
        json.dumps(
            {
                **manifest,
                "factory_events": len(raw),
                "factories_with_launches": len(launch_config_ids_by_factory),
                "bootstrap_configs": len(bootstrap),
                "requests_made": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0






def cmd_pons_normalize_trades(args: argparse.Namespace) -> int:
    """Normalize Pons V1/V2/V4 events into one wallet-level trade schema."""
    points = _load_jsonl(args.points)
    trades = normalize_pons_trades(points)
    manifest = write_jsonl_snapshot(
        trades,
        output=Path(args.out),
        provenance={
            "source": "pons_transaction_enriched_market_points",
            "chain_id": 4663,
            "points": Path(args.points).name,
            "side_semantics": (
                "V2 curve uses explicit CurveBuy/CurveSell; V1/V4 use signed "
                "Pons-token pool leg"
            ),
            "wallet_identity": "transaction.from",
        },
    )
    side_counts: dict[str, int] = {}
    version_counts: dict[str, int] = {}
    for row in trades:
        side_counts[row["side"]] = side_counts.get(row["side"], 0) + 1
        version_counts[row["pons_version"]] = (
            version_counts.get(row["pons_version"], 0) + 1
        )
    print(
        json.dumps(
            {
                **manifest,
                "side_counts": side_counts,
                "version_counts": version_counts,
                "unique_tokens": len({row["token"] for row in trades}),
                "unique_initiators": len({
                    row["initiator"] for row in trades
                }),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_pons_trade_features(args: argparse.Namespace) -> int:
    """Build causal wallet participation features for normalized Pons trades."""
    trades = _load_jsonl(args.trades)
    rows = build_pons_causal_trade_features(trades)
    manifest = write_jsonl_snapshot(
        rows,
        output=Path(args.out),
        provenance={
            "source": "normalized_pons_wallet_trades",
            "chain_id": 4663,
            "trades": Path(args.trades).name,
            "feature_semantics": (
                "strictly causal cumulative participation; no fixed time "
                "window or dump threshold"
            ),
        },
    )
    print(
        json.dumps(
            {
                **manifest,
                "tokens": len({row["token"] for row in rows}),
                "trades": len(rows),
                "new_buyer_trades": sum(
                    bool(row["is_new_buyer"]) for row in rows
                ),
                "repeat_buyer_trades": sum(
                    bool(row["is_repeat_buyer"]) for row in rows
                ),
                "new_seller_trades": sum(
                    bool(row["is_new_seller"]) for row in rows
                ),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_rpc_pons_transaction_enrich(args: argparse.Namespace) -> int:
    """Attach batched transaction initiator identities to Pons research points."""
    points = _load_jsonl(args.points)
    hashes = sorted({
        row["transaction_hash"].lower()
        for row in points
    })

    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    started = time.monotonic()
    transaction_rows = fetch_transaction_identity_rows(
        rpc,
        hashes,
        batch_size=args.batch_size,
        min_batch_size=args.min_batch_size,
    )
    enriched = attach_pons_transaction_identities(
        points,
        transaction_rows,
    )

    transaction_manifest = write_jsonl_snapshot(
        transaction_rows,
        output=Path(args.transactions_out),
        provenance={
            "source": "eth_getTransactionByHash_batched",
            "chain_id": 4663,
            "points": Path(args.points).name,
            "unique_transactions": len(hashes),
            "requested_batch_size": args.batch_size,
            "min_batch_size": args.min_batch_size,
            "identity_semantics": (
                "initiator is transaction.from; pool/router event sender is "
                "not substituted for wallet identity"
            ),
        },
    )
    enriched_manifest = write_jsonl_snapshot(
        enriched,
        output=Path(args.out),
        provenance={
            "source": "pons_research_points_plus_transaction_identity",
            "chain_id": 4663,
            "points": Path(args.points).name,
            "transaction_map_sha256": transaction_manifest["sha256"],
        },
    )

    unique_initiators = {
        row["initiator"]
        for row in transaction_rows
    }
    destination_counts: dict[str, int] = {}
    for row in transaction_rows:
        destination = row["to"] or "<contract_creation>"
        destination_counts[destination] = (
            destination_counts.get(destination, 0) + 1
        )

    print(
        json.dumps(
            {
                "transactions": transaction_manifest,
                "enriched_points": enriched_manifest,
                "unique_transactions": len(transaction_rows),
                "unique_initiators": len(unique_initiators),
                "unique_destinations": len(destination_counts),
                "rpc_requests": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_rpc_pons_time_enrich(args: argparse.Namespace) -> int:
    """Attach exact Robinhood block timestamps to eligible Pons research data."""
    outcomes = _load_jsonl(args.outcomes)
    episodes = _load_jsonl(args.episodes)
    blocks = sorted({
        int(row["block_number"])
        for row in outcomes
    })

    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    started = time.monotonic()
    timestamp_rows = fetch_block_timestamp_rows(
        rpc,
        blocks,
        batch_size=args.batch_size,
        min_batch_size=args.min_batch_size,
    )
    enriched_outcomes = enrich_pons_points_with_time(
        outcomes,
        timestamp_rows,
    )
    enriched_episodes = enrich_pons_episodes_with_time(
        episodes,
        timestamp_rows,
    )

    timestamps_manifest = write_jsonl_snapshot(
        timestamp_rows,
        output=Path(args.timestamps_out),
        provenance={
            "source": "eth_getBlockByNumber_batched",
            "chain_id": 4663,
            "outcomes": Path(args.outcomes).name,
            "unique_blocks": len(blocks),
            "requested_batch_size": args.batch_size,
            "min_batch_size": args.min_batch_size,
        },
    )
    outcomes_manifest = write_jsonl_snapshot(
        enriched_outcomes,
        output=Path(args.out),
        provenance={
            "source": "pons_outcomes_plus_exact_block_timestamps",
            "chain_id": 4663,
            "outcomes": Path(args.outcomes).name,
            "timestamp_map_sha256": timestamps_manifest["sha256"],
        },
    )
    episodes_manifest = write_jsonl_snapshot(
        enriched_episodes,
        output=Path(args.episodes_out),
        provenance={
            "source": "pons_drawdown_episodes_plus_exact_block_timestamps",
            "chain_id": 4663,
            "episodes": Path(args.episodes).name,
            "timestamp_map_sha256": timestamps_manifest["sha256"],
        },
    )
    print(
        json.dumps(
            {
                "timestamps": timestamps_manifest,
                "outcomes": outcomes_manifest,
                "episodes": episodes_manifest,
                "unique_blocks": len(blocks),
                "eligible_points": len(enriched_outcomes),
                "drawdown_episodes": len(enriched_episodes),
                "rpc_requests": rpc.requests_made,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_pons_v2_graduated_registry(args: argparse.Namespace) -> int:
    """Reduce a full V2 registry to the tokens that actually graduated."""
    registry = _load_jsonl(args.registry)
    graduations = _load_jsonl(args.graduations)
    rows = filter_v2_registry_to_graduated(registry, graduations)
    manifest = write_jsonl_snapshot(
        rows,
        output=Path(args.out),
        provenance={
            "source": "pons_v2_registry_join_pool_graduated",
            "chain_id": 4663,
            "registry": Path(args.registry).name,
            "graduations": Path(args.graduations).name,
            "full_registry_tokens": len(registry),
            "graduated_tokens": len(rows),
        },
    )
    print(
        json.dumps(
            {
                **manifest,
                "full_registry_tokens": len(registry),
                "graduated_tokens": len(rows),
                "reduction_ratio": (
                    0 if not registry else len(rows) / len(registry)
                ),
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_pons_research_dataset(args: argparse.Namespace) -> int:
    """Merge Pons V1/V2 market paths into the canonical research dataset."""
    v1_rows = _load_jsonl(args.v1_points) if args.v1_points else []
    v2_curve_rows = (
        _load_jsonl(args.v2_curve_points) if args.v2_curve_points else []
    )
    v2_seed_rows = (
        _load_jsonl(args.v2_seed_points) if args.v2_seed_points else []
    )
    v2_v4_rows = (
        _load_jsonl(args.v2_v4_points) if args.v2_v4_points else []
    )

    points = build_pons_market_path(
        v1_rows=v1_rows,
        v2_curve_rows=v2_curve_rows,
        v2_seed_rows=v2_seed_rows,
        v2_v4_rows=v2_v4_rows,
    )
    summary = summarize_pons_eligibility(points)
    eligible = eligible_pons_tokens(summary)
    annotated = annotate_pons_drawdowns_and_future_returns(
        points,
        eligible_tokens=eligible,
    )
    episodes = extract_pons_drawdown_episodes(annotated)

    path_manifest = write_jsonl_snapshot(
        points,
        output=Path(args.path_out),
        provenance={
            "source": "canonical_pons_v1_v2_market_paths",
            "chain_id": 4663,
            "v1_points": (
                Path(args.v1_points).name if args.v1_points else None
            ),
            "v2_curve_points": (
                Path(args.v2_curve_points).name
                if args.v2_curve_points else None
            ),
            "v2_seed_points": (
                Path(args.v2_seed_points).name
                if args.v2_seed_points else None
            ),
            "v2_v4_points": (
                Path(args.v2_v4_points).name if args.v2_v4_points else None
            ),
        },
    )
    summary_manifest = write_jsonl_snapshot(
        summary,
        output=Path(args.universe_out),
        provenance={
            "source": "canonical_pons_market_path",
            "market_path_sha256": path_manifest["sha256"],
            "eligibility_threshold_usd": "100000",
            "eligibility_semantics": "token reached at least $100k at any point",
        },
    )
    annotated_manifest = write_jsonl_snapshot(
        annotated,
        output=Path(args.outcomes_out),
        provenance={
            "source": "canonical_pons_market_path",
            "market_path_sha256": path_manifest["sha256"],
            "universe_sha256": summary_manifest["sha256"],
            "recovery_floor_multiple": "5",
            "outcome_semantics": (
                "continuous best strictly-later multiple from each point; "
                "5x is only the minimum recovery label"
            ),
            "dump_semantics": (
                "no fixed dump threshold; drawdown from running peak retained "
                "continuously for empirical discovery"
            ),
        },
    )

    episode_manifest = write_jsonl_snapshot(
        episodes,
        output=Path(args.episodes_out),
        provenance={
            "source": "threshold_free_pons_running_peak_drawdowns",
            "market_path_sha256": path_manifest["sha256"],
            "outcomes_sha256": annotated_manifest["sha256"],
            "major_dump_threshold": None,
            "episode_semantics": (
                "peak-to-trough episode closes only when prior peak is "
                "reclaimed; no depth cutoff is imposed"
            ),
        },
    )

    version_counts = {}
    eligible_version_counts = {}
    by_token = {row["token"]: row for row in summary}
    for row in summary:
        version = row["pons_version"]
        version_counts[version] = version_counts.get(version, 0) + 1
        if row["reached_100k"]:
            eligible_version_counts[version] = (
                eligible_version_counts.get(version, 0) + 1
            )

    recoverable_points = [
        row for row in annotated if row["reached_5x_later"]
    ]
    tokens_with_a_5x_later_point = {
        row["token"] for row in recoverable_points
    }

    print(
        json.dumps(
            {
                "market_path": path_manifest,
                "universe": summary_manifest,
                "outcomes": annotated_manifest,
                "drawdown_episodes": episode_manifest,
                "pons_tokens_with_priced_paths": len(by_token),
                "pons_tokens_reached_100k": len(eligible),
                "tokens_by_version": version_counts,
                "eligible_tokens_by_version": eligible_version_counts,
                "eligible_tokens_with_at_least_one_5x_later_point": len(
                    tokens_with_a_5x_later_point
                ),
                "annotated_eligible_price_points": len(annotated),
                "drawdown_episodes_count": len(episodes),
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




def _load_quote_usd_inputs(
    args: argparse.Namespace,
):
    """Load small state rows and lazily merge all causal USD update sources."""
    pairs = [
        (
            getattr(args, "oracle_state", None),
            getattr(args, "oracle_events", None),
            "oracle",
        ),
        (
            getattr(args, "fallback_state", None),
            getattr(args, "fallback_events", None),
            "fallback",
        ),
    ]
    states = []
    groups = []
    for state_path, event_path, label in pairs:
        if bool(state_path) != bool(event_path):
            raise SystemExit(
                f"--{label}-state and --{label}-events must be supplied together"
            )
        if not state_path:
            continue
        states.extend(_load_jsonl(state_path))
        groups.append(_iter_jsonl(event_path))
    return prepare_quote_usd_inputs(states, groups)


def _load_initial_quote_usd(
    args: argparse.Namespace,
) -> dict[str, Decimal]:
    """Compatibility wrapper returning only truly pre-window quote state."""
    initial, _ = _load_quote_usd_inputs(args)
    return initial


def _load_quote_oracle_inputs(args: argparse.Namespace):
    """Compatibility helper for bounded replays that materialize USD updates."""
    initial, updates = _load_quote_usd_inputs(args)
    return initial, list(updates)

def cmd_rpc_v3_pons_tape(args: argparse.Namespace) -> int:
    """Acquire the shared V3 Initialize/Swap price tape for Pons V1 pools."""
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
    pool_address_filter = (
        None if args.global_topic_scan else sorted(pool_launch_block)
    )
    raw_tape = rpc.iter_logs_chunked(
        args.from_block,
        args.to_block,
        address=pool_address_filter,
        topics=[[V3_INITIALIZE_TOPIC, V3_SWAP_TOPIC]],
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )

    counters = {
        "matched_pons_initializes": 0,
        "matched_pons_swaps": 0,
    }
    matched_pools: set[str] = set()

    def matched():
        for raw in raw_tape:
            pool = raw.address.lower()
            launch_block = pool_launch_block.get(pool)
            if launch_block is None:
                continue
            if raw.block_number < launch_block:
                raise RuntimeError(
                    f"price event for Pons pool {pool} predates recorded launch block"
                )
            topic0 = raw.topics[0] if raw.topics else None
            if topic0 == V3_INITIALIZE_TOPIC:
                event = asdict(decode_v3_pool_initialized(raw))
                event["event_type"] = "v3_initialize"
                counters["matched_pons_initializes"] += 1
            elif topic0 == V3_SWAP_TOPIC:
                event = asdict(decode_v3_swap(raw))
                event["event_type"] = "v3_swap"
                counters["matched_pons_swaps"] += 1
            else:
                continue
            matched_pools.add(pool)
            yield event

    manifest = write_jsonl_snapshot(
        matched(),
        output=Path(args.out),
        provenance={
            "source": "evm_json_rpc",
            "chain_id": 4663,
            "protocol": "uniswap_v3_shared_price_tape",
            "event_topic0_or": [V3_INITIALIZE_TOPIC, V3_SWAP_TOPIC],
            "registry": str(Path(args.registry).name),
            "registry_pools": len(pool_launch_block),
            "server_side_pool_address_filter": pool_address_filter is not None,
            "pool_filter_mode": (
                "address_plus_topic"
                if pool_address_filter is not None
                else "global_topic_then_registry"
            ),
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



def cmd_rpc_v3_quote_route_tape(args: argparse.Namespace) -> int:
    """Acquire V3 price events only after each quote route becomes active."""
    routes = _load_jsonl(args.routes)
    activation_by_pool = {
        row["pool"].lower(): int(row["activation_block"])
        for row in routes
    }
    if not activation_by_pool:
        manifest = write_jsonl_snapshot(
            [],
            output=Path(args.out),
            provenance={
                "source": "evm_json_rpc",
                "chain_id": 4663,
                "protocol": "uniswap_v3_quote_fallback_routes",
                "routes": Path(args.routes).name,
                "from_block": args.from_block,
                "to_block": args.to_block,
                "empty_reason": "no selected V3 fallback routes",
            },
        )
        print(json.dumps({**manifest, "requests_made": 0}, sort_keys=True))
        return 0

    rpc = _archive_rpc(args)
    rpc.assert_robinhood()
    started = time.monotonic()
    raw = rpc.iter_logs_chunked(
        args.from_block,
        args.to_block,
        address=sorted(activation_by_pool),
        topics=[[V3_INITIALIZE_TOPIC, V3_SWAP_TOPIC]],
        chunk_size=args.chunk_size,
        min_chunk_size=args.min_chunk_size,
    )
    counters = {
        "pre_activation_events_skipped": 0,
        "matched_initializes": 0,
        "matched_swaps": 0,
    }

    def active_events():
        for log in raw:
            pool = log.address.lower()
            activation = activation_by_pool.get(pool)
            if activation is None:
                raise ValueError(
                    f"V3 route filter returned unknown pool {pool}"
                )
            if int(log.block_number) < activation:
                counters["pre_activation_events_skipped"] += 1
                continue
            topic0 = log.topics[0] if log.topics else None
            if topic0 == V3_INITIALIZE_TOPIC:
                event = asdict(decode_v3_pool_initialized(log))
                event["event_type"] = "v3_initialize"
                counters["matched_initializes"] += 1
            elif topic0 == V3_SWAP_TOPIC:
                event = asdict(decode_v3_swap(log))
                event["event_type"] = "v3_swap"
                counters["matched_swaps"] += 1
            else:
                continue
            yield event

    manifest = write_jsonl_snapshot(
        active_events(),
        output=Path(args.out),
        provenance={
            "source": "evm_json_rpc",
            "chain_id": 4663,
            "protocol": "uniswap_v3_quote_fallback_routes",
            "routes": Path(args.routes).name,
            "route_pools": len(activation_by_pool),
            "from_block": args.from_block,
            "to_block": args.to_block,
            "event_topic0_or": [V3_INITIALIZE_TOPIC, V3_SWAP_TOPIC],
            "activation_semantics": (
                "events before each route's first Pons use are skipped"
            ),
        },
    )
    print(json.dumps({
        **manifest,
        **counters,
        "requests_made": rpc.requests_made,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }, sort_keys=True))
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
    initial_quote_usd, quote_usd_updates = _load_quote_oracle_inputs(args)
    quote_decimals_by_token = {}
    feed_path = getattr(args, "oracle_feed_registry", None)
    if feed_path:
        quote_decimals_by_token = {
            row["quote_token"].lower(): int(row["quote_decimals"])
            for row in _load_jsonl(feed_path)
        }

    points = build_v1_market_cap_points(
        registry,
        _iter_jsonl(args.swaps),
        anchor_points,
        initial_weth_usd=initial_weth_usd,
        weth_decimals=weth_state.decimals,
        usdg_decimals=usdg_state.decimals,
        initial_quote_usd=initial_quote_usd,
        quote_usd_updates=quote_usd_updates,
        quote_decimals_by_token=quote_decimals_by_token,
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
            "oracle_feed_registry": (
                None
                if not getattr(args, "oracle_feed_registry", None)
                else Path(args.oracle_feed_registry).name
            ),
            "oracle_state": (
                None
                if not getattr(args, "oracle_state", None)
                else Path(args.oracle_state).name
            ),
            "oracle_events": (
                None
                if not getattr(args, "oracle_events", None)
                else Path(args.oracle_events).name
            ),
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








    pons_normalized_trades = sub.add_parser("pons-normalize-trades")
    pons_normalized_trades.add_argument("--points", required=True)
    pons_normalized_trades.add_argument("--out", required=True)
    pons_normalized_trades.set_defaults(func=cmd_pons_normalize_trades)

    pons_trade_features = sub.add_parser("pons-trade-features")
    pons_trade_features.add_argument("--trades", required=True)
    pons_trade_features.add_argument("--out", required=True)
    pons_trade_features.set_defaults(func=cmd_pons_trade_features)

    pons_transactions = sub.add_parser("rpc-pons-transaction-enrich")
    pons_transactions.add_argument("--points", required=True)
    pons_transactions.add_argument("--batch-size", type=int, default=100)
    pons_transactions.add_argument("--min-batch-size", type=int, default=1)
    pons_transactions.add_argument("--transactions-out", required=True)
    pons_transactions.add_argument("--out", required=True)
    pons_transactions.set_defaults(func=cmd_rpc_pons_transaction_enrich)

    pons_time = sub.add_parser("rpc-pons-time-enrich")
    pons_time.add_argument("--outcomes", required=True)
    pons_time.add_argument("--episodes", required=True)
    pons_time.add_argument("--batch-size", type=int, default=100)
    pons_time.add_argument("--min-batch-size", type=int, default=1)
    pons_time.add_argument("--timestamps-out", required=True)
    pons_time.add_argument("--out", required=True)
    pons_time.add_argument("--episodes-out", required=True)
    pons_time.set_defaults(func=cmd_rpc_pons_time_enrich)

    v2_graduated_registry = sub.add_parser("pons-v2-graduated-registry")
    v2_graduated_registry.add_argument("--registry", required=True)
    v2_graduated_registry.add_argument("--graduations", required=True)
    v2_graduated_registry.add_argument("--out", required=True)
    v2_graduated_registry.set_defaults(func=cmd_pons_v2_graduated_registry)

    pons_research = sub.add_parser("pons-research-dataset")
    pons_research.add_argument("--v1-points")
    pons_research.add_argument("--v2-curve-points")
    pons_research.add_argument("--v2-seed-points")
    pons_research.add_argument("--v2-v4-points")
    pons_research.add_argument("--path-out", required=True)
    pons_research.add_argument("--universe-out", required=True)
    pons_research.add_argument("--outcomes-out", required=True)
    pons_research.add_argument("--episodes-out", required=True)
    pons_research.set_defaults(func=cmd_pons_research_dataset)

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
    v2_tape.add_argument(
        "--global-topic-scan",
        action="store_true",
        help=(
            "scan matching curve event signatures globally and filter against "
            "the frozen Pons registry client-side; useful when the curve "
            "address list is too large for one RPC filter"
        ),
    )
    v2_tape.add_argument("--out", required=True)
    v2_tape.set_defaults(func=cmd_rpc_v2_curve_tape)


    v2_transition_tape = sub.add_parser("rpc-v2-transition-tape")
    v2_transition_tape.add_argument("--registry", required=True)
    v2_transition_tape.add_argument("--from-block", type=int, required=True)
    v2_transition_tape.add_argument("--to-block", type=int, required=True)
    v2_transition_tape.add_argument("--chunk-size", type=int, default=100_000)
    v2_transition_tape.add_argument("--min-chunk-size", type=int, default=1)
    v2_transition_tape.add_argument("--graduations-out", required=True)
    v2_transition_tape.add_argument("--registrations-out", required=True)
    v2_transition_tape.set_defaults(func=cmd_rpc_v2_transition_tape)

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
    v2_v4.add_argument(
        "--global-pool-scan",
        action="store_true",
        help=(
            "scan PoolManager Initialize/Swap events without a topic1 pool-id "
            "list and filter against frozen Pons registrations client-side"
        ),
    )
    v2_v4.add_argument("--out", required=True)
    v2_v4.set_defaults(func=cmd_rpc_v2_v4_tape)





    flap_registry = sub.add_parser("flap-registry")
    flap_registry.add_argument("--events", required=True)
    flap_registry.add_argument("--out", required=True)
    flap_registry.set_defaults(func=cmd_flap_registry)




    pools_fun_registry = sub.add_parser("rpc-pools-fun-registry-window")
    pools_fun_registry.add_argument("--from-block", type=int, required=True)
    pools_fun_registry.add_argument("--to-block", type=int, required=True)
    pools_fun_registry.add_argument("--chunk-size", type=int, default=100_000)
    pools_fun_registry.add_argument("--min-chunk-size", type=int, default=1)
    pools_fun_registry.add_argument("--out", required=True)
    pools_fun_registry.set_defaults(func=cmd_rpc_pools_fun_registry_window)

    pools_fun_v3 = sub.add_parser("rpc-pools-fun-v3-tape")
    pools_fun_v3.add_argument("--registry", required=True)
    pools_fun_v3.add_argument("--from-block", type=int, required=True)
    pools_fun_v3.add_argument("--to-block", type=int, required=True)
    pools_fun_v3.add_argument("--chunk-size", type=int, default=100_000)
    pools_fun_v3.add_argument("--min-chunk-size", type=int, default=1)
    pools_fun_v3.add_argument("--initialize-out", required=True)
    pools_fun_v3.add_argument("--swap-out", required=True)
    pools_fun_v3.set_defaults(func=cmd_rpc_pools_fun_v3_tape)

    pools_fun_mcap = sub.add_parser("rpc-pools-fun-market-cap-window")
    pools_fun_mcap.add_argument("--registry", required=True)
    pools_fun_mcap.add_argument("--initializes", required=True)
    pools_fun_mcap.add_argument("--swaps", required=True)
    pools_fun_mcap.add_argument("--from-block", type=int, required=True)
    pools_fun_mcap.add_argument("--to-block", type=int, required=True)
    pools_fun_mcap.add_argument("--chunk-size", type=int, default=100_000)
    pools_fun_mcap.add_argument("--min-chunk-size", type=int, default=1)
    pools_fun_mcap.add_argument(
        "--usd-anchor-pool",
        default=UNISWAP_V3_WETH_USDG_ANCHOR_POOL,
    )
    pools_fun_mcap.add_argument("--oracle-state")
    pools_fun_mcap.add_argument("--oracle-events")
    pools_fun_mcap.add_argument("--out", required=True)
    pools_fun_mcap.add_argument("--summary-out", required=True)
    pools_fun_mcap.set_defaults(func=cmd_rpc_pools_fun_market_cap_window)

    pools_trade_registry = sub.add_parser("rpc-pools-trade-registry-window")
    pools_trade_registry.add_argument("--from-block", type=int, required=True)
    pools_trade_registry.add_argument("--to-block", type=int, required=True)
    pools_trade_registry.add_argument("--chunk-size", type=int, default=100_000)
    pools_trade_registry.add_argument("--min-chunk-size", type=int, default=1)
    pools_trade_registry.add_argument("--out", required=True)
    pools_trade_registry.set_defaults(func=cmd_rpc_pools_trade_registry_window)

    pools_trade_v4 = sub.add_parser("rpc-pools-trade-v4-tape")
    pools_trade_v4.add_argument("--registry", required=True)
    pools_trade_v4.add_argument("--from-block", type=int, required=True)
    pools_trade_v4.add_argument("--to-block", type=int, required=True)
    pools_trade_v4.add_argument("--chunk-size", type=int, default=100_000)
    pools_trade_v4.add_argument("--min-chunk-size", type=int, default=1)
    pools_trade_v4.add_argument("--initialize-out", required=True)
    pools_trade_v4.add_argument("--swap-out", required=True)
    pools_trade_v4.set_defaults(func=cmd_rpc_pools_trade_v4_tape)

    pools_trade_mcap = sub.add_parser("rpc-pools-trade-market-cap-window")
    pools_trade_mcap.add_argument("--registry", required=True)
    pools_trade_mcap.add_argument("--initializes", required=True)
    pools_trade_mcap.add_argument("--swaps", required=True)
    pools_trade_mcap.add_argument("--from-block", type=int, required=True)
    pools_trade_mcap.add_argument("--to-block", type=int, required=True)
    pools_trade_mcap.add_argument("--chunk-size", type=int, default=100_000)
    pools_trade_mcap.add_argument("--min-chunk-size", type=int, default=1)
    pools_trade_mcap.add_argument(
        "--usd-anchor-pool",
        default=UNISWAP_V3_WETH_USDG_ANCHOR_POOL,
    )
    pools_trade_mcap.add_argument("--oracle-state")
    pools_trade_mcap.add_argument("--oracle-events")
    pools_trade_mcap.add_argument("--out", required=True)
    pools_trade_mcap.add_argument("--summary-out", required=True)
    pools_trade_mcap.set_defaults(func=cmd_rpc_pools_trade_market_cap_window)


    hood_tape = sub.add_parser("rpc-hood-fun-tape")
    hood_tape.add_argument("--from-block", type=int, required=True)
    hood_tape.add_argument("--to-block", type=int, required=True)
    hood_tape.add_argument("--chunk-size", type=int, default=100_000)
    hood_tape.add_argument("--min-chunk-size", type=int, default=1)
    hood_tape.add_argument("--out", required=True)
    hood_tape.set_defaults(func=cmd_rpc_hood_fun_tape)

    hood_registry = sub.add_parser("hood-fun-registry")
    hood_registry.add_argument("--events", required=True)
    hood_registry.add_argument("--out", required=True)
    hood_registry.set_defaults(func=cmd_hood_fun_registry)

    hood_mcap = sub.add_parser("rpc-hood-fun-curve-market-cap-window")
    hood_mcap.add_argument("--events", required=True)
    hood_mcap.add_argument("--registry", required=True)
    hood_mcap.add_argument("--from-block", type=int, required=True)
    hood_mcap.add_argument("--to-block", type=int, required=True)
    hood_mcap.add_argument("--chunk-size", type=int, default=100_000)
    hood_mcap.add_argument("--min-chunk-size", type=int, default=1)
    hood_mcap.add_argument(
        "--usd-anchor-pool",
        default=UNISWAP_V3_WETH_USDG_ANCHOR_POOL,
    )
    hood_mcap.add_argument("--out", required=True)
    hood_mcap.add_argument("--summary-out", required=True)
    hood_mcap.set_defaults(func=cmd_rpc_hood_fun_curve_market_cap_window)

    trench_tape = sub.add_parser("rpc-trench-tape")
    trench_tape.add_argument("--from-block", type=int, required=True)
    trench_tape.add_argument("--to-block", type=int, required=True)
    trench_tape.add_argument("--chunk-size", type=int, default=100_000)
    trench_tape.add_argument("--min-chunk-size", type=int, default=1)
    trench_tape.add_argument("--out", required=True)
    trench_tape.set_defaults(func=cmd_rpc_trench_tape)

    trench_registry = sub.add_parser("trench-registry")
    trench_registry.add_argument("--events", required=True)
    trench_registry.add_argument("--out", required=True)
    trench_registry.set_defaults(func=cmd_trench_registry)

    trench_mcap = sub.add_parser("rpc-trench-curve-market-cap-window")
    trench_mcap.add_argument("--events", required=True)
    trench_mcap.add_argument("--registry", required=True)
    trench_mcap.add_argument("--from-block", type=int, required=True)
    trench_mcap.add_argument("--to-block", type=int, required=True)
    trench_mcap.add_argument("--chunk-size", type=int, default=100_000)
    trench_mcap.add_argument("--min-chunk-size", type=int, default=1)
    trench_mcap.add_argument(
        "--usd-anchor-pool",
        default=UNISWAP_V3_WETH_USDG_ANCHOR_POOL,
    )
    trench_mcap.add_argument("--oracle-state")
    trench_mcap.add_argument("--oracle-events")
    trench_mcap.add_argument("--out", required=True)
    trench_mcap.add_argument("--summary-out", required=True)
    trench_mcap.set_defaults(func=cmd_rpc_trench_curve_market_cap_window)

    flap_tape = sub.add_parser("rpc-flap-tape")
    flap_tape.add_argument("--from-block", type=int, required=True)
    flap_tape.add_argument("--to-block", type=int, required=True)
    flap_tape.add_argument("--chunk-size", type=int, default=100_000)
    flap_tape.add_argument("--min-chunk-size", type=int, default=1)
    flap_tape.add_argument("--out", required=True)
    flap_tape.set_defaults(func=cmd_rpc_flap_tape)

    flap_mcap = sub.add_parser("rpc-flap-curve-market-cap-window")
    flap_mcap.add_argument("--events", required=True)
    flap_mcap.add_argument("--registry", required=True)
    flap_mcap.add_argument("--from-block", type=int, required=True)
    flap_mcap.add_argument("--to-block", type=int, required=True)
    flap_mcap.add_argument("--chunk-size", type=int, default=100_000)
    flap_mcap.add_argument("--min-chunk-size", type=int, default=1)
    flap_mcap.add_argument(
        "--usd-anchor-pool",
        default=UNISWAP_V3_WETH_USDG_ANCHOR_POOL,
    )
    flap_mcap.add_argument("--oracle-state")
    flap_mcap.add_argument("--oracle-events")
    flap_mcap.add_argument("--out", required=True)
    flap_mcap.add_argument("--summary-out", required=True)
    flap_mcap.set_defaults(func=cmd_rpc_flap_curve_market_cap_window)

    dex_census = sub.add_parser("rpc-dex-pool-window")
    dex_census.add_argument("--from-block", type=int, required=True)
    dex_census.add_argument("--to-block", type=int, required=True)
    dex_census.add_argument("--chunk-size", type=int, default=100_000)
    dex_census.add_argument("--min-chunk-size", type=int, default=1)
    dex_census.add_argument("--v3-out", required=True)
    dex_census.add_argument("--v4-out", required=True)
    dex_census.set_defaults(func=cmd_rpc_dex_pool_window)

    quote_v3_routes = sub.add_parser(
        "rpc-pons-unpriced-quote-v3-routes"
    )
    quote_v3_routes.add_argument("--quote-registry", required=True)
    quote_v3_routes.add_argument("--out", required=True)
    quote_v3_routes.set_defaults(
        func=cmd_rpc_pons_unpriced_quote_v3_routes
    )

    select_quote_v3 = sub.add_parser("pons-select-v3-quote-routes")
    select_quote_v3.add_argument("--audit", required=True)
    select_quote_v3.add_argument("--out", required=True)
    select_quote_v3.set_defaults(func=cmd_pons_select_v3_quote_routes)

    quote_v3_usd = sub.add_parser("pons-v3-quote-usd-tape")
    quote_v3_usd.add_argument("--routes", required=True)
    quote_v3_usd.add_argument("--v3-events", required=True)
    quote_v3_usd.add_argument("--anchor-events", required=True)
    quote_v3_usd.add_argument("--anchor-initial", required=True)
    quote_v3_usd.add_argument("--state-out", required=True)
    quote_v3_usd.add_argument("--out", required=True)
    quote_v3_usd.set_defaults(func=cmd_pons_v3_quote_usd_tape)

    quote_audit = sub.add_parser("pons-quote-audit")
    quote_audit.add_argument("--registry", required=True)
    quote_audit.add_argument("--out", required=True)
    quote_audit.set_defaults(func=cmd_pons_quote_audit)

    quote_causality = sub.add_parser("rpc-pons-quote-causality")
    quote_causality.add_argument("--quote-registry", required=True)
    quote_causality.add_argument("--out", required=True)
    quote_causality.set_defaults(func=cmd_rpc_pons_quote_causality)

    pons_oracle_lifecycle = sub.add_parser(
        "rpc-pons-stock-oracle-lifecycle"
    )
    pons_oracle_lifecycle.add_argument("--quote-registry", required=True)
    pons_oracle_lifecycle.add_argument("--from-block", type=int)
    pons_oracle_lifecycle.add_argument("--to-block", type=int, required=True)
    pons_oracle_lifecycle.add_argument("--chunk-size", type=int, default=100_000)
    pons_oracle_lifecycle.add_argument("--min-chunk-size", type=int, default=1)
    pons_oracle_lifecycle.add_argument("--state-out", required=True)
    pons_oracle_lifecycle.add_argument("--out", required=True)
    pons_oracle_lifecycle.set_defaults(
        func=cmd_rpc_pons_stock_oracle_lifecycle
    )

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

    pons_stock_oracle = sub.add_parser("rpc-pons-stock-oracle-window")
    pons_stock_oracle.add_argument("--registry", required=True)
    pons_stock_oracle.add_argument("--from-block", type=int, required=True)
    pons_stock_oracle.add_argument("--to-block", type=int, required=True)
    pons_stock_oracle.add_argument("--chunk-size", type=int, default=100_000)
    pons_stock_oracle.add_argument("--min-chunk-size", type=int, default=1)
    pons_stock_oracle.add_argument("--feed-out", required=True)
    pons_stock_oracle.add_argument("--state-out", required=True)
    pons_stock_oracle.add_argument("--out", required=True)
    pons_stock_oracle.set_defaults(func=cmd_rpc_v2_stock_oracle_window)

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

    v1_eligibility = sub.add_parser("pons-v1-lifecycle-eligibility")
    v1_eligibility.add_argument("--registry", required=True)
    v1_eligibility.add_argument("--v3-events", required=True)
    v1_eligibility.add_argument("--quote-registry", required=True)
    v1_eligibility.add_argument("--anchor-events", required=True)
    v1_eligibility.add_argument("--anchor-initial", required=True)
    v1_eligibility.add_argument("--oracle-state")
    v1_eligibility.add_argument("--oracle-events")
    v1_eligibility.add_argument("--fallback-state")
    v1_eligibility.add_argument("--fallback-events")
    v1_eligibility.add_argument(
        "--snapshot-head", type=int, required=True
    )
    v1_eligibility.add_argument("--out", required=True)
    v1_eligibility.set_defaults(
        func=cmd_pons_v1_lifecycle_eligibility
    )

    v2_eligibility = sub.add_parser("pons-v2-curve-eligibility")
    v2_eligibility.add_argument("--registry", required=True)
    v2_eligibility.add_argument("--curve-events", required=True)
    v2_eligibility.add_argument("--anchor-events", required=True)
    v2_eligibility.add_argument("--anchor-initial", required=True)
    v2_eligibility.add_argument("--oracle-state")
    v2_eligibility.add_argument("--oracle-events")
    v2_eligibility.add_argument("--fallback-state")
    v2_eligibility.add_argument("--fallback-events")
    v2_eligibility.add_argument("--snapshot-head", type=int, required=True)
    v2_eligibility.add_argument("--out", required=True)
    v2_eligibility.set_defaults(func=cmd_pons_v2_curve_eligibility)

    v2_lifecycle_eligibility = sub.add_parser(
        "pons-v2-lifecycle-eligibility"
    )
    v2_lifecycle_eligibility.add_argument("--registry", required=True)
    v2_lifecycle_eligibility.add_argument("--curve-summary", required=True)
    v2_lifecycle_eligibility.add_argument("--graduations", required=True)
    v2_lifecycle_eligibility.add_argument("--registrations", required=True)
    v2_lifecycle_eligibility.add_argument("--v4-events", required=True)
    v2_lifecycle_eligibility.add_argument("--anchor-events", required=True)
    v2_lifecycle_eligibility.add_argument("--anchor-initial", required=True)
    v2_lifecycle_eligibility.add_argument("--oracle-state")
    v2_lifecycle_eligibility.add_argument("--oracle-events")
    v2_lifecycle_eligibility.add_argument("--fallback-state")
    v2_lifecycle_eligibility.add_argument("--fallback-events")
    v2_lifecycle_eligibility.add_argument(
        "--snapshot-head", type=int, required=True
    )
    v2_lifecycle_eligibility.add_argument("--out", required=True)
    v2_lifecycle_eligibility.set_defaults(
        func=cmd_pons_v2_lifecycle_eligibility
    )

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
    tape.add_argument(
        "--global-topic-scan",
        action="store_true",
        help=(
            "scan V3 Initialize/Swap topics globally and filter against the "
            "frozen Pons pool registry client-side"
        ),
    )
    tape.add_argument("--out", required=True)
    tape.set_defaults(func=cmd_rpc_v3_pons_tape)


    quote_route_tape = sub.add_parser("rpc-v3-quote-route-tape")
    quote_route_tape.add_argument("--routes", required=True)
    quote_route_tape.add_argument("--from-block", type=int, required=True)
    quote_route_tape.add_argument("--to-block", type=int, required=True)
    quote_route_tape.add_argument("--chunk-size", type=int, default=100_000)
    quote_route_tape.add_argument("--min-chunk-size", type=int, default=1)
    quote_route_tape.add_argument("--out", required=True)
    quote_route_tape.set_defaults(func=cmd_rpc_v3_quote_route_tape)

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
    market_caps.add_argument("--oracle-feed-registry")
    market_caps.add_argument("--oracle-state")
    market_caps.add_argument("--oracle-events")
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
