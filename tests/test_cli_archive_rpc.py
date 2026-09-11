import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from hlp.cli import (
    _archive_rpc,
    _load_initial_quote_usd,
    build_parser,
    cmd_rpc_pons_transfer_tape,
    cmd_rpc_v2_v4_tape,
)
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


def test_v2_v4_filter_modes_shape_topic1_and_provenance(
    monkeypatch,
    tmp_path,
):
    pool_id = "0x" + "11" * 32
    registrations = tmp_path / "registrations.jsonl"
    registrations.write_text(
        json.dumps({"pool_id": pool_id}) + "\n"
    )
    calls = []

    class FakeRpc:
        requests_made = 0
        request_bytes_sent = 0
        response_bytes_received = 0
        route_label = "test_route"

        def assert_robinhood(self):
            return None

        def iter_logs_chunked(
            self,
            from_block,
            to_block,
            *,
            address=None,
            topics=None,
            chunk_size=100_000,
            min_chunk_size=1,
        ):
            calls.append(
                {
                    "from_block": from_block,
                    "to_block": to_block,
                    "address": address,
                    "topics": topics,
                    "chunk_size": chunk_size,
                    "min_chunk_size": min_chunk_size,
                }
            )
            return iter(())

    monkeypatch.setattr(
        "hlp.cli._archive_rpc",
        lambda args: FakeRpc(),
    )

    manifests = []
    for global_pool_scan, name in (
        (True, "global"),
        (False, "server"),
    ):
        out = tmp_path / f"{name}.jsonl"
        parsed = SimpleNamespace(
            registrations=str(registrations),
            from_block=10,
            to_block=20,
            chunk_size=5,
            min_chunk_size=1,
            global_pool_scan=global_pool_scan,
            out=str(out),
        )
        assert cmd_rpc_v2_v4_tape(parsed) == 0
        manifests.append(
            json.loads(
                Path(str(out) + ".manifest.json").read_text()
            )
        )

    assert len(calls) == 2
    assert len(calls[0]["topics"]) == 1
    assert len(calls[0]["topics"][0]) == 2
    assert calls[1]["topics"][0] == calls[0]["topics"][0]
    assert calls[1]["topics"][1] == [pool_id]

    global_provenance = manifests[0]["provenance"]
    server_provenance = manifests[1]["provenance"]
    assert global_provenance["event_topic1_pool_ids"] is None
    assert (
        global_provenance["pool_filter_mode"]
        == "global_poolmanager_topic_then_registry"
    )
    assert server_provenance["event_topic1_pool_ids"] == [pool_id]
    assert (
        server_provenance["pool_filter_mode"]
        == "server_side_topic1_registered_pool_ids"
    )


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



def test_unpriced_quote_v3_route_audit_accepts_factory():
    parser = build_parser()
    factory = "0x" + "77" * 20
    args = parser.parse_args([
        "rpc-pons-unpriced-quote-v3-routes",
        "--quote-registry", "quotes.jsonl",
        "--factory", factory,
        "--out", "routes.jsonl",
    ])
    assert args.factory == factory



def test_unpriced_quote_v4_route_probe_parses():
    parser = build_parser()
    args = parser.parse_args([
        "rpc-pons-unpriced-quote-v4-routes",
        "--quote-registry", "residual.jsonl",
        "--snapshot-head", "1000",
        "--lookaround-blocks", "100",
        "--out", "v4.jsonl",
    ])
    assert args.snapshot_head == 1000
    assert args.lookaround_blocks == 100



def test_v4_quote_route_pipeline_parses():
    parser = build_parser()

    select_args = parser.parse_args([
        "pons-select-v4-quote-routes",
        "--probe", "probe.jsonl",
        "--out", "routes.jsonl",
    ])
    assert select_args.probe == "probe.jsonl"

    tape_args = parser.parse_args([
        "rpc-v4-quote-route-tape",
        "--routes", "routes.jsonl",
        "--from-block", "100",
        "--to-block", "200",
        "--out", "events.jsonl",
    ])
    assert tape_args.from_block == 100

    usd_args = parser.parse_args([
        "pons-v4-quote-usd-tape",
        "--routes", "routes.jsonl",
        "--v4-events", "events.jsonl",
        "--state-out", "state.jsonl",
        "--out", "updates.jsonl",
    ])
    assert usd_args.v4_events == "events.jsonl"



def test_quote_usd_merge_parser_accepts_repeated_source_pairs():
    parser = build_parser()
    args = parser.parse_args([
        "pons-merge-quote-usd-tapes",
        "--state", "v3-state.jsonl",
        "--events", "v3-events.jsonl",
        "--state", "v4-state.jsonl",
        "--events", "v4-events.jsonl",
        "--state-out", "fallback-state.jsonl",
        "--out", "fallback-events.jsonl",
        "--snapshot-head", "200",
    ])
    assert args.state == ["v3-state.jsonl", "v4-state.jsonl"]
    assert args.events == ["v3-events.jsonl", "v4-events.jsonl"]
    assert args.snapshot_head == 200



def test_v3_quote_usd_parser_allows_direct_usdg_without_anchor_files():
    parser = build_parser()
    args = parser.parse_args([
        "pons-v3-quote-usd-tape",
        "--routes", "routes.jsonl",
        "--v3-events", "events.jsonl",
        "--state-out", "state.jsonl",
        "--out", "updates.jsonl",
    ])
    assert args.anchor_events is None
    assert args.anchor_initial is None



def test_deployment_block_parser_accepts_archive_route():
    parser = build_parser()
    args = parser.parse_args([
        "deployment-block",
        "0x" + "11" * 20,
        "--archive",
        "--high", "1000",
    ])
    assert args.archive is True
    assert args.high == 1000



def test_known_v4_quote_pool_validator_parses():
    parser = build_parser()
    quote_token = "0x" + "11" * 20
    pool_id = "0x" + "22" * 32
    args = parser.parse_args([
        "rpc-pons-validate-v4-quote-pool",
        "--quote-registry", "quotes.jsonl",
        "--quote-token", quote_token,
        "--pool-id", pool_id,
        "--from-block", "100",
        "--to-block", "200",
        "--out", "candidate.jsonl",
    ])
    assert args.quote_token == quote_token
    assert args.pool_id == pool_id
    assert args.from_block == 100
    assert args.to_block == 200


def test_extend_v4_quote_route_probe_parses():
    parser = build_parser()
    args = parser.parse_args([
        "rpc-pons-extend-v4-quote-routes",
        "--probe", "prior.jsonl",
        "--snapshot-head", "2000",
        "--forward-blocks", "500000",
        "--known-pool-only",
        "--out", "next.jsonl",
    ])
    assert args.forward_blocks == 500000
    assert args.known_pool_only is True
    assert args.probe == "prior.jsonl"

def test_representative_transfer_and_holder_parsers():
    parser = build_parser()

    transfers = parser.parse_args([
        "rpc-pons-transfer-tape",
        "--tokens", "sample.jsonl",
        "--from-block", "100",
        "--to-block", "200",
        "--out", "transfers.jsonl",
    ])
    assert transfers.tokens == "sample.jsonl"
    assert transfers.from_block == 100
    assert transfers.chunk_size == 2000

    holders = parser.parse_args([
        "pons-holder-state",
        "--transfers", "transfers.jsonl",
        "--out", "holders.jsonl",
        "--summary-out", "holder-summary.jsonl",
    ])
    assert holders.transfers == "transfers.jsonl"
    assert holders.summary_out == "holder-summary.jsonl"

def test_representative_sample_parser():
    parser = build_parser()
    args = parser.parse_args([
        "pons-representative-sample",
        "--v1-lifecycle", "v1.jsonl",
        "--v2-lifecycle", "v2.jsonl",
        "--outcomes", "outcomes.jsonl",
        "--out", "sample.jsonl",
    ])
    assert args.v1_lifecycle == "v1.jsonl"
    assert args.runners == 5
    assert args.failures == 5
    assert args.out == "sample.jsonl"



def test_transfer_tape_manifest_binds_exact_sample_identity(
    monkeypatch,
    tmp_path,
):
    sample = tmp_path / "sample.jsonl"
    rows = [
        {"token": "0x" + "11" * 20},
        {"token": "0x" + "22" * 20},
    ]
    sample.write_text(
        "".join(
            json.dumps(row, sort_keys=True) + "\n"
            for row in rows
        )
    )

    class FakeRpc:
        requests_made = 3
        response_bytes_received = 4
        route_label = "test_route"

        def assert_robinhood(self):
            return None

    monkeypatch.setattr(
        "hlp.cli._archive_rpc",
        lambda args: FakeRpc(),
    )
    monkeypatch.setattr(
        "hlp.cli.fetch_pons_transfer_rows",
        lambda *args, **kwargs: [],
    )

    captured = {}

    def fake_snapshot(rows, *, output, provenance):
        captured["output"] = output
        captured["provenance"] = provenance
        return {"sha256": "deadbeef", "records": 0}

    monkeypatch.setattr(
        "hlp.cli.write_jsonl_snapshot",
        fake_snapshot,
    )

    args = SimpleNamespace(
        tokens=str(sample),
        from_block=100,
        to_block=200,
        chunk_size=50,
        min_chunk_size=5,
        out=str(tmp_path / "transfers.jsonl"),
    )
    assert cmd_rpc_pons_transfer_tape(args) == 0

    expected_tokens = sorted(row["token"].lower() for row in rows)
    expected_sample_sha = hashlib.sha256(
        sample.read_bytes()
    ).hexdigest()
    expected_token_set_sha = hashlib.sha256(
        ("\n".join(expected_tokens) + "\n").encode()
    ).hexdigest()

    provenance = captured["provenance"]
    assert provenance["sample_sha256"] == expected_sample_sha
    assert provenance["token_set_sha256"] == expected_token_set_sha
    assert provenance["token_count"] == 2
