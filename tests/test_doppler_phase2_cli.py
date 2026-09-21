import json
from types import SimpleNamespace

from hlp.cli import (
    build_parser,
    cmd_rpc_doppler_launch_window,
)
from hlp.data.types import DopplerLaunch
from hlp.protocols.erc20 import Erc20StaticState


TOKEN = "0x" + "11" * 20
QUOTE = "0x" + "22" * 20
TX = "0x" + "aa" * 32


class FakeRpc:
    route_label = "test_archive"
    requests_made = 3
    response_bytes_received = 100

    def assert_robinhood(self):
        return None

    def iter_logs_chunked(self, *args, **kwargs):
        return [object()]


def test_doppler_launch_window_parser():
    args = build_parser().parse_args([
        "rpc-doppler-launch-window",
        "--from-block", "10",
        "--to-block", "20",
        "--out", "launches.jsonl",
        "--state-out", "states.jsonl",
    ])
    assert args.from_block == 10
    assert args.to_block == 20
    assert args.out == "launches.jsonl"
    assert args.state_out == "states.jsonl"


def test_doppler_launch_window_reads_exact_launch_block_state(
    monkeypatch,
    tmp_path,
):
    launch = DopplerLaunch(
        asset=TOKEN,
        numeraire=QUOTE,
        initializer="0x" + "33" * 20,
        pool_or_hook="0x" + "44" * 20,
        block_number=15,
        transaction_hash=TX,
        transaction_index=1,
        log_index=2,
    )
    monkeypatch.setattr("hlp.cli._archive_rpc", lambda args: FakeRpc())
    monkeypatch.setattr(
        "hlp.cli.decode_doppler_launch",
        lambda raw: launch,
    )
    observed = {}

    def fake_static(rpc, token, *, block):
        observed["token"] = token
        observed["block"] = block
        return Erc20StaticState(
            token=token,
            block_number=block,
            decimals=9,
            total_supply=123_000_000,
        )

    monkeypatch.setattr("hlp.cli.read_erc20_static", fake_static)
    launches = tmp_path / "launches.jsonl"
    states = tmp_path / "states.jsonl"
    args = SimpleNamespace(
        from_block=10,
        to_block=20,
        chunk_size=200,
        min_chunk_size=25,
        out=str(launches),
        state_out=str(states),
    )

    assert cmd_rpc_doppler_launch_window(args) == 0
    assert observed == {"token": TOKEN, "block": 15}

    launch_row = json.loads(launches.read_text().strip())
    state_row = json.loads(states.read_text().strip())
    assert launch_row["asset"] == TOKEN
    assert launch_row["numeraire"] == QUOTE
    assert state_row == {
        "token": TOKEN,
        "state_block": 15,
        "token_decimals": 9,
        "supply_raw": 123_000_000,
    }

    launch_manifest = json.loads(
        launches.with_suffix(".jsonl.manifest.json").read_text()
    )
    state_manifest = json.loads(
        states.with_suffix(".jsonl.manifest.json").read_text()
    )
    assert launch_manifest["provenance"]["protocol"] == (
        "doppler_airlock_create"
    )
    assert state_manifest["provenance"]["state_semantics"] == (
        "ERC20 decimals/totalSupply at exact Airlock Create block"
    )
