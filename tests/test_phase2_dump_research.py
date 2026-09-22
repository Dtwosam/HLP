from copy import deepcopy

import pytest

from hlp.data.phase2_dump_research import (
    PHASE2_DUMP_CANDIDATE_RESEARCH_VERSION,
    PHASE2_DUMP_GEOMETRY_VERSION,
    build_phase2_dump_geometry,
    research_phase2_dump_candidates,
)
from hlp.data.phase2_universe import PHASE2_UNIVERSE_VERSION


SHA = "ab" * 32
TOKEN_A = "0x" + "11" * 20
TOKEN_B = "0x" + "22" * 20


def universe(tokens=(TOKEN_A,)):
    rows = [
        {
            "token": token,
            "universe_status": "eligible",
        }
        for token in tokens
    ]
    summary = {
        "version": PHASE2_UNIVERSE_VERSION,
        "snapshot_head_block": 100,
        "eligible_tokens": len(rows),
        "coverage_complete": True,
        "phase2_universe_frozen": True,
    }
    return rows, summary


def price_rows(token=TOKEN_A):
    values = [
        (1, 100_000),
        (2, 200_000),
        (3, 120_000),
        (4, 100_000),
        (5, 130_000),
        (6, 600_000),
    ]
    return [
        {
            "token": token,
            "block_number": block,
            "transaction_index": 0,
            "log_index": 0,
            "market_cap_proxy_usd": str(value),
        }
        for block, value in values
    ]


def geometry(rows=None, tokens=(TOKEN_A,)):
    universe_rows, summary = universe(tokens)
    return build_phase2_dump_geometry(
        universe_rows,
        price_rows() if rows is None else rows,
        universe_summary=summary,
        universe_sha256=SHA,
        price_path_provenance_sha256=SHA,
    )


def candidate(
    candidate_id="candidate-a",
    drawdown="0.4",
    rebound="0.25",
):
    return {
        "candidate_id": candidate_id,
        "min_drawdown_fraction": drawdown,
        "confirmation_rebound_fraction": rebound,
    }


def test_dump_geometry_is_causal_and_does_not_freeze_threshold():
    rows, summary = geometry()

    assert summary["version"] == PHASE2_DUMP_GEOMETRY_VERSION
    assert summary["tokens"] == 1
    assert summary["price_points"] == 6
    assert summary["uses_price_path_only"] is True
    assert summary["dump_threshold_frozen"] is False
    assert summary["outcome_labels_computed"] is False

    by_block = {row["block_number"]: row for row in rows}
    assert by_block[2]["is_new_trailing_peak"] is True
    assert by_block[3]["trailing_peak_block"] == 2
    assert by_block[3]["drawdown_fraction"] == "0.4"
    assert by_block[4]["drawdown_fraction"] == "0.5"
    assert by_block[6]["is_new_trailing_peak"] is True
    assert by_block[6]["drawdown_fraction"] == "0"


def test_dump_candidate_records_retrospective_trough_and_causal_confirmation():
    rows, summary = geometry()

    results, research = research_phase2_dump_candidates(
        rows,
        [candidate()],
        geometry_summary=summary,
    )

    assert research["version"] == PHASE2_DUMP_CANDIDATE_RESEARCH_VERSION
    assert research["candidate_selected"] is False
    assert research["phase2_dump_detector_frozen"] is False
    assert research["outcome_labels_computed"] is False
    assert research["candidate_status_counts"] == {
        "candidate-a": {"confirmed": 1}
    }

    event = results[0]
    assert event["candidate_status"] == "confirmed"
    assert event["peak_block"] == 2
    assert event["threshold_cross_block"] == 3
    assert event["trough_block"] == 4
    assert event["confirmation_block"] == 5
    assert event["observed_drawdown_fraction"] == "0.5"
    assert event["observed_confirmation_rebound_fraction"] == "0.3"
    assert event["point_in_time_confirmed"] is True
    assert event["research_candidate_only"] is True


def test_dump_candidate_confirmation_is_stable_when_future_rally_is_appended():
    prefix_rows = price_rows()[:5]
    prefix_geometry, prefix_summary = geometry(prefix_rows)
    prefix_results, _ = research_phase2_dump_candidates(
        prefix_geometry,
        [candidate()],
        geometry_summary=prefix_summary,
    )

    full_geometry, full_summary = geometry()
    full_results, _ = research_phase2_dump_candidates(
        full_geometry,
        [candidate()],
        geometry_summary=full_summary,
    )

    keys = (
        "peak_block",
        "threshold_cross_block",
        "trough_block",
        "confirmation_block",
        "observed_drawdown_fraction",
        "observed_confirmation_rebound_fraction",
    )
    assert {
        key: prefix_results[0][key] for key in keys
    } == {
        key: full_results[0][key] for key in keys
    }


def test_dump_research_compares_explicit_candidates_without_selecting_one():
    rows, summary = geometry()

    results, research = research_phase2_dump_candidates(
        rows,
        [
            candidate("confirmed", "0.4", "0.25"),
            candidate("too-deep", "0.6", "0.25"),
        ],
        geometry_summary=summary,
    )

    by_id = {row["candidate_id"]: row for row in results}
    assert by_id["confirmed"]["candidate_status"] == "confirmed"
    assert by_id["too-deep"]["candidate_status"] == "no_material_drawdown"
    assert research["candidate_selected"] is False
    assert research["dump_threshold_frozen"] is False


def test_dump_research_requires_frozen_universe_and_complete_token_paths():
    universe_rows, summary = universe()
    summary["phase2_universe_frozen"] = False
    with pytest.raises(ValueError, match="requires a frozen"):
        build_phase2_dump_geometry(
            universe_rows,
            price_rows(),
            universe_summary=summary,
            universe_sha256=SHA,
            price_path_provenance_sha256=SHA,
        )

    universe_rows, summary = universe((TOKEN_A, TOKEN_B))
    with pytest.raises(ValueError, match="coverage missing"):
        build_phase2_dump_geometry(
            universe_rows,
            price_rows(),
            universe_summary=summary,
            universe_sha256=SHA,
            price_path_provenance_sha256=SHA,
        )


def test_dump_research_has_no_implicit_candidate_defaults_or_outcome_state():
    rows, summary = geometry()
    with pytest.raises(ValueError, match="explicit candidate specs"):
        research_phase2_dump_candidates(
            rows,
            [],
            geometry_summary=summary,
        )

    contaminated = deepcopy(summary)
    contaminated["outcome_labels_computed"] = True
    with pytest.raises(ValueError, match="cannot consume outcome labels"):
        research_phase2_dump_candidates(
            rows,
            [candidate()],
            geometry_summary=contaminated,
        )
