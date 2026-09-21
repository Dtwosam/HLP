import json
from types import SimpleNamespace

from hlp.cli import (
    build_parser,
    cmd_phase2_noxa_initialized_registry,
    cmd_rpc_noxa_registry_window,
)
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
