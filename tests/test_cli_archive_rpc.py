from types import SimpleNamespace

from hlp.cli import _archive_rpc, _load_initial_quote_usd, build_parser
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


def test_v2_curve_eligibility_parses():
    parser = build_parser()
    args = parser.parse_args([
        "pons-v2-curve-eligibility",
        "--registry", "v2.jsonl",
        "--curve-events", "curve.jsonl",
        "--anchor-events", "anchor.jsonl",
        "--anchor-initial", "anchor.json",
        "--snapshot-head", "100",
        "--out", "summary.jsonl",
    ])
    assert args.snapshot_head == 100
    assert args.oracle_state is None


def test_pons_stock_oracle_lifecycle_parses_shard():
    parser = build_parser()
    args = parser.parse_args([
        "rpc-pons-stock-oracle-lifecycle",
        "--quote-registry", "quotes.jsonl",
        "--from-block", "100",
        "--to-block", "200",
        "--state-out", "state.jsonl",
        "--out", "updates.jsonl",
    ])
    assert args.from_block == 100
    assert args.to_block == 200


def test_v4_global_pool_scan_parses():
    parser = build_parser()
    args = parser.parse_args([
        "rpc-v2-v4-tape",
        "--registrations", "registrations.jsonl",
        "--from-block", "10",
        "--to-block", "20",
        "--global-pool-scan",
        "--out", "v4.jsonl",
    ])
    assert args.global_pool_scan is True


def test_v2_lifecycle_eligibility_parses():
    parser = build_parser()
    args = parser.parse_args([
        "pons-v2-lifecycle-eligibility",
        "--registry", "v2.jsonl",
        "--curve-summary", "curve-summary.jsonl",
        "--graduations", "graduations.jsonl",
        "--registrations", "registrations.jsonl",
        "--v4-events", "v4.jsonl",
        "--anchor-events", "anchor.jsonl",
        "--anchor-initial", "anchor-initial.json",
        "--snapshot-head", "100",
        "--out", "lifecycle.jsonl",
    ])
    assert args.snapshot_head == 100
    assert args.oracle_state is None



def test_initial_quote_loader_does_not_materialize_oracle_tape(monkeypatch):
    calls = []

    def fake_load(path):
        calls.append(path)
        assert path == "state.jsonl"
        return [{
            "quote_token": "0x" + "11" * 20,
            "usd_price": "200",
        }]

    monkeypatch.setattr("hlp.cli._load_jsonl", fake_load)
    parsed = SimpleNamespace(
        oracle_state="state.jsonl",
        oracle_events="updates.jsonl",
    )

    initial = _load_initial_quote_usd(parsed)

    assert calls == ["state.jsonl"]
    assert str(initial["0x" + "11" * 20]) == "200"



def test_v1_lifecycle_eligibility_parses():
    parser = build_parser()
    args = parser.parse_args([
        "pons-v1-lifecycle-eligibility",
        "--registry", "pons-full.jsonl",
        "--v3-events", "v3.jsonl",
        "--quote-registry", "quotes.jsonl",
        "--anchor-events", "anchor.jsonl",
        "--anchor-initial", "anchor.json",
        "--snapshot-head", "100",
        "--out", "summary.jsonl",
    ])
    assert args.snapshot_head == 100
    assert args.oracle_state is None



def test_unpriced_quote_v3_route_audit_parses():
    parser = build_parser()
    args = parser.parse_args([
        "rpc-pons-unpriced-quote-v3-routes",
        "--quote-registry", "quotes.jsonl",
        "--out", "routes.jsonl",
    ])
    assert args.quote_registry == "quotes.jsonl"
    assert args.out == "routes.jsonl"



def test_v3_quote_route_selection_and_usd_tape_parse():
    parser = build_parser()
    selected = parser.parse_args([
        "pons-select-v3-quote-routes",
        "--audit", "audit.jsonl",
        "--out", "routes.jsonl",
    ])
    assert selected.audit == "audit.jsonl"

    tape = parser.parse_args([
        "pons-v3-quote-usd-tape",
        "--routes", "routes.jsonl",
        "--v3-events", "v3.jsonl",
        "--anchor-events", "anchor.jsonl",
        "--anchor-initial", "anchor-initial.json",
        "--state-out", "state.jsonl",
        "--out", "updates.jsonl",
    ])
    assert tape.routes == "routes.jsonl"
    assert tape.state_out == "state.jsonl"



def test_v3_quote_route_tape_parses():
    parser = build_parser()
    args = parser.parse_args([
        "rpc-v3-quote-route-tape",
        "--routes", "routes.jsonl",
        "--from-block", "100",
        "--to-block", "200",
        "--out", "v3.jsonl",
    ])
    assert args.routes == "routes.jsonl"
    assert args.from_block == 100



def test_full_eligibility_parsers_accept_fallback_quote_tapes():
    parser = build_parser()

    v1 = parser.parse_args([
        "pons-v1-lifecycle-eligibility",
        "--registry", "registry.jsonl",
        "--v3-events", "v3.jsonl",
        "--quote-registry", "quotes.jsonl",
        "--anchor-events", "anchor.jsonl",
        "--anchor-initial", "anchor.json",
        "--oracle-state", "chainlink-state.jsonl",
        "--oracle-events", "chainlink-events.jsonl",
        "--fallback-state", "fallback-state.jsonl",
        "--fallback-events", "fallback-events.jsonl",
        "--snapshot-head", "200",
        "--out", "v1-summary.jsonl",
    ])
    assert v1.fallback_state == "fallback-state.jsonl"

    v2 = parser.parse_args([
        "pons-v2-curve-eligibility",
        "--registry", "registry.jsonl",
        "--curve-events", "curve.jsonl",
        "--anchor-events", "anchor.jsonl",
        "--anchor-initial", "anchor.json",
        "--fallback-state", "fallback-state.jsonl",
        "--fallback-events", "fallback-events.jsonl",
        "--snapshot-head", "200",
        "--out", "v2-summary.jsonl",
    ])
    assert v2.fallback_events == "fallback-events.jsonl"



def test_delayed_v3_usdg_route_probe_parses():
    parser = build_parser()
    args = parser.parse_args([
        "rpc-pons-delayed-v3-usdg-routes",
        "--audit", "audit.jsonl",
        "--to-block", "200",
        "--max-forward-blocks", "100000",
        "--out", "delayed.jsonl",
    ])
    assert args.max_forward_blocks == 100000
    assert args.audit == "audit.jsonl"



def test_v3_quote_route_selector_accepts_delayed_probe():
    parser = build_parser()
    args = parser.parse_args([
        "pons-select-v3-quote-routes",
        "--audit", "audit.jsonl",
        "--delayed", "delayed.jsonl",
        "--out", "routes.jsonl",
    ])
    assert args.delayed == "delayed.jsonl"
