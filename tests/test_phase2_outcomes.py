import json
from pathlib import Path

from hlp.data.phase2_outcomes import (
    PHASE2_OUTCOME_HANDOFF_VERSION,
    PHASE2_OUTCOME_LABEL_VERSION,
    build_phase2_outcome_handoff,
    materialize_phase2_outcome_labels,
)


SHA = "ab" * 32
TOKEN_A = "0x" + "11" * 20
TOKEN_B = "0x" + "22" * 20


def detector_summary():
    return {
        "version": "phase2-dump-detector-freeze-v1",
        "snapshot_head_block": 100,
        "universe_sha256": SHA,
        "normalized_price_path_sha256": SHA,
        "geometry_sha256": SHA,
        "selected_candidate_id": "chosen",
        "selected_candidate_spec": {
            "candidate_id": "chosen",
            "family": "peak_drawdown_rebound",
            "min_drawdown_fraction": "0.4",
            "confirmation_rebound_fraction": "0.25",
        },
        "tokens": 2,
        "candidate_selected": True,
        "detector_freeze_ready": True,
        "uses_outcome_labels": False,
        "point_in_time_confirmation": True,
        "dump_threshold_frozen": True,
        "phase2_dump_detector_frozen": True,
        "outcome_labels_computed": False,
    }


def detector_rows():
    return [
        {
            "version": "phase2-dump-detector-freeze-v1",
            "detector_id": "chosen",
            "detector_family": "peak_drawdown_rebound",
            "token": TOKEN_A,
            "candidate_status": "confirmed",
            "trough_block": 4,
            "trough_transaction_index": 0,
            "trough_log_index": 0,
            "trough_market_cap_proxy_usd": "100",
            "confirmation_block": 5,
            "confirmation_transaction_index": 0,
            "confirmation_log_index": 0,
            "confirmation_market_cap_proxy_usd": "130",
            "point_in_time_confirmed": True,
            "detector_frozen": True,
        },
        {
            "version": "phase2-dump-detector-freeze-v1",
            "detector_id": "chosen",
            "detector_family": "peak_drawdown_rebound",
            "token": TOKEN_B,
            "candidate_status": "no_material_drawdown",
            "point_in_time_confirmed": False,
            "detector_frozen": True,
        },
    ]


def price_handoff():
    return {
        "version": "phase2-research-price-path-handoff-v1",
        "snapshot_head_block": 100,
        "universe_sha256": SHA,
        "normalized_price_path_sha256": SHA,
        "eligible_tokens": 2,
        "price_points": 8,
        "research_price_path_ready": True,
        "outcome_labels_computed": False,
    }


def price_rows():
    rows = [
        (TOKEN_A, 4, 0, 0, "100"),
        (TOKEN_A, 5, 0, 0, "130"),
        (TOKEN_A, 6, 0, 0, "80"),
        (TOKEN_A, 7, 0, 0, "200"),
        (TOKEN_A, 8, 0, 0, "500"),
        (TOKEN_A, 9, 0, 0, "1200"),
        (TOKEN_B, 10, 0, 0, "150"),
        (TOKEN_B, 11, 0, 0, "180"),
    ]
    return [
        {
            "version": "phase2-research-price-path-v1",
            "token": token,
            "block_number": block,
            "transaction_index": tx,
            "log_index": log,
            "market_cap_proxy_usd": value,
            "canonical_research_price_path": True,
        }
        for token, block, tx, log, value in rows
    ]


def test_outcomes_preserve_continuous_multiple_and_5x_minimum(tmp_path: Path):
    output = tmp_path / "outcomes.jsonl"
    manifest, summary = materialize_phase2_outcome_labels(
        detector_rows(),
        price_rows(),
        detector_summary=detector_summary(),
        price_path_handoff=price_handoff(),
        output=output,
    )

    rows = {
        row["token"]: row
        for row in (
            json.loads(line)
            for line in output.read_text().splitlines()
        )
    }
    winner = rows[TOKEN_A]
    assert winner["version"] == PHASE2_OUTCOME_LABEL_VERSION
    assert winner["outcome_eligible"] is True
    assert winner["comeback_5x"] is True
    assert winner["max_post_dump_multiple"] == "12"
    assert winner["maximum_forward_market_cap_proxy_usd"] == "1200"
    assert winner["reached_2x"] is True
    assert winner["reached_5x"] is True
    assert winner["reached_10x"] is True
    assert winner["time_to_5x_from_trough_blocks"] == 4
    assert winner["time_to_5x_from_confirmation_blocks"] == 3
    assert (
        winner[
            "maximum_adverse_excursion_from_confirmation_fraction"
        ]
        == "0.3846153846153846153846153846"
    )
    assert winner["right_censored_at_snapshot"] is True

    no_dump = rows[TOKEN_B]
    assert no_dump["outcome_eligible"] is False
    assert no_dump["comeback_5x"] is None
    assert no_dump["max_post_dump_multiple"] is None

    assert manifest["records"] == 2
    assert summary["confirmed_dump_tokens"] == 1
    assert summary["comeback_5x_tokens"] == 1
    assert summary["max_post_dump_multiple_retained"] is True
    assert summary["outcome_labels_computed"] is True


def test_outcome_timing_uses_exact_event_order_for_same_block(tmp_path: Path):
    detector = detector_rows()[:1]
    summary = detector_summary()
    summary["tokens"] = 1
    path = price_handoff()
    path["eligible_tokens"] = 1
    path["price_points"] = 4
    rows = [
        {
            "version": "phase2-research-price-path-v1",
            "token": TOKEN_A,
            "block_number": 4,
            "transaction_index": 0,
            "log_index": 0,
            "market_cap_proxy_usd": "100",
            "canonical_research_price_path": True,
        },
        {
            "version": "phase2-research-price-path-v1",
            "token": TOKEN_A,
            "block_number": 5,
            "transaction_index": 0,
            "log_index": 0,
            "market_cap_proxy_usd": "130",
            "canonical_research_price_path": True,
        },
        {
            "version": "phase2-research-price-path-v1",
            "token": TOKEN_A,
            "block_number": 5,
            "transaction_index": 1,
            "log_index": 0,
            "market_cap_proxy_usd": "500",
            "canonical_research_price_path": True,
        },
        {
            "version": "phase2-research-price-path-v1",
            "token": TOKEN_A,
            "block_number": 6,
            "transaction_index": 0,
            "log_index": 0,
            "market_cap_proxy_usd": "1000",
            "canonical_research_price_path": True,
        },
    ]

    output = tmp_path / "same-block.jsonl"
    materialize_phase2_outcome_labels(
        detector,
        rows,
        detector_summary=summary,
        price_path_handoff=path,
        output=output,
    )
    row = json.loads(output.read_text())
    assert row["first_5x_block"] == 5
    assert row["first_5x_transaction_index"] == 1
    assert row["time_to_5x_from_confirmation_blocks"] == 0


def test_outcome_handoff_binds_detector_and_keeps_continuous_target():
    summary = {
        "version": PHASE2_OUTCOME_LABEL_VERSION,
        "snapshot_head_block": 100,
        "universe_sha256": SHA,
        "normalized_price_path_sha256": SHA,
        "geometry_sha256": SHA,
        "selected_detector_id": "chosen",
        "tokens": 2,
        "confirmed_dump_tokens": 1,
        "comeback_5x_tokens": 1,
        "outcome_rows_sha256": SHA,
        "milestones": [2, 3, 5, 10],
        "post_dump_base_semantics": "retrospective_trough",
        "live_signal_semantics": "confirmation_event",
        "max_post_dump_multiple_retained": True,
        "candidate_selected": True,
        "dump_threshold_frozen": True,
        "phase2_dump_detector_frozen": True,
        "outcome_labels_computed": True,
    }

    handoff = build_phase2_outcome_handoff(
        summary,
        outcome_summary_sha256=SHA,
        detector_freeze_handoff_sha256=SHA,
        price_path_handoff_sha256=SHA,
    )
    assert handoff["version"] == PHASE2_OUTCOME_HANDOFF_VERSION
    assert handoff["selected_detector_id"] == "chosen"
    assert handoff["max_post_dump_multiple_retained"] is True
    assert handoff["outcome_labels_computed"] is True
