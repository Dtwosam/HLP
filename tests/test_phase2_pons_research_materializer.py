import json
from decimal import Decimal
from pathlib import Path

from hlp.config import ROBINHOOD_WETH
from hlp.data.phase2_pons_research_materializer import (
    materialize_pons_v1_research,
    materialize_pons_v2_research,
)
from hlp.data.sharded_tape import write_virtual_jsonl_manifest
from hlp.data.snapshot import write_jsonl_snapshot


TOKEN = "0x0000000000000000000000000000000000000011"
POOL = "0x" + "33" * 20
CURVE = "0x" + "22" * 20
POOL_ID = "0x" + "aa" * 32


def expected(manifest):
    return {
        "records": manifest["records"],
        "sha256": manifest["sha256"],
    }


def snapshot(tmp_path, name, rows):
    path = tmp_path / name
    manifest = write_jsonl_snapshot(
        rows,
        output=path,
        provenance={
            "chain_id": 4663,
            "snapshot_head_block": 100,
        },
    )
    return path, path.with_suffix(path.suffix + ".manifest.json"), manifest


def sharded(tmp_path, name, rows):
    root = tmp_path / (name + "-shards")
    root.mkdir()
    data, sidecar, shard_manifest = snapshot(
        root,
        f"{name}-000.jsonl",
        rows,
    )
    sidecar_payload = json.loads(sidecar.read_text())
    sidecar_payload["provenance"].update({
        "from_block": 20,
        "to_block": 20,
    })
    sidecar.write_text(
        json.dumps(sidecar_payload, indent=2, sort_keys=True) + "\n"
    )
    aggregate_sha = shard_manifest["sha256"]
    aggregate_path = tmp_path / f"{name}.manifest.json"
    aggregate = write_virtual_jsonl_manifest(
        manifest_path=aggregate_path,
        path_name=f"{name}.jsonl",
        records=shard_manifest["records"],
        sha256=aggregate_sha,
        provenance={
            "storage_mode": "sharded_artifacts",
            "shards": [{
                "file": data.name,
                "records": shard_manifest["records"],
                "sha256": shard_manifest["sha256"],
                "from_block": 20,
                "to_block": 20,
            }],
        },
    )
    return root, aggregate_path, aggregate


def test_materialize_v1_research_replays_accepted_eligible_summary(tmp_path):
    registry, registry_m, registry_manifest = snapshot(
        tmp_path,
        "registry.jsonl",
        [{
            "version": "v1",
            "token": TOKEN,
            "pair_token": ROBINHOOD_WETH.lower(),
            "pool": POOL,
            "block_number": 10,
            "supply_raw": 100_000 * 10**18,
            "token_decimals": 18,
        }],
    )
    quote, quote_m, quote_manifest = snapshot(
        tmp_path,
        "quotes.jsonl",
        [
            {
                "quote_token": ROBINHOOD_WETH.lower(),
                "quote_decimals": 18,
            },
            {
                "quote_token": "0x5fc5360d0400a0fd4f2af552add042d716f1d168",
                "quote_decimals": 18,
            },
        ],
    )
    anchor, anchor_m, anchor_manifest = snapshot(
        tmp_path,
        "anchor.jsonl",
        [],
    )
    oracle_state, oracle_state_m, oracle_state_manifest = snapshot(
        tmp_path,
        "oracle-state.jsonl",
        [],
    )
    oracle_updates, oracle_updates_m, oracle_updates_manifest = snapshot(
        tmp_path,
        "oracle-updates.jsonl",
        [],
    )
    root, aggregate_path, aggregate = sharded(
        tmp_path,
        "v1-events",
        [{
            "pool": POOL,
            "block_number": 20,
            "transaction_index": 1,
            "log_index": 0,
            "sqrt_price_x96": 2**96,
        }],
    )
    anchor_initial = tmp_path / "anchor-initial.json"
    anchor_initial.write_text(json.dumps({"weth_usd": "2000"}))

    accepted, accepted_m, accepted_manifest = snapshot(
        tmp_path,
        "accepted.jsonl",
        [{
            "token": TOKEN,
            "pool": POOL,
            "quote_token": ROBINHOOD_WETH.lower(),
            "launch_block": 10,
            "pricing_statuses": ["priced_weth_usdg"],
            "price_points": 1,
            "priced_points": 1,
            "unpriced_points": 0,
            "first_priced_block": 20,
            "last_priced_block": 20,
            "first_unpriced_block": None,
            "last_unpriced_block": None,
            "max_market_cap_proxy_usd": "200000000",
            "max_market_cap_block": 20,
            "crossed_100k": True,
            "v3_swap_max_market_cap_proxy_usd": None,
            "v3_swap_max_market_cap_block": None,
            "pricing_complete": True,
            "eligibility_status": "eligible",
        }],
    )

    report = materialize_pons_v1_research(
        eligible_tokens=[TOKEN],
        accepted_lifecycle_path=accepted,
        accepted_lifecycle_manifest_path=accepted_m,
        accepted_lifecycle_expected=expected(accepted_manifest),
        registry_path=registry,
        registry_manifest_path=registry_m,
        registry_expected=expected(registry_manifest),
        quote_registry_path=quote,
        quote_registry_manifest_path=quote_m,
        quote_registry_expected=expected(quote_manifest),
        market_events_root=root,
        market_events_manifest_path=aggregate_path,
        market_events_expected=expected(aggregate),
        anchor_events_path=anchor,
        anchor_events_manifest_path=anchor_m,
        anchor_expected=expected(anchor_manifest),
        anchor_initial_path=anchor_initial,
        oracle_state_path=oracle_state,
        oracle_state_manifest_path=oracle_state_m,
        oracle_state_expected=expected(oracle_state_manifest),
        oracle_updates_path=oracle_updates,
        oracle_updates_manifest_path=oracle_updates_m,
        oracle_updates_expected=expected(oracle_updates_manifest),
        output=tmp_path / "v1-research.jsonl",
        provenance={"accepted": True},
    )

    assert report["accepted_lifecycle_replay_equivalent"] is True
    assert report["full_inputs_validated"] is True
    assert report["materialized_records"] == 1
