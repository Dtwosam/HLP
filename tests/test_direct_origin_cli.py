import json
from types import SimpleNamespace

from hlp.cli import (
    build_parser,
    cmd_phase2_direct_launch_population,
)


TOKEN = "0x" + "11" * 20
OTHER = "0x" + "22" * 20


def _write_jsonl(path, rows):
    path.write_text(
        "".join(
            json.dumps(row, sort_keys=True) + "\n"
            for row in rows
        )
    )


def _report():
    return {
        "version": "phase2-direct-origin-attribution-v1",
        "snapshot_head_block": 100,
        "direct_source_ids": ["direct_uniswap_v3"],
        "markets": 2,
        "tokens": 2,
        "known_launch_source_markets": 1,
        "unattributed_markets": 1,
        "multi_launch_source_markets": 0,
        "matched_launch_source_ids": ["pons_v1"],
        "launch_source_ids": ["noxa", "pons_v1"],
        "provided_launch_source_ids": ["noxa", "pons_v1"],
        "complete_launch_source_ids": ["noxa", "pons_v1"],
        "missing_launch_registry_source_ids": [],
        "incomplete_launch_coverage_source_ids": [],
        "launch_source_coverage_complete": True,
        "absence_from_launch_registries_is_conclusive": True,
        "unattributed_markets_remain_direct_launch_unknown": False,
        "phase2_universe_coverage_complete": False,
    }


def _row(token, pool, classification, source_ids, complete, block):
    return {
        "source_id": "direct_uniswap_v3",
        "venue": "uniswap_v3",
        "token": token,
        "pool": pool,
        "initialize_block": block,
        "launch_source_ids": source_ids,
        "launch_source_count": len(source_ids),
        "origin_classification": classification,
        "origin_attribution_complete": complete,
    }


def test_direct_launch_population_parser():
    args = build_parser().parse_args([
        "phase2-direct-launch-population",
        "--attributed-registry", "attributed.jsonl",
        "--attribution-report", "attribution.json",
        "--out", "direct.jsonl",
        "--summary-out", "summary.json",
    ])
    assert args.attributed_registry == "attributed.jsonl"
    assert args.attribution_report == "attribution.json"


def test_direct_launch_population_command(tmp_path):
    attributed = tmp_path / "attributed.jsonl"
    attribution_report = tmp_path / "attribution.json"
    output = tmp_path / "direct.jsonl"
    summary = tmp_path / "summary.json"
    _write_jsonl(
        attributed,
        [
            _row(
                TOKEN,
                "0x" + "33" * 20,
                "known_launch_source",
                ["pons_v1"],
                True,
                10,
            ),
            _row(
                OTHER,
                "0x" + "44" * 20,
                "unattributed",
                [],
                False,
                20,
            ),
        ],
    )
    attribution_report.write_text(
        json.dumps(_report(), indent=2) + "\n"
    )

    args = SimpleNamespace(
        attributed_registry=str(attributed),
        attribution_report=str(attribution_report),
        out=str(output),
        summary_out=str(summary),
    )
    assert cmd_phase2_direct_launch_population(args) == 0

    rows = [
        json.loads(line)
        for line in output.read_text().splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["token"] == OTHER
    assert rows[0]["direct_launch_attribution_complete"] is True
    assert rows[0]["selector_freeze_ready"] is False
    payload = json.loads(summary.read_text())
    assert payload["direct_launch_population_conclusive"] is True
    assert payload["direct_launch_candidate_markets"] == 1
    assert payload["selector_freeze_ready"] is False
    assert payload["source_coverage_complete"] is False
