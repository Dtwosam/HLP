"""HLP command-line entry point."""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import asdict
from pathlib import Path

from hlp.config import (
    DEFAULT_RPC_URL,
    SOLIDRPC_PUBLIC_RPC_URL,
    ROBINHOOD_USDG,
    ROBINHOOD_WETH,
    UNISWAP_V3_WETH_USDG_ANCHOR_POOL,
    PONS_V1_FACTORY,
    PONS_V2_FACTORY,
    PONS_V1_DEPLOYMENT_BLOCK,
    PONS_V2_DEPLOYMENT_BLOCK,
    PONS_V2_MEME_HOOK,
    UNISWAP_V4_POOL_MANAGER,
)
from hlp.protocols.uniswap import V3_SWAP_TOPIC, decode_v3_swap
from hlp.data.blockscout import BlockscoutClient
from hlp.data.hoodexplorer import HoodExplorerClient
from hlp.data.pons_v1 import iter_enriched_v1_launches
from hlp.data.pons_v2 import ZERO_ADDRESS, iter_enriched_v2_launches
from hlp.data.rpc import RpcClient
from hlp.data.reconstruct import (
    attach_quote_usd_anchor,
    reconstruct_v3_price_points,
    v3_quote_price_at_block,
)
from hlp.data.snapshot import write_jsonl_snapshot
from hlp.data.universe import build_v1_market_cap_points, summarize_v1_market_caps
from hlp.data.v2_curve import (
    build_v2_curve_market_cap_points,
    summarize_v2_curve_market_caps,
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
    V2_TOKEN_LAUNCHED_TOPIC,
    decode_v1_launch,
    decode_v2_curve_buyback,
    decode_v2_curve_trade,
    decode_v2_launch,
    decode_v2_launch_config_event_id,
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
