import json
from decimal import Decimal
from types import SimpleNamespace

from hlp.cli import (
    build_parser,
    cmd_phase2_noxa_initialized_registry,
    cmd_phase2_noxa_market_window,
    cmd_rpc_noxa_registry_window,
)
from hlp.config import ROBINHOOD_WETH
from hlp.data.types import InstantV3Launch, NoxaLaunchedToken


TOKEN = "0x" + "11" * 20
QUOTE = "0x" + "22" * 20
POOL = "0x" + "33" * 20
FACTORY = "0x" + "44" * 20
DEPLOYER = "0x" + "55" * 20
POSITION_MANAGER = "0x" + "66" * 20


class FakeRpc:
    route_label = "test_archive"
    requests_made = 3
    response_bytes_received = 100

    def assert_robinhood(self):
        return None

    def iter_logs_chunked(self, *args, **kwargs):
        return [object()]


def test_noxa_phase2_parsers():
    parser = build_parser()
    registry = parser.parse_args([
        "rpc-noxa-registry-window",
        "--from-block", "10",
        "--to-block", "20",
        "--out", "registry.jsonl",
    ])
    assert registry.from_block == 10

    initialized = parser.parse_args([
        "phase2-noxa-initialized-registry",
        "--registry", "registry.jsonl",
        "--initializes", "init.jsonl",
        "--out", "initialized.jsonl",
        "--summary-out", "summary.json",
    ])
    assert initialized.initializes == "init.jsonl"

    market = parser.parse_args([
        "phase2-noxa-market-window",
        "--registry", "initialized.jsonl",
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
    assert market.supply_deltas == "supply.jsonl"


def test_rpc_noxa_registry_window_reads_state_at_launch_block(
    monkeypatch,
    tmp_path,
):
    launch = InstantV3Launch(
        venue="noxa",
        factory="0x" + "77" * 20,
        token=TOKEN,
        deployer=DEPLOYER,
        dex_factory=FACTORY,
        pair_token=QUOTE,
        pool=POOL,
        dex_id=1,
        launch_config_id=2,
        position_id=3,
        restrictions_end_block=99,
        initial_buy_amount=4,
        block_number=15,
        transaction_hash="0x" + "01" * 32,
        transaction_index=1,
        log_index=2,
    )
    state = NoxaLaunchedToken(
        token=TOKEN,
        deployer=DEPLOYER,
        paired_token=QUOTE,
        position_manager=POSITION_MANAGER,
        position_id=3,
        dex_id=1,
        launch_config_id=2,
        restrictions_end_block=99,
        supply=1_000_000_000 * 10**18,
        block_number=15,
    )
    monkeypatch.setattr("hlp.cli._archive_rpc", lambda args: FakeRpc())
    monkeypatch.setattr("hlp.cli.decode_noxa_launch", lambda raw: launch)
    observed = {}

    def fake_state(rpc, token, *, block):
        observed["token"] = token
        observed["block"] = block
        return state

    monkeypatch.setattr(
        "hlp.cli.read_noxa_launched_token",
        fake_state,
    )
    out = tmp_path / "registry.jsonl"
    args = SimpleNamespace(
        from_block=10,
        to_block=20,
        chunk_size=200,
        min_chunk_size=25,
        out=str(out),
    )
    assert cmd_rpc_noxa_registry_window(args) == 0
    assert observed == {"token": TOKEN, "block": 15}
    rows = [
        json.loads(line)
        for line in out.read_text().splitlines()
        if line.strip()
    ]
    assert rows[0]["pool"] == POOL
    assert rows[0]["supply_raw"] == 1_000_000_000 * 10**18


def test_noxa_initialized_registry_cli(tmp_path):
    registry = tmp_path / "registry.jsonl"
    initializes = tmp_path / "init.jsonl"
    out = tmp_path / "initialized.jsonl"
    summary = tmp_path / "summary.json"
    registry.write_text(json.dumps({
        "venue": "noxa",
        "launch_kind": "instant_v3",
        "token": TOKEN,
        "quote_token": QUOTE,
        "pool": POOL,
        "supply_raw": 10**18,
        "launch_block": 10,
        "launch_transaction_index": 1,
        "launch_log_index": 2,
    }) + "\n")
    initializes.write_text(json.dumps({
        "pool": POOL,
        "sqrt_price_x96": 2**96,
        "tick": 0,
        "block_number": 10,
        "transaction_hash": "0x" + "02" * 32,
        "transaction_index": 2,
        "log_index": 3,
    }) + "\n")
    args = SimpleNamespace(
        registry=str(registry),
        initializes=str(initializes),
        out=str(out),
        summary_out=str(summary),
    )
    assert cmd_phase2_noxa_initialized_registry(args) == 0
    report = json.loads(summary.read_text())
    assert report["source_id"] == "noxa"
    assert report["launches"] == 1
    assert report["source_coverage_complete"] is False


def test_noxa_market_window_replays_launch_seed_supply(
    monkeypatch,
    tmp_path,
):
    quote = ROBINHOOD_WETH.lower()
    registry = tmp_path / "initialized.jsonl"
    swaps = tmp_path / "swaps.jsonl"
    supply = tmp_path / "supply.jsonl"
    decimals = tmp_path / "quotes.json"
    feeds = tmp_path / "feeds.jsonl"
    points = tmp_path / "points.jsonl"
    summary = tmp_path / "summary.jsonl"
    report = tmp_path / "report.json"

    registry.write_text(json.dumps({
        "venue": "noxa",
        "launch_kind": "instant_v3",
        "token": TOKEN,
        "quote_token": quote,
        "pool": POOL,
        "supply_raw": 10**18,
        "launch_block": 10,
        "launch_transaction_hash": "0x" + "10" * 32,
        "launch_transaction_index": 1,
        "launch_log_index": 2,
        "initialize_block": 10,
        "initialize_transaction_hash": "0x" + "20" * 32,
        "initialize_transaction_index": 2,
        "initialize_log_index": 3,
        "initial_sqrt_price_x96": 2**96,
        "initial_tick": 0,
    }, sort_keys=True) + "\n")
    swaps.write_text(json.dumps({
        "pool": POOL,
        "sender": "0x" + "77" * 20,
        "recipient": "0x" + "88" * 20,
        "amount0": -(10**18),
        "amount1": 10**18,
        "sqrt_price_x96": 2**96,
        "liquidity": 1_000 * 10**18,
        "tick": 0,
        "block_number": 11,
        "transaction_hash": "0x" + "30" * 32,
        "transaction_index": 1,
        "log_index": 0,
    }, sort_keys=True) + "\n")
    supply.write_text(json.dumps({
        "token": TOKEN,
        "from_address": "0x" + "00" * 20,
        "to_address": "0x" + "99" * 20,
        "value_raw": 10**17,
        "supply_delta_raw": 10**17,
        "is_mint": True,
        "is_burn": False,
        "block_number": 11,
        "transaction_hash": "0x" + "40" * 32,
        "transaction_index": 0,
        "log_index": 0,
    }, sort_keys=True) + "\n")
    decimals.write_text(json.dumps({quote: 18}))
    feeds.write_text("")

    class MarketRpc:
        route_label = "test_archive"
        requests_made = 0
        response_bytes_received = 0

        def assert_robinhood(self):
            return None

    monkeypatch.setattr("hlp.cli._archive_rpc", lambda args: MarketRpc())
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
        quote_decimals=str(decimals),
        quote_feeds=str(feeds),
        usd_anchor_pool="0x" + "aa" * 20,
        chunk_size=100_000,
        min_chunk_size=25,
        out=str(points),
        summary_out=str(summary),
        report_out=str(report),
    )
    assert cmd_phase2_noxa_market_window(args) == 0

    rows = [
        json.loads(line)
        for line in points.read_text().splitlines()
        if line.strip()
    ]
    assert len(rows) == 2
    assert rows[0]["supply_raw"] == 10**18
    assert rows[1]["supply_raw"] == 11 * 10**17
    assert all(row["source_id"] == "noxa" for row in rows)
    payload = json.loads(report.read_text())
    assert payload["unpriced_points"] == 0
    assert payload["supply_delta_events"] == 1
    assert payload["source_coverage_complete"] is False

