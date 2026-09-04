"""HLP command-line entry point."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict

from hlp.config import DEFAULT_RPC_URL, PONS_V1_FACTORY, PONS_V2_FACTORY
from hlp.data.rpc import RpcClient
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
    )


def cmd_network_smoke(args: argparse.Namespace) -> int:
    rpc = _rpc(args)
    rpc.assert_robinhood()
    head = rpc.block_number()
    block = rpc.get_block(head)
    factories = {}
    for name, address in (("pons_v1", PONS_V1_FACTORY), ("pons_v2", PONS_V2_FACTORY)):
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
    sub = parser.add_subparsers(dest="command", required=True)

    smoke = sub.add_parser("network-smoke")
    smoke.set_defaults(func=cmd_network_smoke)

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
