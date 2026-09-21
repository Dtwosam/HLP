import json
from types import SimpleNamespace

from hlp.cli import (
    build_parser,
    cmd_phase2_apply_source_coverage,
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
