import json
from decimal import Decimal
from types import SimpleNamespace

from hlp.cli import (
    build_parser,
    cmd_phase2_apply_source_coverage,
    cmd_phase2_direct_quote_registry,
    cmd_phase2_direct_v3_market_cap_window,
    cmd_phase2_direct_v3_registry,
    cmd_phase2_direct_v4_market_cap_window,
    cmd_phase2_direct_v4_registry,
    cmd_phase2_market_quality_audit,
    cmd_pools_trade_instant_registry,
    cmd_pools_trade_lbp_registry,
)
from hlp.data.phase2_coverage import PHASE2_COVERAGE_LEDGER_VERSION
from hlp.protocols.erc20 import Erc20StaticState


def complete(source_id):
    return {
        "source_id": source_id,
        "source_readiness": "phase1_proven",
        "coverage_status": "complete",
        "required_start_block": 10,
        "first_block": 10,
        "last_block": 100,
        "continuous": True,
        "missing_ranges": [],
        "tokens_discovered": 1,
        "price_points": 2,
        "priced_points": 2,
        "observed_volume_usd": None,
        "provenance_sha256": "ab" * 32,
        "blocking_reason": None,
    }


def pending(source_id):
    return {
        "source_id": source_id,
        "source_readiness": "adapter_ready",
        "coverage_status": "not_started",
        "required_start_block": 20,
        "first_block": None,
        "last_block": None,
        "continuous": None,
        "missing_ranges": [],
        "tokens_discovered": 0,
        "price_points": 0,
        "priced_points": 0,
        "observed_volume_usd": None,
        "provenance_sha256": None,
        "blocking_reason": None,
    }


def test_phase2_apply_source_coverage_parser():
    parser = build_parser()
    args = parser.parse_args([
        "phase2-apply-source-coverage",
        "--ledger", "ledger.json",
        "--report", "report.json",
        "--out", "updated.json",
        "--validation-out", "validation.json",
    ])
    assert args.ledger == "ledger.json"
    assert args.report == "report.json"
    assert args.out == "updated.json"


def test_phase2_apply_source_coverage_command(
    monkeypatch,
    tmp_path,
):
    inventory = [
        {"source_id": "pons_v1", "readiness": "phase1_proven"},
        {"source_id": "noxa", "readiness": "adapter_ready"},
    ]
    monkeypatch.setattr(
        "hlp.cli.build_phase2_source_inventory",
        lambda: inventory,
    )

    ledger_path = tmp_path / "ledger.json"
    report_path = tmp_path / "report.json"
    out_path = tmp_path / "updated.json"
    validation_path = tmp_path / "validation.json"

    ledger_path.write_text(json.dumps({
        "version": PHASE2_COVERAGE_LEDGER_VERSION,
        "snapshot_head_block": 100,
        "sources": [
            complete("pons_v1"),
            pending("noxa"),
        ],
    }))
    report_path.write_text(json.dumps({
        **pending("noxa"),
        "coverage_status": "complete",
        "first_block": 20,
        "last_block": 100,
        "continuous": True,
        "tokens_discovered": 3,
        "price_points": 9,
        "priced_points": 9,
        "provenance_sha256": "cd" * 32,
        "snapshot_head_block": 100,
        "extra_audit_field": "must-not-enter-ledger",
    }))

    args = SimpleNamespace(
        ledger=str(ledger_path),
        report=str(report_path),
        out=str(out_path),
        validation_out=str(validation_path),
    )
    assert cmd_phase2_apply_source_coverage(args) == 0

    updated = json.loads(out_path.read_text())
    rows = {
        row["source_id"]: row
        for row in updated["sources"]
    }
    assert rows["noxa"]["coverage_status"] == "complete"
    assert rows["noxa"]["price_points"] == 9
    assert "extra_audit_field" not in rows["noxa"]

    validation = json.loads(validation_path.read_text())
    assert validation["complete_source_ids"] == [
        "noxa",
        "pons_v1",
    ]
    assert validation["phase2_universe_coverage_complete"] is True



def test_reusable_pools_trade_tape_parsers():
    parser = build_parser()

    launcher = parser.parse_args([
        "rpc-pools-trade-launcher-tape",
        "--from-block", "10",
        "--to-block", "20",
        "--created-out", "created.jsonl",
        "--distributed-out", "distributed.jsonl",
    ])
    assert launcher.created_out == "created.jsonl"
    assert launcher.distributed_out == "distributed.jsonl"

    instant = parser.parse_args([
        "rpc-pools-trade-instant-launch-tape",
        "--from-block", "10",
        "--to-block", "20",
        "--out", "launched.jsonl",
    ])
    assert instant.out == "launched.jsonl"

    lbp = parser.parse_args([
        "rpc-pools-trade-lbp-initializer-tape",
        "--from-block", "10",
        "--to-block", "20",
        "--out", "initializers.jsonl",
    ])
    assert lbp.out == "initializers.jsonl"


def _write_jsonl(path, rows):
    path.write_text(
        "".join(
            json.dumps(row, sort_keys=True) + "\n"
            for row in rows
        )
    )


def test_pools_trade_instant_registry_assembles_reusable_tapes(
    tmp_path,
):
    token = "0x" + "11" * 20
    zero = "0x" + "00" * 20
    strategy = "0x" + "22" * 20
    pool_id = "0x" + "33" * 32
    launcher = "0x" + "44" * 20
    tx = "0x" + "aa" * 32

    created = tmp_path / "created.jsonl"
    distributed = tmp_path / "distributed.jsonl"
    launched = tmp_path / "launched.jsonl"
    out = tmp_path / "registry.jsonl"
    _write_jsonl(created, [{
        "launcher": launcher,
        "token": token,
        "block_number": 10,
        "transaction_hash": tx,
        "transaction_index": 1,
        "log_index": 0,
    }])
    _write_jsonl(distributed, [{
        "launcher": launcher,
        "token": token,
        "strategy": strategy,
        "amount_raw": 10**27,
        "block_number": 10,
        "transaction_hash": tx,
        "transaction_index": 1,
        "log_index": 1,
    }])
    _write_jsonl(launched, [{
        "strategy": strategy,
        "pool_id": pool_id,
        "token": token,
        "final_position_recipient": "0x" + "55" * 20,
        "currency0": zero,
        "currency1": token,
        "fee": 2500,
        "tick_spacing": 50,
        "hooks": zero,
        "block_number": 10,
        "transaction_hash": tx,
        "transaction_index": 1,
        "log_index": 2,
    }])

    args = SimpleNamespace(
        created=str(created),
        distributed=str(distributed),
        launched=str(launched),
        out=str(out),
    )
    assert cmd_pools_trade_instant_registry(args) == 0
    row = json.loads(out.read_text().strip())
    assert row["token"] == token
    assert row["pool_id"] == pool_id
    assert row["supply_raw"] == 10**27


def test_pools_trade_lbp_registry_derives_pool_id_from_reused_tapes(
    tmp_path,
):
    token = "0x" + "11" * 20
    zero = "0x" + "00" * 20
    strategy = "0x" + "22" * 20
    launcher = "0x" + "44" * 20
    initializer = "0x" + "66" * 20
    tx = "0x" + "aa" * 32

    created = tmp_path / "created.jsonl"
    distributed = tmp_path / "distributed.jsonl"
    initializers = tmp_path / "initializers.jsonl"
    out = tmp_path / "lbp-registry.jsonl"
    _write_jsonl(created, [{
        "launcher": launcher,
        "token": token,
        "block_number": 10,
        "transaction_hash": tx,
        "transaction_index": 1,
        "log_index": 0,
    }])
    _write_jsonl(distributed, [{
        "launcher": launcher,
        "token": token,
        "strategy": strategy,
        "amount_raw": 1_000_000_000 * 10**18,
        "block_number": 10,
        "transaction_hash": tx,
        "transaction_index": 1,
        "log_index": 1,
    }])
    _write_jsonl(initializers, [{
        "strategy": strategy,
        "initializer": initializer,
        "token": token,
        "currency": zero,
        "migration_block": 100,
        "reserved_token_amount_for_lp": 100 * 10**18,
        "recipient": "0x" + "77" * 20,
        "position_recipient": "0x" + "88" * 20,
        "pool_fee": 2500,
        "pool_tick_spacing": 50,
        "pool_hook": zero,
        "position_definitions_offset": 352,
        "lp_allocation_schedule_offset": 576,
        "block_number": 10,
        "transaction_hash": tx,
        "transaction_index": 1,
        "log_index": 2,
    }])

    args = SimpleNamespace(
        created=str(created),
        distributed=str(distributed),
        initializers=str(initializers),
        out=str(out),
    )
    assert cmd_pools_trade_lbp_registry(args) == 0
    row = json.loads(out.read_text().strip())
    assert row["token"] == token
    assert row["currency0"] == zero
    assert row["currency1"] == token
    assert row["pool_id"].startswith("0x")
    assert len(row["pool_id"]) == 66






def test_phase2_direct_quote_registry_parser():
    parser = build_parser()
    args = parser.parse_args([
        "phase2-direct-quote-registry",
        "--registry-out", "quotes.jsonl",
        "--decimals-out", "decimals.json",
        "--feed-out", "feeds.jsonl",
        "--summary-out", "summary.json",
    ])
    assert args.registry_out == "quotes.jsonl"
    assert args.decimals_out == "decimals.json"
    assert args.feed_out == "feeds.jsonl"


def test_phase2_direct_quote_registry_command(
    monkeypatch,
    tmp_path,
):
    quote = "0x" + "11" * 20
    missing = "0x" + "12" * 20
    feed = "0x" + "22" * 20

    class FakeAssets:
        url = "https://assets.example"
        requests_made = 1
        bytes_received = 100

    class FakeDirectory:
        url = "https://directory.example"
        requests_made = 1
        bytes_received = 200
        last_sha256 = "ab" * 32

    monkeypatch.setattr(
        "hlp.cli.RobinhoodAssetsClient",
        lambda **kwargs: FakeAssets(),
    )
    monkeypatch.setattr(
        "hlp.cli.ChainlinkDirectoryClient",
        lambda **kwargs: FakeDirectory(),
    )
    monkeypatch.setattr(
        "hlp.cli.build_direct_quote_registry_from_clients",
        lambda assets, directory: [
            {
                "quote_token": quote,
                "symbol": "TEST",
                "quote_decimals": 18,
                "pricing_status": "priced_chainlink_stock_token",
                "feed": feed,
                "secondary_feed": None,
                "heartbeat_seconds": 86400,
                "directory_name": "Robinhood TEST / USD",
                "directory_path": "robinhood-test-usd",
            },
            {
                "quote_token": missing,
                "symbol": "MISS",
                "quote_decimals": 8,
                "pricing_status": "missing_chainlink_feed",
                "feed": None,
                "secondary_feed": None,
                "heartbeat_seconds": None,
                "directory_name": None,
                "directory_path": None,
            },
        ],
    )

    registry = tmp_path / "quotes.jsonl"
    decimals = tmp_path / "decimals.json"
    feeds = tmp_path / "feeds.jsonl"
    summary = tmp_path / "summary.json"
    args = SimpleNamespace(
        timeout=1.0,
        attempts=1,
        registry_out=str(registry),
        decimals_out=str(decimals),
        feed_out=str(feeds),
        summary_out=str(summary),
    )
    assert cmd_phase2_direct_quote_registry(args) == 0

    assert json.loads(decimals.read_text()) == {quote: 18}
    feed_row = json.loads(feeds.read_text().strip())
    assert feed_row["quote_token"] == quote
    assert feed_row["feed"] == feed

    report = json.loads(summary.read_text())
    assert report["registry_rows"] == 2
    assert report["priceable_quotes"] == 1
    assert report["chainlink_feed_quotes"] == 1
    assert report["pricing_status_counts"] == {
        "missing_chainlink_feed": 1,
        "priced_chainlink_stock_token": 1,
    }
    assert report["chainlink_directory_sha256"] == "ab" * 32



def test_phase2_direct_v3_registry_parser():
    parser = build_parser()
    args = parser.parse_args([
        "phase2-direct-v3-registry",
        "--pool-created", "created.jsonl",
        "--initialize", "initialize.jsonl",
        "--quote-decimals", "quotes.json",
        "--source-id", "direct_uniswap_v3",
        "--venue", "uniswap_v3",
        "--factory", "0x" + "44" * 20,
        "--state-out", "state.jsonl",
        "--registry-out", "registry.jsonl",
        "--summary-out", "summary.json",
    ])
    assert args.source_id == "direct_uniswap_v3"
    assert args.pool_created == "created.jsonl"
    assert args.initialize == "initialize.jsonl"


def test_shared_v3_initialize_parser():
    parser = build_parser()
    args = parser.parse_args([
        "rpc-v3-initialize-window",
        "--from-block", "10",
        "--to-block", "20",
        "--out", "initialize.jsonl",
    ])
    assert args.from_block == 10
    assert args.to_block == 20
    assert args.out == "initialize.jsonl"


def test_phase2_direct_v3_registry_reads_state_at_matched_initialize_block(
    monkeypatch,
    tmp_path,
):
    token = "0x" + "11" * 20
    quote = "0x" + "22" * 20
    factory = "0x" + "44" * 20
    pool = "0x" + "55" * 20
    created = tmp_path / "created.jsonl"
    initialize = tmp_path / "initialize.jsonl"
    quotes = tmp_path / "quotes.json"

    _write_jsonl(created, [{
        "factory": factory,
        "token0": token,
        "token1": quote,
        "fee": 3000,
        "tick_spacing": 60,
        "pool": pool,
        "block_number": 100,
        "transaction_hash": "0x" + "01" * 32,
        "transaction_index": 1,
        "log_index": 2,
    }])
    _write_jsonl(initialize, [{
        "pool": pool,
        "sqrt_price_x96": 2**96,
        "tick": 0,
        "block_number": 123,
        "transaction_hash": "0x" + "02" * 32,
        "transaction_index": 2,
        "log_index": 3,
    }])
    quotes.write_text(json.dumps({quote: 18}))

    class FakeRpc:
        route_label = "test_archive"
        requests_made = 2
        response_bytes_received = 128

        def assert_robinhood(self):
            return None

    reads = []
    monkeypatch.setattr("hlp.cli._archive_rpc", lambda args: FakeRpc())

    def fake_read_erc20_static(rpc, address, *, block):
        reads.append((address, block))
        return Erc20StaticState(
            token=address,
            block_number=block,
            decimals=18,
            total_supply=1_000_000 * 10**18,
        )

    monkeypatch.setattr(
        "hlp.cli.read_erc20_static",
        fake_read_erc20_static,
    )

    registry_out = tmp_path / "registry.jsonl"
    summary_out = tmp_path / "summary.json"
    args = SimpleNamespace(
        pool_created=str(created),
        initialize=str(initialize),
        quote_decimals=str(quotes),
        source_id="direct_uniswap_v3",
        venue="uniswap_v3",
        factory=factory,
        state_out=str(tmp_path / "state.jsonl"),
        registry_out=str(registry_out),
        summary_out=str(summary_out),
    )
    assert cmd_phase2_direct_v3_registry(args) == 0
    assert reads == [(token, 123)]

    registry = json.loads(registry_out.read_text().strip())
    assert registry["token"] == token
    assert registry["pool"] == pool
    assert registry["state_block"] == 123
    assert registry["initialize_block"] == 123

    summary = json.loads(summary_out.read_text())
    assert summary["supported_quote_candidate_markets"] == 1
    assert summary["matched_initialized_candidate_markets"] == 1
    assert summary["exact_state_reads"] == 1
    assert summary["source_coverage_complete"] is False


def test_phase2_direct_v3_registry_skips_unmatched_initialize_state_reads(
    monkeypatch,
    tmp_path,
):
    token = "0x" + "11" * 20
    quote = "0x" + "22" * 20
    factory = "0x" + "44" * 20
    pool = "0x" + "55" * 20
    created = tmp_path / "created.jsonl"
    initialize = tmp_path / "initialize.jsonl"
    quotes = tmp_path / "quotes.json"

    _write_jsonl(created, [{
        "factory": factory,
        "token0": token,
        "token1": quote,
        "fee": 3000,
        "tick_spacing": 60,
        "pool": pool,
        "block_number": 100,
        "transaction_hash": "0x" + "01" * 32,
        "transaction_index": 1,
        "log_index": 2,
    }])
    _write_jsonl(initialize, [{
        "pool": "0x" + "77" * 20,
        "sqrt_price_x96": 2**96,
        "tick": 0,
        "block_number": 123,
        "transaction_hash": "0x" + "02" * 32,
        "transaction_index": 2,
        "log_index": 3,
    }])
    quotes.write_text(json.dumps({quote: 18}))

    class FakeRpc:
        route_label = "test_archive"
        requests_made = 0
        response_bytes_received = 0

        def assert_robinhood(self):
            return None

    monkeypatch.setattr("hlp.cli._archive_rpc", lambda args: FakeRpc())
    monkeypatch.setattr(
        "hlp.cli.read_erc20_static",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("unmatched pool must not trigger token state")
        ),
    )

    args = SimpleNamespace(
        pool_created=str(created),
        initialize=str(initialize),
        quote_decimals=str(quotes),
        source_id="direct_uniswap_v3",
        venue="uniswap_v3",
        factory=factory,
        state_out=str(tmp_path / "state.jsonl"),
        registry_out=str(tmp_path / "registry.jsonl"),
        summary_out=str(tmp_path / "summary.json"),
    )
    assert cmd_phase2_direct_v3_registry(args) == 0
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["supported_quote_candidate_markets"] == 1
    assert summary["matched_initialized_candidate_markets"] == 0
    assert summary["exact_state_reads"] == 0
    assert summary["registry"]["markets"] == 0


def test_phase2_direct_v4_registry_parser():
    parser = build_parser()
    args = parser.parse_args([
        "phase2-direct-v4-registry",
        "--initialize", "initialize.jsonl",
        "--quote-decimals", "quotes.json",
        "--state-out", "state.jsonl",
        "--registry-out", "registry.jsonl",
        "--summary-out", "summary.json",
    ])
    assert args.source_id == "direct_uniswap_v4"
    assert args.venue == "uniswap_v4"
    assert args.initialize == "initialize.jsonl"
    assert args.quote_decimals == "quotes.json"


def test_phase2_direct_v4_registry_reads_state_at_initialize_block(
    monkeypatch,
    tmp_path,
):
    token = "0x" + "11" * 20
    quote = "0x" + "22" * 20
    manager = "0x" + "66" * 20
    initialize = tmp_path / "initialize.jsonl"
    quotes = tmp_path / "quotes.json"
    state_out = tmp_path / "state.jsonl"
    registry_out = tmp_path / "registry.jsonl"
    summary_out = tmp_path / "summary.json"

    _write_jsonl(initialize, [{
        "pool_manager": manager,
        "pool_id": "0x" + "aa" * 32,
        "currency0": token,
        "currency1": quote,
        "fee": 3000,
        "tick_spacing": 60,
        "hooks": "0x" + "00" * 20,
        "sqrt_price_x96": 2**96,
        "tick": 0,
        "block_number": 123,
        "transaction_hash": "0x" + "03" * 32,
        "transaction_index": 2,
        "log_index": 3,
    }])
    quotes.write_text(json.dumps({quote: 18}))

    class FakeRpc:
        route_label = "test_archive"
        requests_made = 2
        response_bytes_received = 128

        def assert_robinhood(self):
            return None

    reads = []
    monkeypatch.setattr(
        "hlp.cli._archive_rpc",
        lambda args: FakeRpc(),
    )

    def fake_read_erc20_static(rpc, address, *, block):
        reads.append((address, block))
        return Erc20StaticState(
            token=address,
            block_number=block,
            decimals=18,
            total_supply=1_000_000 * 10**18,
        )

    monkeypatch.setattr(
        "hlp.cli.read_erc20_static",
        fake_read_erc20_static,
    )

    args = SimpleNamespace(
        initialize=str(initialize),
        quote_decimals=str(quotes),
        source_id="direct_uniswap_v4",
        venue="uniswap_v4",
        pool_manager=manager,
        state_out=str(state_out),
        registry_out=str(registry_out),
        summary_out=str(summary_out),
    )
    assert cmd_phase2_direct_v4_registry(args) == 0
    assert reads == [(token, 123)]

    registry = json.loads(registry_out.read_text().strip())
    assert registry["token"] == token
    assert registry["quote_token"] == quote
    assert registry["state_block"] == 123
    assert registry["initialize_block"] == 123

    summary = json.loads(summary_out.read_text())
    assert summary["supported_quote_candidate_markets"] == 1
    assert summary["exact_state_reads"] == 1
    assert summary["source_coverage_complete"] is False
    assert summary["registry"]["canonical_market_selection_complete"] is False


def test_phase2_direct_v4_registry_does_not_read_quote_quote_state(
    monkeypatch,
    tmp_path,
):
    quote0 = "0x" + "22" * 20
    quote1 = "0x" + "33" * 20
    manager = "0x" + "66" * 20
    initialize = tmp_path / "initialize.jsonl"
    quotes = tmp_path / "quotes.json"

    _write_jsonl(initialize, [{
        "pool_manager": manager,
        "pool_id": "0x" + "bb" * 32,
        "currency0": quote0,
        "currency1": quote1,
        "fee": 3000,
        "tick_spacing": 60,
        "hooks": "0x" + "00" * 20,
        "sqrt_price_x96": 2**96,
        "tick": 0,
        "block_number": 124,
        "transaction_hash": "0x" + "04" * 32,
        "transaction_index": 2,
        "log_index": 3,
    }])
    quotes.write_text(json.dumps({quote0: 18, quote1: 6}))

    class FakeRpc:
        route_label = "test_archive"
        requests_made = 0
        response_bytes_received = 0

        def assert_robinhood(self):
            return None

    monkeypatch.setattr("hlp.cli._archive_rpc", lambda args: FakeRpc())
    monkeypatch.setattr(
        "hlp.cli.read_erc20_static",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("quote/quote market must not trigger token state")
        ),
    )

    args = SimpleNamespace(
        initialize=str(initialize),
        quote_decimals=str(quotes),
        source_id="direct_uniswap_v4",
        venue="uniswap_v4",
        pool_manager=manager,
        state_out=str(tmp_path / "state.jsonl"),
        registry_out=str(tmp_path / "registry.jsonl"),
        summary_out=str(tmp_path / "summary.json"),
    )
    assert cmd_phase2_direct_v4_registry(args) == 0
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["supported_quote_candidate_markets"] == 0
    assert summary["exact_state_reads"] == 0
    assert summary["registry"]["markets"] == 0



def _direct_market_args(
    *,
    registry,
    initializes,
    swaps,
    out,
    report,
):
    return SimpleNamespace(
        registry=str(registry),
        initializes=str(initializes),
        swaps=str(swaps),
        swaps_shard_dir=None,
        swaps_manifest=None,
        from_block=10,
        to_block=20,
        chunk_size=100_000,
        min_chunk_size=25,
        usd_anchor_pool="0x" + "99" * 20,
        oracle_state=None,
        oracle_events=None,
        fallback_state=None,
        fallback_events=None,
        out=str(out),
        report_out=str(report),
    )


def test_phase2_direct_market_window_parsers():
    parser = build_parser()
    v3 = parser.parse_args([
        "phase2-direct-v3-market-window",
        "--registry", "registry.jsonl",
        "--initializes", "initializes.jsonl",
        "--swaps", "swaps.jsonl",
        "--from-block", "10",
        "--to-block", "20",
        "--out", "points.jsonl",
        "--report-out", "report.json",
    ])
    assert v3.swaps == "swaps.jsonl"
    assert v3.swaps_manifest is None

    v4 = parser.parse_args([
        "phase2-direct-v4-market-window",
        "--registry", "registry.jsonl",
        "--initializes", "initializes.jsonl",
        "--swaps-manifest", "swaps.manifest.json",
        "--swaps-shard-dir", "inputs",
        "--from-block", "10",
        "--to-block", "20",
        "--out", "points.jsonl",
        "--report-out", "report.json",
    ])
    assert v4.swaps is None
    assert v4.swaps_manifest == "swaps.manifest.json"
    assert v4.swaps_shard_dir == "inputs"


def test_phase2_direct_v3_market_window_keeps_pool_points_unselected(
    monkeypatch,
    tmp_path,
):
    from hlp.config import ROBINHOOD_WETH

    token = "0x" + "11" * 20
    quote = ROBINHOOD_WETH.lower()
    pool = "0x" + "55" * 20
    registry = tmp_path / "registry.jsonl"
    initializes = tmp_path / "initializes.jsonl"
    swaps = tmp_path / "swaps.jsonl"
    out = tmp_path / "points.jsonl"
    report = tmp_path / "report.json"

    _write_jsonl(registry, [{
        "source_id": "direct_uniswap_v3",
        "venue": "uniswap_v3",
        "token": token,
        "quote_token": quote,
        "quote_decimals": 18,
        "supply_raw": 1_000_000 * 10**18,
        "pool": pool,
        "initialize_block": 10,
        "initialize_transaction_index": 1,
        "initialize_log_index": 0,
    }])
    _write_jsonl(initializes, [{
        "pool": pool,
        "sqrt_price_x96": 2**96,
        "tick": 0,
        "block_number": 10,
        "transaction_hash": "0x" + "01" * 32,
        "transaction_index": 1,
        "log_index": 0,
    }])
    _write_jsonl(swaps, [{
        "pool": pool,
        "sender": "0x" + "77" * 20,
        "recipient": "0x" + "88" * 20,
        "amount0": -10**18,
        "amount1": 10**18,
        "sqrt_price_x96": 2**96,
        "liquidity": 1_000 * 10**18,
        "tick": 0,
        "block_number": 11,
        "transaction_hash": "0x" + "02" * 32,
        "transaction_index": 1,
        "log_index": 0,
    }])

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

    args = _direct_market_args(
        registry=registry,
        initializes=initializes,
        swaps=swaps,
        out=out,
        report=report,
    )
    assert cmd_phase2_direct_v3_market_cap_window(args) == 0

    points = [
        json.loads(line)
        for line in out.read_text().splitlines()
        if line.strip()
    ]
    assert len(points) == 2
    assert all(row["source_id"] == "direct_uniswap_v3" for row in points)
    assert points[-1]["market_id"] == pool
    assert points[-1]["active_quote_liquidity_usd"] is not None

    payload = json.loads(report.read_text())
    assert payload["market_cap_points"] == 2
    assert payload["quality_ready_points"] == 1
    assert payload["market_selection_rule_frozen"] is False
    assert payload["threshold_summary_emitted"] is False


def test_phase2_direct_v4_market_window_uses_registry_initialize_evidence(
    monkeypatch,
    tmp_path,
):
    from hlp.config import ROBINHOOD_WETH

    token = "0x" + "11" * 20
    quote = ROBINHOOD_WETH.lower()
    pool_id = "0x" + "aa" * 32
    registry = tmp_path / "registry.jsonl"
    initializes = tmp_path / "initializes.jsonl"
    swaps = tmp_path / "swaps.jsonl"
    out = tmp_path / "points.jsonl"
    report = tmp_path / "report.json"

    _write_jsonl(registry, [{
        "source_id": "direct_uniswap_v4",
        "venue": "uniswap_v4",
        "token": token,
        "quote_token": quote,
        "quote_decimals": 18,
        "supply_raw": 1_000_000 * 10**18,
        "pool_id": pool_id,
        "currency0": token,
        "currency1": quote,
        "initialize_block": 5,
        "initialize_transaction_index": 1,
        "initialize_log_index": 0,
    }])
    _write_jsonl(initializes, [])
    _write_jsonl(swaps, [{
        "pool_manager": "0x" + "66" * 20,
        "pool_id": pool_id,
        "sender": "0x" + "77" * 20,
        "amount0": -10**18,
        "amount1": 10**18,
        "sqrt_price_x96": 2**96,
        "liquidity": 1_000 * 10**18,
        "tick": 0,
        "fee": 3000,
        "block_number": 11,
        "transaction_hash": "0x" + "03" * 32,
        "transaction_index": 1,
        "log_index": 0,
    }])

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

    args = _direct_market_args(
        registry=registry,
        initializes=initializes,
        swaps=swaps,
        out=out,
        report=report,
    )
    assert cmd_phase2_direct_v4_market_cap_window(args) == 0
    point = json.loads(out.read_text().strip())
    assert point["source_id"] == "direct_uniswap_v4"
    assert point["market_id"] == pool_id
    assert point["block_number"] == 11

    payload = json.loads(report.read_text())
    assert payload["initialize_events"] == 0
    assert payload["swap_events"] == 1
    assert payload["quality_ready_points"] == 1
    assert payload["market_selection_rule_frozen"] is False



def test_phase2_market_quality_audit_parser():
    parser = build_parser()
    args = parser.parse_args([
        "phase2-market-quality-audit",
        "--points", "v3.jsonl",
        "--points", "v4.jsonl",
        "--trace-out", "trace.jsonl",
        "--candidate-out", "candidate.jsonl",
        "--report-out", "report.json",
    ])
    assert args.points == ["v3.jsonl", "v4.jsonl"]
    assert args.trace_out == "trace.jsonl"
    assert args.candidate_out == "candidate.jsonl"


def test_phase2_market_quality_audit_command(tmp_path):
    token = "0x" + "11" * 20
    v3 = tmp_path / "v3.jsonl"
    v4 = tmp_path / "v4.jsonl"
    v3.write_text(
        json.dumps({
            "token": token,
            "market_id": "0xaaa",
            "block_number": 10,
            "transaction_index": 1,
            "log_index": 0,
            "active_quote_liquidity_usd": "500",
            "market_cap_proxy_usd": "100000",
        }) + "\n"
    )
    v4.write_text(
        json.dumps({
            "token": token,
            "market_id": "0xbbb",
            "block_number": 11,
            "transaction_index": 1,
            "log_index": 0,
            "active_quote_liquidity_usd": "600",
            "market_cap_proxy_usd": "150000",
        }) + "\n"
    )

    trace = tmp_path / "trace.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    report = tmp_path / "report.json"
    args = SimpleNamespace(
        points=[str(v3), str(v4)],
        trace_out=str(trace),
        candidate_out=str(candidate),
        report_out=str(report),
    )
    assert cmd_phase2_market_quality_audit(args) == 0

    payload = json.loads(report.read_text())
    assert payload["version"] == "phase2-market-quality-audit-v1"
    assert payload["selection_rule_frozen"] is False
    assert payload["input_points"] == 2
    assert payload["competition"]["multi_market_tokens"] == 1
    assert payload["causal_trace"]["candidate_switches"] == 1
    assert (
        payload["candidate_canonical_series"]["leadership_switches"]
        == 1
    )
    assert (
        payload["candidate_canonical_series"][
            "cross_pool_volume_double_counting_allowed"
        ]
        is False
    )

    candidate_rows = [
        json.loads(line)
        for line in candidate.read_text().splitlines()
        if line.strip()
    ]
    assert [row["selected_market_id"] for row in candidate_rows] == [
        "0xaaa",
        "0xbbb",
    ]
