from types import SimpleNamespace

from hlp.cli import _archive_rpc, build_parser
from hlp.config import SOLIDRPC_AUTH_RPC_URL, SOLIDRPC_PUBLIC_RPC_URL


def args():
    return SimpleNamespace(timeout=1.0, attempts=1, min_interval=0.0)


def test_archive_rpc_uses_keyless_public_route_without_key(monkeypatch):
    monkeypatch.delenv("ROBINHOOD_ARCHIVE_RPC_URL", raising=False)
    monkeypatch.delenv("ROBINHOOD_ARCHIVE_RPC_API_KEY", raising=False)

    rpc = _archive_rpc(args())

    assert rpc.url == SOLIDRPC_PUBLIC_RPC_URL
    assert rpc.extra_headers is None


def test_archive_rpc_uses_authenticated_route_when_keyed(monkeypatch):
    monkeypatch.delenv("ROBINHOOD_ARCHIVE_RPC_URL", raising=False)
    monkeypatch.setenv("ROBINHOOD_ARCHIVE_RPC_API_KEY", "test-key")

    rpc = _archive_rpc(args())

    assert rpc.url == SOLIDRPC_AUTH_RPC_URL
    assert rpc.extra_headers == {"X-API-Key": "test-key"}


def test_archive_rpc_explicit_url_override_wins(monkeypatch):
    monkeypatch.setenv("ROBINHOOD_ARCHIVE_RPC_URL", "https://example.invalid/rpc")
    monkeypatch.setenv("ROBINHOOD_ARCHIVE_RPC_API_KEY", "test-key")

    rpc = _archive_rpc(args())

    assert rpc.url == "https://example.invalid/rpc"
    assert rpc.extra_headers == {"X-API-Key": "test-key"}


def test_large_pons_tape_modes_parse():
    parser = build_parser()

    v2 = parser.parse_args([
        "rpc-v2-curve-tape",
        "--registry", "registry.jsonl",
        "--from-block", "10",
        "--to-block", "20",
        "--global-topic-scan",
        "--out", "curve.jsonl",
    ])
    assert v2.global_topic_scan is True

    v1 = parser.parse_args([
        "rpc-v3-pons-tape",
        "--registry", "registry.jsonl",
        "--from-block", "10",
        "--to-block", "20",
        "--global-topic-scan",
        "--out", "v3.jsonl",
    ])
    assert v1.global_topic_scan is True


def test_pons_stock_oracle_alias_parses():
    parser = build_parser()
    args = parser.parse_args([
        "rpc-pons-stock-oracle-window",
        "--registry", "registry.jsonl",
        "--from-block", "10",
        "--to-block", "20",
        "--feed-out", "feeds.jsonl",
        "--state-out", "state.jsonl",
        "--out", "updates.jsonl",
    ])
    assert args.registry == "registry.jsonl"


def test_v2_transition_tape_parses():
    parser = build_parser()
    args = parser.parse_args([
        "rpc-v2-transition-tape",
        "--registry", "v2.jsonl",
        "--from-block", "10",
        "--to-block", "20",
        "--graduations-out", "g.jsonl",
        "--registrations-out", "r.jsonl",
    ])
    assert args.registry == "v2.jsonl"
    assert args.graduations_out == "g.jsonl"
    assert args.registrations_out == "r.jsonl"
