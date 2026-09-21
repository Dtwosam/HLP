import json
from types import SimpleNamespace

from hlp.cli import (
    build_parser,
    cmd_phase2_apply_source_coverage,
)
from hlp.data.phase2_coverage import PHASE2_COVERAGE_LEDGER_VERSION


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
