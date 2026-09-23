import json
from decimal import Decimal
from types import SimpleNamespace

from hlp.cli import (
    build_parser,
    cmd_phase2_pools_trade_instant_market_window,
)
from hlp.config import ROBINHOOD_WETH


TOKEN = "0x" + "11" * 20
POOL_ID = "0x" + "22" * 32
QUOTE = ROBINHOOD_WETH.lower()
TX = "0x" + "aa" * 32


def write_jsonl(path, rows):
    path.write_text(
        "".join(
            json.dumps(row, sort_keys=True) + "\n"
            for row in rows
        )
    )


def registry_row():
    return {
        "source_id": "pools_trade_instant",
        "source_kind": "launchpad",
        "venue": "pools.trade",
        "launch_kind": "instant_v4",
        "token": TOKEN,
        "quote_token": QUOTE,
        "distribution_amount_raw": 900_000_000 * 10**18,
        "supply_raw": 1_000_000_000 * 10**18,
        "token_decimals": 18,
        "supply_seed_semantics": (
            "initialize-block-end totalSupply; replay later "
            "mint/burn Transfer deltas causally"
        ),
        "state_block": 10,
        "pool_id": POOL_ID,
        "currency0": TOKEN,
        "currency1": QUOTE,
        "fee": 10000,
        "tick_spacing": 200,
        "hooks": "0x" + "33" * 20,
        "created_block": 9,
        "launch_block": 10,
        "launch_transaction_hash": TX,
        "launch_transaction_index": 1,
        "launch_log_index": 2,
        "initialize_block": 10,
        "initialize_transaction_hash": TX,
        "initialize_transaction_index": 1,
        "initialize_log_index": 3,
        "initial_sqrt_price_x96": 2**96,
        "initial_tick": 0,
    }


def test_pools_trade_instant_market_window_parser():
    args = build_parser().parse_args([
        "phase2-pools-trade-instant-market-window",
        "--registry", "registry.jsonl",
        "--swaps", "swaps.jsonl",
        "--supply-deltas", "supply.jsonl",
        "--from-block", "10",
        "--to-block", "20",
        "--quote-decimals", "quotes.json",
        "--quote-feeds", "feeds.jsonl",
        "--out", "points.jsonl",
        "--summary-out", "summary.jsonl",
        "--report-out", "report.json",
    ])
    assert args.registry == "registry.jsonl"
    assert args.supply_deltas == "supply.jsonl"


def test_pools_trade_instant_market_window_prices_causal_supply(
    monkeypatch,
    tmp_path,
):
    registry = tmp_path / "registry.jsonl"
    swaps = tmp_path / "swaps.jsonl"
    supply = tmp_path / "supply.jsonl"
    decimals = tmp_path / "quotes.json"
    feeds = tmp_path / "feeds.jsonl"
    points = tmp_path / "points.jsonl"
    summary = tmp_path / "summary.jsonl"
    report = tmp_path / "report.json"

    write_jsonl(registry, [registry_row()])
    write_jsonl(swaps, [{
        "pool_id": POOL_ID,
        "sender": "0x" + "66" * 20,
        "amount0": -10**18,
        "amount1": 10**18,
        "sqrt_price_x96": 2**96,
        "liquidity": 1_000 * 10**18,
        "tick": 0,
        "block_number": 12,
        "transaction_hash": "0x" + "bb" * 32,
        "transaction_index": 1,
        "log_index": 0,
    }])
    write_jsonl(supply, [{
        "token": TOKEN,
        "from_address": TOKEN,
        "to_address": "0x" + "00" * 20,
        "value_raw": 100_000_000 * 10**18,
        "supply_delta_raw": -100_000_000 * 10**18,
        "is_mint": False,
        "is_burn": True,
        "block_number": 11,
        "transaction_hash": "0x" + "cc" * 32,
        "transaction_index": 1,
        "log_index": 0,
    }])
    decimals.write_text(json.dumps({QUOTE: 18}) + "\n")
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
        supply_deltas=str(supply),
        from_block=10,
        to_block=20,
        chunk_size=200,
        min_chunk_size=25,
        usd_anchor_pool="0x" + "77" * 20,
        quote_decimals=str(decimals),
        quote_feeds=str(feeds),
        out=str(points),
        summary_out=str(summary),
        report_out=str(report),
    )
    assert cmd_phase2_pools_trade_instant_market_window(args) == 0

    rows = [
        json.loads(line)
        for line in points.read_text().splitlines()
        if line.strip()
    ]
    assert [row["event_type"] for row in rows] == [
        "v4_initialize",
        "v4_swap",
    ]
    assert rows[0]["supply_raw"] == 1_000_000_000 * 10**18
    assert rows[1]["supply_raw"] == 900_000_000 * 10**18
    assert all(
        row["source_id"] == "pools_trade_instant"
        for row in rows
    )

    payload = json.loads(report.read_text())
    assert payload["initialize_events"] == 1
    assert payload["swap_events"] == 1
    assert payload["unpriced_points"] == 0
    assert payload["source_coverage_complete"] is False


def test_pools_trade_instant_empty_window_needs_no_rpc(
    monkeypatch,
    tmp_path,
):
    registry = tmp_path / "registry.jsonl"
    swaps = tmp_path / "swaps.jsonl"
    supply = tmp_path / "supply.jsonl"
    decimals = tmp_path / "quotes.json"
    feeds = tmp_path / "feeds.jsonl"
    points = tmp_path / "points.jsonl"
    summary = tmp_path / "summary.jsonl"
    report = tmp_path / "report.json"

    write_jsonl(registry, [registry_row()])
    swaps.write_text("")
    supply.write_text("")
    decimals.write_text(json.dumps({QUOTE: 18}) + "\n")
    feeds.write_text("")
    monkeypatch.setattr(
        "hlp.cli._archive_rpc",
        lambda args: (_ for _ in ()).throw(
            AssertionError("empty shard should not open RPC")
        ),
    )

    args = SimpleNamespace(
        registry=str(registry),
        swaps=str(swaps),
        supply_deltas=str(supply),
        from_block=1,
        to_block=9,
        chunk_size=200,
        min_chunk_size=25,
        usd_anchor_pool="0x" + "77" * 20,
        quote_decimals=str(decimals),
        quote_feeds=str(feeds),
        out=str(points),
        summary_out=str(summary),
        report_out=str(report),
    )
    assert cmd_phase2_pools_trade_instant_market_window(args) == 0
    payload = json.loads(report.read_text())
    assert payload["empty_window"] is True
