from decimal import Decimal
import json
from types import SimpleNamespace

from hlp.cli import (
    build_parser,
    cmd_rpc_flap_curve_market_cap_window,
    cmd_rpc_trench_curve_market_cap_window,
)


def _write_jsonl(path, rows):
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    )


class FakeRpc:
    route_label = "test_archive"
    requests_made = 0
    response_bytes_received = 0

    def assert_robinhood(self):
        return None


def _common_args(tmp_path, *, events, registry, feeds, prefix):
    return SimpleNamespace(
        events=str(events),
        registry=str(registry),
        from_block=10,
        to_block=20,
        chunk_size=200,
        min_chunk_size=25,
        usd_anchor_pool="0x" + "99" * 20,
        oracle_state=None,
        oracle_events=None,
        quote_feeds=str(feeds),
        out=str(tmp_path / f"{prefix}-points.jsonl"),
        summary_out=str(tmp_path / f"{prefix}-summary.jsonl"),
    )


def test_launchpad_parsers_accept_sparse_quote_feeds():
    parser = build_parser()
    flap = parser.parse_args([
        "rpc-flap-curve-market-cap-window",
        "--events", "events.jsonl",
        "--registry", "registry.jsonl",
        "--from-block", "10",
        "--to-block", "20",
        "--quote-feeds", "feeds.jsonl",
        "--out", "points.jsonl",
        "--summary-out", "summary.jsonl",
    ])
    assert flap.quote_feeds == "feeds.jsonl"

    trench = parser.parse_args([
        "rpc-trench-curve-market-cap-window",
        "--events", "events.jsonl",
        "--registry", "registry.jsonl",
        "--from-block", "10",
        "--to-block", "20",
        "--quote-feeds", "feeds.jsonl",
        "--out", "points.jsonl",
        "--summary-out", "summary.jsonl",
    ])
    assert trench.quote_feeds == "feeds.jsonl"


def test_flap_uses_causal_sparse_chainlink_quote(
    monkeypatch,
    tmp_path,
):
    token = "0x" + "11" * 20
    quote = "0x" + "22" * 20
    events = tmp_path / "events.jsonl"
    registry = tmp_path / "registry.jsonl"
    feeds = tmp_path / "feeds.jsonl"

    _write_jsonl(events, [
        {
            "event_type": "token_created",
            "token": token,
            "actor": "0x" + "33" * 20,
            "amount_raw": None,
            "quote_amount_raw": None,
            "fee_raw": None,
            "post_price_raw": None,
            "value_raw": 1,
            "value2_raw": None,
            "pool": None,
            "name": "T",
            "symbol": "T",
            "meta": None,
            "block_number": 10,
            "transaction_hash": "0x" + "01" * 32,
            "transaction_index": 1,
            "log_index": 0,
        },
        {
            "event_type": "quote_set",
            "token": token,
            "actor": quote,
            "amount_raw": None,
            "quote_amount_raw": None,
            "fee_raw": None,
            "post_price_raw": None,
            "value_raw": None,
            "value2_raw": None,
            "pool": None,
            "name": None,
            "symbol": None,
            "meta": None,
            "block_number": 10,
            "transaction_hash": "0x" + "01" * 32,
            "transaction_index": 1,
            "log_index": 1,
        },
        {
            "event_type": "token_bought",
            "token": token,
            "actor": "0x" + "44" * 20,
            "amount_raw": 1,
            "quote_amount_raw": 1,
            "fee_raw": 0,
            "post_price_raw": 10**18,
            "value_raw": None,
            "value2_raw": None,
            "pool": None,
            "name": None,
            "symbol": None,
            "meta": None,
            "block_number": 10,
            "transaction_hash": "0x" + "01" * 32,
            "transaction_index": 2,
            "log_index": 0,
        },
    ])
    _write_jsonl(registry, [{
        "token": token,
        "quote_token": quote,
        "launch_block": 10,
        "launch_transaction_index": 1,
        "launch_log_index": 0,
        "quote_set_block": 10,
        "quote_set_transaction_index": 1,
        "quote_set_log_index": 1,
    }])
    _write_jsonl(feeds, [{
        "quote_token": quote,
        "symbol": "TEST",
        "feed": "0x" + "55" * 20,
        "pricing_status": "priced_chainlink_stock_token",
    }])

    monkeypatch.setattr("hlp.cli._archive_rpc", lambda args: FakeRpc())
    monkeypatch.setattr(
        "hlp.cli._sparse_weth_usd_anchors",
        lambda *args, **kwargs: (Decimal("2000"), [], 200),
    )
    captured = {}

    def fake_sparse(rpc, targets, *, feed_specs, window_size):
        rows = list(targets)
        captured["targets"] = rows
        captured["window_size"] = window_size
        return [{
            "quote_token": row["quote_token"],
            "block_number": row["block_number"],
            "transaction_index": row["transaction_index"],
            "log_index": row["log_index"],
            "usd_price": "2",
            "pricing_status": "priced_chainlink_stock_token",
            "pricing_source": "sparse_chainlink_state_and_updates",
            "window_from_block": 0,
        } for row in rows]

    monkeypatch.setattr(
        "hlp.cli.build_sparse_chainlink_usd_points",
        fake_sparse,
    )
    args = _common_args(
        tmp_path,
        events=events,
        registry=registry,
        feeds=feeds,
        prefix="flap",
    )
    assert cmd_rpc_flap_curve_market_cap_window(args) == 0
    assert len(captured["targets"]) == 1
    assert captured["targets"][0]["quote_token"] == quote
    assert captured["window_size"] == 200

    points = [
        json.loads(line)
        for line in (tmp_path / "flap-points.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert points[0]["quote_usd"] == "2"
    assert points[0]["market_cap_proxy_usd"] == "2000000000"


def test_trench_uses_sparse_chainlink_launch_quote(
    monkeypatch,
    tmp_path,
):
    token = "0x" + "11" * 20
    quote = "0x" + "22" * 20
    events = tmp_path / "events.jsonl"
    registry = tmp_path / "registry.jsonl"
    feeds = tmp_path / "feeds.jsonl"

    _write_jsonl(events, [{
        "event_type": "sync",
        "token": token,
        "actor": None,
        "curve": None,
        "quote_token": None,
        "amount_raw": None,
        "quote_amount_raw": None,
        "protocol_fee_raw": None,
        "extra_fee_raw": None,
        "extra_fee_receiver": None,
        "extra_fee_rate": None,
        "real_quote_reserves_raw": 1,
        "real_token_reserves_raw": 1,
        "virtual_quote_raw": 10**18,
        "virtual_token_raw": 10**18,
        "name": None,
        "symbol": None,
        "token_uri": None,
        "timestamp": None,
        "block_number": 10,
        "transaction_hash": "0x" + "02" * 32,
        "transaction_index": 2,
        "log_index": 0,
    }])
    _write_jsonl(registry, [{
        "token": token,
        "curve": "0x" + "66" * 20,
        "quote_token": quote,
        "launch_block": 9,
        "launch_transaction_index": 1,
        "launch_log_index": 0,
        "supply_raw": 1_000_000_000 * 10**18,
        "token_decimals": 18,
        "quote_decimals": 18,
    }])
    _write_jsonl(feeds, [{
        "quote_token": quote,
        "symbol": "TEST",
        "feed": "0x" + "55" * 20,
        "pricing_status": "priced_chainlink_stock_token",
    }])

    monkeypatch.setattr("hlp.cli._archive_rpc", lambda args: FakeRpc())
    monkeypatch.setattr(
        "hlp.cli._sparse_weth_usd_anchors",
        lambda *args, **kwargs: (Decimal("2000"), [], 200),
    )

    def fake_sparse(rpc, targets, *, feed_specs, window_size):
        rows = list(targets)
        return [{
            "quote_token": row["quote_token"],
            "block_number": row["block_number"],
            "transaction_index": row["transaction_index"],
            "log_index": row["log_index"],
            "usd_price": "3",
            "pricing_status": "priced_chainlink_stock_token",
            "pricing_source": "sparse_chainlink_state_and_updates",
            "window_from_block": 0,
        } for row in rows]

    monkeypatch.setattr(
        "hlp.cli.build_sparse_chainlink_usd_points",
        fake_sparse,
    )
    args = _common_args(
        tmp_path,
        events=events,
        registry=registry,
        feeds=feeds,
        prefix="trench",
    )
    assert cmd_rpc_trench_curve_market_cap_window(args) == 0

    points = [
        json.loads(line)
        for line in (tmp_path / "trench-points.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert points[0]["quote_usd"] == "3"
    assert points[0]["market_cap_proxy_usd"] == "3000000000"
