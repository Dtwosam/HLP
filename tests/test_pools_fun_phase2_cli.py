import json
from decimal import Decimal
from types import SimpleNamespace

from hlp.cli import (
    build_parser,
    cmd_phase2_pools_fun_market_window,
    cmd_phase2_v3_registry_event_filter,
    cmd_pools_fun_initialized_registry,
)
from hlp.config import ROBINHOOD_WETH


TOKEN = "0x" + "11" * 20
POOL = "0x" + "22" * 20
QUOTE = ROBINHOOD_WETH.lower()


def write_jsonl(path, rows):
    path.write_text(
        "".join(
            json.dumps(row, sort_keys=True) + "\n"
            for row in rows
        )
    )


def launch_registry_row():
    return {
        "venue": "pools.fun",
        "launch_kind": "instant_sushi_v3",
        "token": TOKEN,
        "pool": POOL,
        "quote_token": QUOTE,
        "creator": "0x" + "33" * 20,
        "deployer": "0x" + "44" * 20,
        "fee_recipient": "0x" + "55" * 20,
        "start_tick": 0,
        "metadata_uri": "ipfs://x",
        "dev_buy_amount_out": 0,
        "supply_raw": 1_000_000_000 * 10**18,
        "token_decimals": 18,
        "launch_block": 10,
        "launch_transaction_hash": "0x" + "aa" * 32,
        "launch_transaction_index": 1,
        "launch_log_index": 2,
    }


def initialized_registry_row():
    return {
        **launch_registry_row(),
        "initialize_block": 10,
        "initialize_transaction_hash": "0x" + "bb" * 32,
        "initialize_transaction_index": 1,
        "initialize_log_index": 1,
        "initial_sqrt_price_x96": 2**96,
        "initial_tick": 0,
    }


def test_phase2_pools_fun_parsers():
    parser = build_parser()
    initialized = parser.parse_args([
        "phase2-pools-fun-initialized-registry",
        "--registry", "registry.jsonl",
        "--initializes", "init.jsonl",
        "--out", "enriched.jsonl",
        "--summary-out", "summary.json",
    ])
    assert initialized.registry == "registry.jsonl"

    filtered = parser.parse_args([
        "phase2-v3-registry-event-filter",
        "--registry", "registry.jsonl",
        "--input-manifest", "swaps.manifest.json",
        "--input-shard-dir", "inputs",
        "--out", "filtered.jsonl",
        "--summary-out", "filter.json",
    ])
    assert filtered.input is None
    assert filtered.input_manifest == "swaps.manifest.json"

    market = parser.parse_args([
        "phase2-pools-fun-market-window",
        "--registry", "enriched.jsonl",
        "--swaps", "filtered.jsonl",
        "--from-block", "10",
        "--to-block", "20",
        "--quote-decimals", "quotes.json",
        "--quote-feeds", "feeds.jsonl",
        "--out", "points.jsonl",
        "--summary-out", "tokens.jsonl",
        "--report-out", "report.json",
    ])
    assert market.quote_decimals == "quotes.json"
    assert market.quote_feeds == "feeds.jsonl"


def test_v3_registry_event_filter_keeps_only_registered_pool(tmp_path):
    registry = tmp_path / "registry.jsonl"
    events = tmp_path / "events.jsonl"
    out = tmp_path / "filtered.jsonl"
    summary = tmp_path / "summary.json"
    write_jsonl(registry, [launch_registry_row()])
    write_jsonl(events, [
        {
            "pool": POOL,
            "block_number": 11,
            "transaction_hash": "0x" + "01" * 32,
            "transaction_index": 1,
            "log_index": 0,
        },
        {
            "pool": "0x" + "99" * 20,
            "block_number": 11,
            "transaction_hash": "0x" + "02" * 32,
            "transaction_index": 1,
            "log_index": 1,
        },
    ])

    args = SimpleNamespace(
        registry=str(registry),
        input=str(events),
        input_manifest=None,
        input_shard_dir=None,
        out=str(out),
        summary_out=str(summary),
    )
    assert cmd_phase2_v3_registry_event_filter(args) == 0
    rows = [
        json.loads(line)
        for line in out.read_text().splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["pool"] == POOL
    report = json.loads(summary.read_text())
    assert report["records"] == 1
    assert report["matched_pools"] == 1


def test_pools_fun_initialized_registry_command(tmp_path):
    registry = tmp_path / "registry.jsonl"
    initializes = tmp_path / "initializes.jsonl"
    out = tmp_path / "enriched.jsonl"
    summary = tmp_path / "summary.json"
    write_jsonl(registry, [launch_registry_row()])
    write_jsonl(initializes, [{
        "pool": POOL,
        "sqrt_price_x96": 2**96,
        "tick": 0,
        "block_number": 10,
        "transaction_hash": "0x" + "bb" * 32,
        "transaction_index": 1,
        "log_index": 1,
    }])

    args = SimpleNamespace(
        registry=str(registry),
        initializes=str(initializes),
        out=str(out),
        summary_out=str(summary),
    )
    assert cmd_pools_fun_initialized_registry(args) == 0
    row = json.loads(out.read_text().strip())
    assert row["initialize_block"] == 10
    report = json.loads(summary.read_text())
    assert report["all_pools_initialized"] is True
    assert report["source_coverage_complete"] is False


def test_pools_fun_market_window_reuses_sparse_weth_anchor(
    monkeypatch,
    tmp_path,
):
    registry = tmp_path / "registry.jsonl"
    swaps = tmp_path / "swaps.jsonl"
    decimals = tmp_path / "quotes.json"
    feeds = tmp_path / "feeds.jsonl"
    points = tmp_path / "points.jsonl"
    summary = tmp_path / "summary.jsonl"
    report = tmp_path / "report.json"
    write_jsonl(registry, [initialized_registry_row()])
    write_jsonl(swaps, [{
        "pool": POOL,
        "sender": "0x" + "66" * 20,
        "recipient": "0x" + "77" * 20,
        "amount0": -10**18,
        "amount1": 10**18,
        "sqrt_price_x96": 2**96,
        "liquidity": 1_000 * 10**18,
        "tick": 0,
        "block_number": 11,
        "transaction_hash": "0x" + "cc" * 32,
        "transaction_index": 1,
        "log_index": 0,
    }])
    decimals.write_text(json.dumps({QUOTE: 18}))
    feeds.write_text("")

    class FakeRpc:
        route_label = "test_archive"
        requests_made = 0
        response_bytes_received = 0

        def assert_robinhood(self):
            return None

    monkeypatch.setattr("hlp.cli._archive_rpc", lambda args: FakeRpc())
    monkeypatch.setattr(
        "hlp.cli._sparse_weth_usd_anchors",
        lambda *args, **kwargs: (Decimal("2000"), [], 200),
    )

    args = SimpleNamespace(
        registry=str(registry),
        swaps=str(swaps),
        from_block=10,
        to_block=20,
        quote_decimals=str(decimals),
        quote_feeds=str(feeds),
        usd_anchor_pool="0x" + "88" * 20,
        chunk_size=100_000,
        min_chunk_size=25,
        out=str(points),
        summary_out=str(summary),
        report_out=str(report),
    )
    assert cmd_phase2_pools_fun_market_window(args) == 0

    point_rows = [
        json.loads(line)
        for line in points.read_text().splitlines()
        if line.strip()
    ]
    assert len(point_rows) == 2
    assert all(row["source_id"] == "pools_fun" for row in point_rows)
    assert all(row["market_cap_proxy_usd"] is not None for row in point_rows)

    payload = json.loads(report.read_text())
    assert payload["initialize_events"] == 1
    assert payload["swap_events"] == 1
    assert payload["market_cap_points"] == 2
    assert payload["unpriced_points"] == 0
    assert payload["source_coverage_complete"] is False
