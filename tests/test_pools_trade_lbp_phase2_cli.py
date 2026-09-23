import json
from decimal import Decimal
from types import SimpleNamespace

from hlp.cli import (
    build_parser,
    cmd_phase2_pools_trade_lbp_cca_market_window,
    cmd_phase2_pools_trade_lbp_migrated_registry,
    cmd_phase2_pools_trade_lbp_v4_market_window,
    cmd_rpc_pools_trade_lbp_cca_window,
    cmd_rpc_pools_trade_lbp_initializer_tape,
)
from hlp.data.types import (
    CcaPriceEvent,
    PoolsTradeLbpInitializerCreated,
)
from hlp.protocols.erc20 import Erc20StaticState


TOKEN = "0x" + "11" * 20


class FakeRpc:
    route_label = "test_archive"
    requests_made = 2
    response_bytes_received = 100

    def assert_robinhood(self):
        return None

    def iter_logs_chunked(self, *args, **kwargs):
        return [object()]


def initializer():
    return PoolsTradeLbpInitializerCreated(
        strategy="0x05d552391067389ee44fec3924157ed33f976000",
        initializer="0x" + "22" * 20,
        token=TOKEN,
        currency="0x" + "00" * 20,
        migration_block=20,
        reserved_token_amount_for_lp=200,
        recipient="0x" + "33" * 20,
        position_recipient="0x" + "44" * 20,
        pool_fee=2500,
        pool_tick_spacing=50,
        pool_hook="0x" + "00" * 20,
        position_definitions_offset=352,
        lp_allocation_schedule_offset=576,
        block_number=10,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=1,
        log_index=2,
    )


def test_lbp_initializer_parser_accepts_state_out():
    args = build_parser().parse_args([
        "rpc-pools-trade-lbp-initializer-tape",
        "--from-block", "10",
        "--to-block", "20",
        "--out", "initializers.jsonl",
        "--state-out", "state.jsonl",
    ])
    assert args.state_out == "state.jsonl"


def test_lbp_registry_parser_accepts_states():
    args = build_parser().parse_args([
        "pools-trade-lbp-registry",
        "--created", "created.jsonl",
        "--distributed", "distributed.jsonl",
        "--initializers", "initializers.jsonl",
        "--states", "state.jsonl",
        "--out", "registry.jsonl",
    ])
    assert args.states == "state.jsonl"


def test_lbp_initializer_tape_freezes_exact_block_state(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr("hlp.cli._archive_rpc", lambda args: FakeRpc())
    monkeypatch.setattr(
        "hlp.cli.decode_pools_trade_lbp_initializer_created",
        lambda raw: initializer(),
    )
    observed = {}

    def fake_static(rpc, token, *, block):
        observed["token"] = token
        observed["block"] = block
        return Erc20StaticState(
            token=token,
            block_number=block,
            decimals=18,
            total_supply=1000,
        )

    monkeypatch.setattr("hlp.cli.read_erc20_static", fake_static)
    init_path = tmp_path / "initializers.jsonl"
    state_path = tmp_path / "state.jsonl"
    args = SimpleNamespace(
        from_block=10,
        to_block=20,
        chunk_size=200,
        min_chunk_size=25,
        out=str(init_path),
        state_out=str(state_path),
    )

    assert cmd_rpc_pools_trade_lbp_initializer_tape(args) == 0
    assert observed == {"token": TOKEN, "block": 10}
    state = json.loads(state_path.read_text().strip())
    assert state == {
        "token": TOKEN,
        "state_block": 10,
        "token_decimals": 18,
        "supply_raw": 1000,
    }


def _write_jsonl(path, rows):
    path.write_text(
        "".join(
            json.dumps(row, sort_keys=True) + "\n"
            for row in rows
        )
    )


def test_lbp_cca_market_window_parser():
    args = build_parser().parse_args([
        "phase2-pools-trade-lbp-cca-market-window",
        "--registry", "registry.jsonl",
        "--events", "cca.jsonl",
        "--supply-deltas", "supply.jsonl",
        "--orientation-evidence", "orientation.json",
        "--from-block", "10",
        "--to-block", "20",
        "--quote-decimals", "quotes.json",
        "--quote-feeds", "feeds.jsonl",
        "--out", "points.jsonl",
        "--summary-out", "summary.jsonl",
        "--report-out", "report.json",
    ])
    assert args.registry == "registry.jsonl"
    assert args.orientation_evidence == "orientation.json"


def test_lbp_cca_market_window_prices_causal_supply(
    monkeypatch,
    tmp_path,
):
    initializer_address = "0x" + "22" * 20
    zero = "0x" + "00" * 20
    registry_path = tmp_path / "registry.jsonl"
    events_path = tmp_path / "cca.jsonl"
    supply_path = tmp_path / "supply.jsonl"
    orientation_path = tmp_path / "orientation.json"
    decimals_path = tmp_path / "quotes.json"
    feeds_path = tmp_path / "feeds.jsonl"
    points_path = tmp_path / "points.jsonl"
    summary_path = tmp_path / "summary.jsonl"
    report_path = tmp_path / "report.json"

    _write_jsonl(registry_path, [{
        "venue": "pools.trade",
        "launch_kind": "crowd_lbp",
        "token": TOKEN,
        "quote_token": zero,
        "supply_raw": 1_000_000_000 * 10**18,
        "initializer": initializer_address,
        "initializer_block": 10,
        "initializer_transaction_hash": "0x" + "aa" * 32,
        "initializer_transaction_index": 1,
        "initializer_log_index": 1,
        "migration_block": 20,
        "pool_id": "0x" + "44" * 32,
    }])
    _write_jsonl(events_path, [{
        "auction": initializer_address,
        "event_type": "checkpoint",
        "checkpoint_block": 12,
        "clearing_price_x96": 2**96,
        "cumulative_mps": 1,
        "block_number": 12,
        "transaction_hash": "0x" + "bb" * 32,
        "transaction_index": 1,
        "log_index": 0,
    }])
    _write_jsonl(supply_path, [{
        "token": TOKEN,
        "from_address": TOKEN,
        "to_address": zero,
        "value_raw": 100_000_000 * 10**18,
        "supply_delta_raw": -100_000_000 * 10**18,
        "is_mint": False,
        "is_burn": True,
        "block_number": 11,
        "transaction_hash": "0x" + "cc" * 32,
        "transaction_index": 1,
        "log_index": 0,
    }])
    orientation_path.write_text("{}\n")
    decimals_path.write_text(json.dumps({zero: 18}) + "\n")
    feeds_path.write_text("")

    class MarketRpc:
        route_label = "test_archive"
        requests_made = 0
        response_bytes_received = 0

        def assert_robinhood(self):
            return None

    monkeypatch.setattr(
        "hlp.cli.validate_pools_trade_cca_orientation",
        lambda row: {"orientation": "quote_per_token"},
    )
    monkeypatch.setattr(
        "hlp.cli._archive_rpc",
        lambda args: MarketRpc(),
    )
    monkeypatch.setattr(
        "hlp.cli._sparse_weth_usd_anchors",
        lambda *args, **kwargs: (Decimal("2000"), [], 200),
    )

    args = SimpleNamespace(
        registry=str(registry_path),
        events=str(events_path),
        supply_deltas=str(supply_path),
        orientation_evidence=str(orientation_path),
        from_block=10,
        to_block=20,
        chunk_size=200,
        min_chunk_size=25,
        usd_anchor_pool="0x" + "77" * 20,
        quote_decimals=str(decimals_path),
        quote_feeds=str(feeds_path),
        out=str(points_path),
        summary_out=str(summary_path),
        report_out=str(report_path),
    )
    assert cmd_phase2_pools_trade_lbp_cca_market_window(args) == 0

    rows = [
        json.loads(line)
        for line in points_path.read_text().splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["source_id"] == "pools_trade_lbp"
    assert rows[0]["supply_raw"] == 900_000_000 * 10**18
    assert rows[0]["orientation"] == "quote_per_token"

    report = json.loads(report_path.read_text())
    assert report["cca_events"] == 1
    assert report["unpriced_points"] == 0
    assert report["source_coverage_complete"] is False


def test_lbp_cca_empty_window_needs_no_rpc(
    monkeypatch,
    tmp_path,
):
    zero = "0x" + "00" * 20
    registry_path = tmp_path / "registry.jsonl"
    events_path = tmp_path / "cca.jsonl"
    supply_path = tmp_path / "supply.jsonl"
    orientation_path = tmp_path / "orientation.json"
    decimals_path = tmp_path / "quotes.json"
    feeds_path = tmp_path / "feeds.jsonl"
    points_path = tmp_path / "points.jsonl"
    summary_path = tmp_path / "summary.jsonl"
    report_path = tmp_path / "report.json"

    _write_jsonl(registry_path, [{
        "venue": "pools.trade",
        "launch_kind": "crowd_lbp",
        "token": TOKEN,
        "quote_token": zero,
        "supply_raw": 1000,
        "initializer": "0x" + "22" * 20,
        "initializer_block": 10,
        "initializer_transaction_hash": "0x" + "aa" * 32,
        "initializer_transaction_index": 1,
        "initializer_log_index": 1,
        "migration_block": 20,
        "pool_id": "0x" + "44" * 32,
    }])
    events_path.write_text("")
    supply_path.write_text("")
    orientation_path.write_text("{}\n")
    decimals_path.write_text(json.dumps({zero: 18}) + "\n")
    feeds_path.write_text("")
    monkeypatch.setattr(
        "hlp.cli.validate_pools_trade_cca_orientation",
        lambda row: {"orientation": "quote_per_token"},
    )
    monkeypatch.setattr(
        "hlp.cli._archive_rpc",
        lambda args: (_ for _ in ()).throw(
            AssertionError("empty CCA shard should not open RPC")
        ),
    )

    args = SimpleNamespace(
        registry=str(registry_path),
        events=str(events_path),
        supply_deltas=str(supply_path),
        orientation_evidence=str(orientation_path),
        from_block=21,
        to_block=30,
        chunk_size=200,
        min_chunk_size=25,
        usd_anchor_pool="0x" + "77" * 20,
        quote_decimals=str(decimals_path),
        quote_feeds=str(feeds_path),
        out=str(points_path),
        summary_out=str(summary_path),
        report_out=str(report_path),
    )
    assert cmd_phase2_pools_trade_lbp_cca_market_window(args) == 0
    report = json.loads(report_path.read_text())
    assert report["empty_window"] is True


def test_lbp_cca_window_parser():
    args = build_parser().parse_args([
        "rpc-pools-trade-lbp-cca-window",
        "--registry", "registry.jsonl",
        "--from-block", "10",
        "--to-block", "20",
        "--out", "cca.jsonl",
    ])
    assert args.registry == "registry.jsonl"
    assert args.out == "cca.jsonl"


def test_lbp_cca_window_filters_global_topic_surface(
    monkeypatch,
    tmp_path,
):
    known = "0x" + "22" * 20
    unknown = "0x" + "33" * 20
    zero = "0x" + "00" * 20
    registry_path = tmp_path / "registry.jsonl"
    output_path = tmp_path / "cca.jsonl"
    _write_jsonl(registry_path, [{
        "venue": "pools.trade",
        "launch_kind": "crowd_lbp",
        "token": TOKEN,
        "quote_token": zero,
        "supply_raw": 1000,
        "initializer": known,
        "initializer_block": 10,
        "initializer_transaction_hash": "0x" + "aa" * 32,
        "initializer_transaction_index": 1,
        "initializer_log_index": 1,
        "migration_block": 20,
        "pool_id": "0x" + "44" * 32,
    }])

    class ScanRpc:
        route_label = "test_archive"
        requests_made = 1
        response_bytes_received = 10

        def assert_robinhood(self):
            return None

        def iter_logs_chunked(self, *args, **kwargs):
            assert kwargs["address"] is None
            assert kwargs["topics"]
            return [
                SimpleNamespace(address=unknown),
                SimpleNamespace(address=known),
            ]

    monkeypatch.setattr(
        "hlp.cli._archive_rpc",
        lambda args: ScanRpc(),
    )
    monkeypatch.setattr(
        "hlp.cli.decode_pools_trade_cca_price_event",
        lambda raw: CcaPriceEvent(
            auction=known,
            event_type="checkpoint",
            checkpoint_block=12,
            clearing_price_x96=2**96,
            cumulative_mps=1,
            block_number=12,
            transaction_hash="0x" + "bb" * 32,
            transaction_index=1,
            log_index=0,
        ),
    )

    args = SimpleNamespace(
        registry=str(registry_path),
        from_block=10,
        to_block=20,
        chunk_size=200,
        min_chunk_size=25,
        out=str(output_path),
    )
    assert cmd_rpc_pools_trade_lbp_cca_window(args) == 0
    rows = [
        json.loads(line)
        for line in output_path.read_text().splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["auction"] == known
    manifest = json.loads(
        (tmp_path / "cca.jsonl.manifest.json").read_text()
    )
    provenance = manifest["provenance"]
    assert provenance["address_filter"] is None
    assert provenance["global_topic_events"] == 2
    assert provenance["ignored_non_registry_topic_events"] == 1


def _migrated_lbp_row():
    zero = "0x" + "00" * 20
    return {
        "venue": "pools.trade",
        "launch_kind": "crowd_lbp",
        "source_id": "pools_trade_lbp",
        "source_kind": "launchpad",
        "token": TOKEN,
        "quote_token": zero,
        "supply_raw": 1_000_000_000 * 10**18,
        "token_decimals": 18,
        "pool_id": "0x" + "44" * 32,
        "currency0": zero,
        "currency1": TOKEN,
        "pool_fee": 2500,
        "pool_tick_spacing": 50,
        "pool_hook": zero,
        "fee": 2500,
        "tick_spacing": 50,
        "hooks": zero,
        "initializer": "0x" + "22" * 20,
        "initializer_block": 10,
        "initializer_transaction_hash": "0x" + "aa" * 32,
        "initializer_transaction_index": 1,
        "initializer_log_index": 1,
        "migration_block": 20,
        "initialize_block": 25,
        "initialize_transaction_hash": "0x" + "bb" * 32,
        "initialize_transaction_index": 1,
        "initialize_log_index": 2,
        "initial_sqrt_price_x96": 2**96,
        "initial_tick": 0,
        "migration_delay_blocks": 5,
    }


def test_lbp_migrated_registry_parser():
    args = build_parser().parse_args([
        "phase2-pools-trade-lbp-migrated-registry",
        "--registry", "registry.jsonl",
        "--initializes", "initialize.jsonl",
        "--out", "migrated.jsonl",
        "--summary-out", "summary.json",
    ])
    assert args.initializes == "initialize.jsonl"


def test_lbp_migrated_registry_command(
    tmp_path,
):
    base = _migrated_lbp_row()
    registry = tmp_path / "registry.jsonl"
    initializes = tmp_path / "initialize.jsonl"
    output = tmp_path / "migrated.jsonl"
    summary = tmp_path / "summary.json"
    base_registry = {
        key: value
        for key, value in base.items()
        if key not in {
            "fee",
            "tick_spacing",
            "hooks",
            "initialize_block",
            "initialize_transaction_hash",
            "initialize_transaction_index",
            "initialize_log_index",
            "initial_sqrt_price_x96",
            "initial_tick",
            "migration_delay_blocks",
        }
    }
    _write_jsonl(registry, [base_registry])
    _write_jsonl(initializes, [{
        "pool_id": base["pool_id"],
        "currency0": base["currency0"],
        "currency1": base["currency1"],
        "fee": base["fee"],
        "tick_spacing": base["tick_spacing"],
        "hooks": base["hooks"],
        "sqrt_price_x96": base["initial_sqrt_price_x96"],
        "tick": base["initial_tick"],
        "block_number": base["initialize_block"],
        "transaction_hash": base["initialize_transaction_hash"],
        "transaction_index": base["initialize_transaction_index"],
        "log_index": base["initialize_log_index"],
    }])
    args = SimpleNamespace(
        registry=str(registry),
        initializes=str(initializes),
        out=str(output),
        summary_out=str(summary),
    )
    assert cmd_phase2_pools_trade_lbp_migrated_registry(args) == 0
    payload = json.loads(summary.read_text())
    assert payload["registry_tokens"] == 1
    assert payload["migrated_tokens"] == 1
    assert payload["non_migrated_tokens"] == 0


def test_lbp_v4_market_window_parser():
    args = build_parser().parse_args([
        "phase2-pools-trade-lbp-v4-market-window",
        "--registry", "migrated.jsonl",
        "--swaps", "swaps.jsonl",
        "--supply-deltas", "supply.jsonl",
        "--from-block", "20",
        "--to-block", "30",
        "--quote-decimals", "quotes.json",
        "--quote-feeds", "feeds.jsonl",
        "--out", "points.jsonl",
        "--summary-out", "summary.jsonl",
        "--report-out", "report.json",
    ])
    assert args.registry == "migrated.jsonl"


def test_lbp_v4_market_window_replays_initializer_supply(
    monkeypatch,
    tmp_path,
):
    zero = "0x" + "00" * 20
    registry = tmp_path / "migrated.jsonl"
    swaps = tmp_path / "swaps.jsonl"
    supply = tmp_path / "supply.jsonl"
    decimals = tmp_path / "quotes.json"
    feeds = tmp_path / "feeds.jsonl"
    points = tmp_path / "points.jsonl"
    summary = tmp_path / "summary.jsonl"
    report = tmp_path / "report.json"

    row = _migrated_lbp_row()
    _write_jsonl(registry, [row])
    _write_jsonl(swaps, [{
        "pool_id": row["pool_id"],
        "sender": "0x" + "66" * 20,
        "amount0": -10**18,
        "amount1": 10**18,
        "sqrt_price_x96": 2**96,
        "liquidity": 1_000 * 10**18,
        "tick": 0,
        "block_number": 27,
        "transaction_hash": "0x" + "dd" * 32,
        "transaction_index": 1,
        "log_index": 0,
    }])
    _write_jsonl(supply, [{
        "token": TOKEN,
        "from_address": TOKEN,
        "to_address": zero,
        "value_raw": 100_000_000 * 10**18,
        "supply_delta_raw": -100_000_000 * 10**18,
        "is_mint": False,
        "is_burn": True,
        "block_number": 23,
        "transaction_hash": "0x" + "cc" * 32,
        "transaction_index": 1,
        "log_index": 0,
    }])
    decimals.write_text(json.dumps({zero: 18}) + "\n")
    feeds.write_text("")

    class MarketRpc:
        route_label = "test_archive"
        requests_made = 0
        response_bytes_received = 0

        def assert_robinhood(self):
            return None

    monkeypatch.setattr(
        "hlp.cli._archive_rpc",
        lambda args: MarketRpc(),
    )
    monkeypatch.setattr(
        "hlp.cli._sparse_weth_usd_anchors",
        lambda *args, **kwargs: (Decimal("2000"), [], 200),
    )

    args = SimpleNamespace(
        registry=str(registry),
        swaps=str(swaps),
        supply_deltas=str(supply),
        from_block=20,
        to_block=30,
        chunk_size=200,
        min_chunk_size=25,
        usd_anchor_pool="0x" + "77" * 20,
        quote_decimals=str(decimals),
        quote_feeds=str(feeds),
        out=str(points),
        summary_out=str(summary),
        report_out=str(report),
    )
    assert cmd_phase2_pools_trade_lbp_v4_market_window(args) == 0
    rows = [
        json.loads(line)
        for line in points.read_text().splitlines()
        if line.strip()
    ]
    assert [item["event_type"] for item in rows] == [
        "v4_initialize",
        "v4_swap",
    ]
    assert rows[0]["supply_raw"] == 900_000_000 * 10**18
    assert rows[1]["supply_raw"] == 900_000_000 * 10**18
    assert all(
        item["source_id"] == "pools_trade_lbp"
        for item in rows
    )
    payload = json.loads(report.read_text())
    assert payload["unpriced_points"] == 0
    assert payload["source_coverage_complete"] is False

