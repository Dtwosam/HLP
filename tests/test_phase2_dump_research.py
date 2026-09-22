from copy import deepcopy

import pytest

from hlp.data.phase2_dump_research import (
    PHASE2_DUMP_CANDIDATE_RESEARCH_VERSION,
    PHASE2_DUMP_CANDIDATE_HANDOFF_VERSION,
    PHASE2_DUMP_CANDIDATE_DIAGNOSTICS_VERSION,
    PHASE2_DUMP_CANDIDATE_DIAGNOSTICS_HANDOFF_VERSION,
    PHASE2_DUMP_GEOMETRY_VERSION,
    PHASE2_DUMP_DETECTOR_FREEZE_VERSION,
    PHASE2_DUMP_DETECTOR_FREEZE_HANDOFF_VERSION,
    PHASE2_DUMP_GEOMETRY_HANDOFF_VERSION,
    build_phase2_dump_geometry,
    build_phase2_dump_geometry_handoff,
    materialize_phase2_dump_geometry,
    materialize_phase2_dump_candidate_research,
    build_phase2_dump_candidate_handoff,
    build_phase2_dump_candidate_diagnostics,
    build_phase2_dump_candidate_diagnostics_handoff,
    research_phase2_dump_candidates,
    materialize_phase2_dump_detector_freeze,
    build_phase2_dump_detector_freeze_handoff,
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



def test_streaming_dump_geometry_matches_causal_row_semantics(tmp_path):
    universe_rows, summary = universe()
    source = price_rows()
    output = tmp_path / "geometry.jsonl"

    manifest, streamed = materialize_phase2_dump_geometry(
        universe_rows,
        iter(source),
        universe_summary=summary,
        universe_sha256=SHA,
        price_path_provenance_sha256=SHA,
        normalized_price_path_sha256=SHA,
        output=output,
    )
    import json
    actual = [
        json.loads(line)
        for line in output.read_text().splitlines()
        if line.strip()
    ]
    expected, expected_summary = build_phase2_dump_geometry(
        universe_rows,
        source,
        universe_summary=summary,
        universe_sha256=SHA,
        price_path_provenance_sha256=SHA,
    )

    assert actual == expected
    assert streamed["price_points"] == expected_summary["price_points"]
    assert streamed["token_max_drawdown_fraction"] == expected_summary[
        "token_max_drawdown_fraction"
    ]
    assert streamed["geometry_sha256"] == manifest["sha256"]
    assert streamed["streaming_materialization"] is True
    assert streamed["phase2_dump_detector_frozen"] is False


def test_dump_geometry_handoff_keeps_detector_unselected(tmp_path):
    universe_rows, summary = universe()
    _, streamed = materialize_phase2_dump_geometry(
        universe_rows,
        iter(price_rows()),
        universe_summary=summary,
        universe_sha256=SHA,
        price_path_provenance_sha256=SHA,
        normalized_price_path_sha256=SHA,
        output=tmp_path / "geometry.jsonl",
    )
    handoff = build_phase2_dump_geometry_handoff(
        streamed,
        geometry_summary_sha256=SHA,
        price_path_handoff_sha256=SHA,
    )
    assert handoff["version"] == PHASE2_DUMP_GEOMETRY_HANDOFF_VERSION
    assert handoff["dump_geometry_ready"] is True
    assert handoff["candidate_selected"] is False
    assert handoff["dump_threshold_frozen"] is False
    assert handoff["outcome_labels_computed"] is False



def test_streaming_dump_geometry_cleans_partial_output_on_missing_token(
    tmp_path,
):
    universe_rows, summary = universe((TOKEN_A, TOKEN_B))
    output = tmp_path / "geometry-partial.jsonl"

    with pytest.raises(ValueError, match="coverage missing"):
        materialize_phase2_dump_geometry(
            universe_rows,
            iter(price_rows(TOKEN_A)),
            universe_summary=summary,
            universe_sha256=SHA,
            price_path_provenance_sha256=SHA,
            normalized_price_path_sha256=SHA,
            output=output,
        )

    assert not output.exists()
    assert not output.with_suffix(".jsonl.tmp").exists()



def test_streaming_candidate_research_matches_existing_candidate_semantics(
    tmp_path,
):
    rows, summary = geometry()
    specs = [
        candidate("confirmed", "0.4", "0.25"),
        candidate("too-deep", "0.6", "0.25"),
    ]
    expected, expected_summary = research_phase2_dump_candidates(
        rows,
        specs,
        geometry_summary=summary,
    )
    summary = {
        **summary,
        "normalized_price_path_sha256": SHA,
        "geometry_sha256": SHA,
    }
    output = tmp_path / "candidates.jsonl"
    manifest, streamed = materialize_phase2_dump_candidate_research(
        iter(rows),
        specs,
        geometry_summary=summary,
        output=output,
    )

    import json
    actual = [
        json.loads(line)
        for line in output.read_text().splitlines()
        if line.strip()
    ]
    assert actual == expected
    assert streamed["candidate_status_counts"] == expected_summary[
        "candidate_status_counts"
    ]
    assert streamed["candidate_rows"] == len(expected)
    assert streamed["candidate_rows_sha256"] == manifest["sha256"]
    assert streamed["streaming_evaluation"] is True
    assert streamed["candidate_selected"] is False
    assert streamed["outcome_labels_computed"] is False


def test_candidate_handoff_cannot_select_or_freeze_detector(tmp_path):
    rows, summary = geometry()
    summary = {
        **summary,
        "normalized_price_path_sha256": SHA,
        "geometry_sha256": SHA,
    }
    _, research = materialize_phase2_dump_candidate_research(
        iter(rows),
        [candidate()],
        geometry_summary=summary,
        output=tmp_path / "candidate.jsonl",
    )
    handoff = build_phase2_dump_candidate_handoff(
        research,
        research_summary_sha256=SHA,
        geometry_handoff_sha256=SHA,
    )
    assert handoff["version"] == PHASE2_DUMP_CANDIDATE_HANDOFF_VERSION
    assert handoff["candidate_research_ready"] is True
    assert handoff["candidate_selected"] is False
    assert handoff["phase2_dump_detector_frozen"] is False
    assert handoff["outcome_labels_computed"] is False



def test_candidate_diagnostics_report_live_structure_without_outcomes(tmp_path):
    rows, geometry_summary = geometry()
    geometry_summary = {
        **geometry_summary,
        "normalized_price_path_sha256": SHA,
        "geometry_sha256": SHA,
    }
    output = tmp_path / "candidate.jsonl"
    _, research = materialize_phase2_dump_candidate_research(
        iter(rows),
        [
            candidate("candidate-a", "0.4", "0.25"),
            candidate("candidate-b", "0.4", "0.25"),
        ],
        geometry_summary=geometry_summary,
        output=output,
    )
    import json
    candidate_rows = [
        json.loads(line)
        for line in output.read_text().splitlines()
        if line.strip()
    ]
    diagnostics, summary = build_phase2_dump_candidate_diagnostics(
        candidate_rows,
        research_summary=research,
    )

    assert len(diagnostics) == 2
    first = diagnostics[0]
    assert first["status_counts"] == {"confirmed": 1}
    assert first["confirmed_fraction"] == "1"
    assert first["threshold_to_trough_blocks"]["median"] == "1"
    assert first["trough_to_confirmation_blocks"]["median"] == "1"
    assert first["observed_drawdown_fraction"]["median"] == "0.5"
    assert first["uses_outcome_labels"] is False
    assert first["detector_freeze_ready"] is False
    assert summary["version"] == PHASE2_DUMP_CANDIDATE_DIAGNOSTICS_VERSION
    assert summary["equivalent_candidate_pairs"] == [
        ["candidate-a", "candidate-b"]
    ]
    assert summary["candidate_selected"] is False
    assert summary["outcome_labels_computed"] is False



def test_candidate_diagnostics_handoff_cannot_self_approve_freeze(tmp_path):
    rows, geometry_summary = geometry()
    geometry_summary = {
        **geometry_summary,
        "normalized_price_path_sha256": SHA,
        "geometry_sha256": SHA,
    }
    output = tmp_path / "candidate.jsonl"
    _, research = materialize_phase2_dump_candidate_research(
        iter(rows),
        [candidate()],
        geometry_summary=geometry_summary,
        output=output,
    )
    import json
    candidate_rows = [
        json.loads(line)
        for line in output.read_text().splitlines()
        if line.strip()
    ]
    _, diagnostics_summary = build_phase2_dump_candidate_diagnostics(
        candidate_rows,
        research_summary=research,
    )
    handoff = build_phase2_dump_candidate_diagnostics_handoff(
        diagnostics_summary,
        diagnostics_sha256=SHA,
        diagnostics_summary_sha256=SHA,
        candidate_research_handoff_sha256=SHA,
    )
    assert handoff[
        "version"
    ] == PHASE2_DUMP_CANDIDATE_DIAGNOSTICS_HANDOFF_VERSION
    assert handoff["candidate_selected"] is False
    assert handoff["detector_freeze_ready"] is False
    assert handoff["phase2_dump_detector_frozen"] is False
    assert handoff["outcome_labels_computed"] is False



def test_explicit_detector_freeze_uses_diagnostics_but_never_outcomes(tmp_path):
    rows, geometry_summary = geometry()
    geometry_summary = {
        **geometry_summary,
        "normalized_price_path_sha256": SHA,
        "geometry_sha256": SHA,
    }
    candidate_path = tmp_path / "candidates.jsonl"
    _, research = materialize_phase2_dump_candidate_research(
        iter(rows),
        [
            candidate("chosen", "0.4", "0.25"),
            candidate("other", "0.6", "0.25"),
        ],
        geometry_summary=geometry_summary,
        output=candidate_path,
    )
    import json
    candidate_rows = [
        json.loads(line)
        for line in candidate_path.read_text().splitlines()
        if line.strip()
    ]
    diagnostics_rows, diagnostics_summary = (
        build_phase2_dump_candidate_diagnostics(
            candidate_rows,
            research_summary=research,
        )
    )
    output = tmp_path / "frozen.jsonl"
    manifest, frozen = materialize_phase2_dump_detector_freeze(
        candidate_rows,
        diagnostics_rows,
        research_summary=research,
        diagnostics_summary=diagnostics_summary,
        selected_candidate_id="chosen",
        output=output,
    )

    assert frozen["version"] == PHASE2_DUMP_DETECTOR_FREEZE_VERSION
    assert frozen["selected_candidate_id"] == "chosen"
    assert frozen["selected_candidate_spec"][
        "min_drawdown_fraction"
    ] == "0.4"
    assert frozen["tokens"] == 1
    assert frozen["detector_rows"] == 1
    assert frozen["confirmed_tokens"] == 1
    assert frozen["uses_outcome_labels"] is False
    assert frozen["candidate_selected"] is True
    assert frozen["phase2_dump_detector_frozen"] is True
    assert frozen["outcome_labels_computed"] is False

    row = json.loads(output.read_text())
    assert row["version"] == PHASE2_DUMP_DETECTOR_FREEZE_VERSION
    assert row["detector_id"] == "chosen"
    assert row["detector_frozen"] is True
    assert row["point_in_time_confirmed"] is True
    assert manifest["sha256"] == frozen["detector_rows_sha256"]


def test_detector_freeze_handoff_binds_explicit_selection(tmp_path):
    rows, geometry_summary = geometry()
    geometry_summary = {
        **geometry_summary,
        "normalized_price_path_sha256": SHA,
        "geometry_sha256": SHA,
    }
    candidate_path = tmp_path / "candidates.jsonl"
    _, research = materialize_phase2_dump_candidate_research(
        iter(rows),
        [candidate("chosen", "0.4", "0.25")],
        geometry_summary=geometry_summary,
        output=candidate_path,
    )
    import json
    candidate_rows = [
        json.loads(line)
        for line in candidate_path.read_text().splitlines()
        if line.strip()
    ]
    diagnostics_rows, diagnostics_summary = (
        build_phase2_dump_candidate_diagnostics(
            candidate_rows,
            research_summary=research,
        )
    )
    _, frozen = materialize_phase2_dump_detector_freeze(
        candidate_rows,
        diagnostics_rows,
        research_summary=research,
        diagnostics_summary=diagnostics_summary,
        selected_candidate_id="chosen",
        output=tmp_path / "frozen.jsonl",
    )
    handoff = build_phase2_dump_detector_freeze_handoff(
        frozen,
        freeze_summary_sha256=SHA,
        candidate_research_handoff_sha256=SHA,
        candidate_diagnostics_handoff_sha256=SHA,
    )
    assert (
        handoff["version"]
        == PHASE2_DUMP_DETECTOR_FREEZE_HANDOFF_VERSION
    )
    assert handoff["selected_candidate_id"] == "chosen"
    assert handoff["candidate_selected"] is True
    assert handoff["detector_freeze_ready"] is True
    assert handoff["phase2_dump_detector_frozen"] is True
    assert handoff["outcome_labels_computed"] is False


def test_detector_freeze_rejects_unknown_candidate_and_outcome_contamination(
    tmp_path,
):
    rows, geometry_summary = geometry()
    geometry_summary = {
        **geometry_summary,
        "normalized_price_path_sha256": SHA,
        "geometry_sha256": SHA,
    }
    candidate_path = tmp_path / "candidates.jsonl"
    _, research = materialize_phase2_dump_candidate_research(
        iter(rows),
        [candidate("chosen", "0.4", "0.25")],
        geometry_summary=geometry_summary,
        output=candidate_path,
    )
    import json
    candidate_rows = [
        json.loads(line)
        for line in candidate_path.read_text().splitlines()
        if line.strip()
    ]
    diagnostics_rows, diagnostics_summary = (
        build_phase2_dump_candidate_diagnostics(
            candidate_rows,
            research_summary=research,
        )
    )

    with pytest.raises(ValueError, match="unknown"):
        materialize_phase2_dump_detector_freeze(
            candidate_rows,
            diagnostics_rows,
            research_summary=research,
            diagnostics_summary=diagnostics_summary,
            selected_candidate_id="missing",
            output=tmp_path / "missing.jsonl",
        )

    contaminated = deepcopy(diagnostics_summary)
    contaminated["outcome_labels_computed"] = True
    with pytest.raises(ValueError, match="outcome labels"):
        materialize_phase2_dump_detector_freeze(
            candidate_rows,
            diagnostics_rows,
            research_summary=research,
            diagnostics_summary=contaminated,
            selected_candidate_id="chosen",
            output=tmp_path / "contaminated.jsonl",
        )
