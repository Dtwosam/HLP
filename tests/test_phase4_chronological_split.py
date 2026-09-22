import json
from pathlib import Path

import pytest

from hlp.data.phase4_chronological_split import (
    PHASE4_CHRONOLOGICAL_SPLIT_HANDOFF_VERSION,
    PHASE4_CHRONOLOGICAL_SPLIT_VERSION,
    build_phase4_chronological_split_handoff,
    materialize_phase4_chronological_split,
)


SHA = "ab" * 32


def handoff():
    return {
        "version": "phase4-discovery-entry-handoff-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": SHA,
        "discovery_rows_sha256": SHA,
        "discovery_subjects": 6,
        "labels_joined_after_feature_freeze": True,
        "feature_values_mutated": False,
        "phase4_discovery_entry_ready": True,
        "phase4_discovery_checkpoint_claimed": False,
    }


def row(index, block, winner):
    return {
        "version": "phase4-discovery-entry-v1",
        "token": "0x" + f"{index:040x}",
        "feature_cutoff_block": block,
        "feature_cutoff_transaction_index": 0,
        "feature_cutoff_log_index": 0,
        "feature_values": {"unit.value": str(index)},
        "missing_feature_ids": [],
        "target_comeback_5x": winner,
        "labels_joined_after_feature_freeze": True,
        "feature_values_mutated": False,
        "phase4_discovery_only": True,
    }


def test_chronological_split_uses_only_cutoff_blocks(tmp_path: Path):
    outputs = {
        "discovery": tmp_path / "discovery.jsonl",
        "validation": tmp_path / "validation.jsonl",
        "final": tmp_path / "final.jsonl",
    }
    manifests, summary = materialize_phase4_chronological_split(
        [
            row(6, 60, True),
            row(2, 20, False),
            row(4, 40, True),
            row(1, 10, True),
            row(5, 50, False),
            row(3, 30, False),
        ],
        discovery_entry_handoff=handoff(),
        discovery_end_block=30,
        validation_end_block=50,
        discovery_output=outputs["discovery"],
        validation_output=outputs["validation"],
        final_test_output=outputs["final"],
    )

    assert summary["version"] == PHASE4_CHRONOLOGICAL_SPLIT_VERSION
    assert summary["split_ranges"]["discovery"]["rows"] == 3
    assert summary["split_ranges"]["validation"]["rows"] == 2
    assert summary["split_ranges"]["final_test"]["rows"] == 1
    assert summary["split_assignment_uses_feature_values"] is False
    assert summary["split_assignment_uses_outcome_values"] is False
    assert summary["random_shuffle_used"] is False
    assert summary["final_test_separated"] is True
    assert manifests["discovery"]["records"] == 3

    discovery = [
        json.loads(line)
        for line in outputs["discovery"].read_text().splitlines()
    ]
    assert [row["feature_cutoff_block"] for row in discovery] == [
        10,
        20,
        30,
    ]


def test_chronological_split_rejects_empty_final_test(tmp_path: Path):
    with pytest.raises(ValueError, match="no final-test subjects"):
        materialize_phase4_chronological_split(
            [row(i, i * 10, bool(i % 2)) for i in range(1, 7)],
            discovery_entry_handoff=handoff(),
            discovery_end_block=30,
            validation_end_block=60,
            discovery_output=tmp_path / "d.jsonl",
            validation_output=tmp_path / "v.jsonl",
            final_test_output=tmp_path / "f.jsonl",
        )


def test_chronological_split_handoff_keeps_final_test_separate():
    summary = {
        "version": PHASE4_CHRONOLOGICAL_SPLIT_VERSION,
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": SHA,
        "discovery_rows_sha256": SHA,
        "discovery_subjects": 10,
        "discovery_end_block": 100,
        "validation_end_block": 200,
        "split_ranges": {
            "discovery": {"rows": 6, "rows_sha256": SHA},
            "validation": {"rows": 2, "rows_sha256": SHA},
            "final_test": {"rows": 2, "rows_sha256": SHA},
        },
        "split_assignment_uses_feature_values": False,
        "split_assignment_uses_outcome_values": False,
        "random_shuffle_used": False,
        "chronological_order_enforced": True,
        "feature_values_mutated": False,
        "final_test_separated": True,
        "phase4_chronological_split_ready": True,
        "phase4_split_frozen": True,
        "phase4_discovery_checkpoint_claimed": False,
    }
    result = build_phase4_chronological_split_handoff(
        summary,
        split_summary_sha256=SHA,
        discovery_entry_handoff_sha256=SHA,
        feature_registry_file_sha256=SHA,
    )
    assert (
        result["version"]
        == PHASE4_CHRONOLOGICAL_SPLIT_HANDOFF_VERSION
    )
    assert result["split_assignment_uses_outcome_values"] is False
    assert result["random_shuffle_used"] is False
    assert result["final_test_separated"] is True
    assert result["phase4_discovery_checkpoint_claimed"] is False
