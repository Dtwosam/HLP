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
    PONS_V1_FACTORY,
    PONS_V2_FACTORY,
    PONS_V2_MEME_HOOK,
    UNISWAP_V4_POOL_MANAGER,
)
from hlp.data.blockscout import BlockscoutClient
from hlp.data.hoodexplorer import HoodExplorerClient
from hlp.data.rpc import RpcClient
from hlp.data.snapshot import write_jsonl_snapshot
from hlp.protocols.pons import (
    V1_TOKEN_LAUNCHED_TOPIC,
    V2_TOKEN_LAUNCHED_TOPIC,
    decode_v1_launch,
    decode_v2_launch,
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
