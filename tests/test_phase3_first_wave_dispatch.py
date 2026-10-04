from hlp.data.phase3_first_wave_dispatch import (
    build_phase3_first_wave_plan,
    validate_phase3_first_wave_plan,
    validate_phase3_first_wave_launch_receipt,
    validate_phase3_first_wave_completion_receipt,
)


def entry_completion():
    return {
        "version": "phase3-feature-entry-completion-receipt-v1",
        "feature_entry_completion_control_run_id": 16001,
        "feature_entry_launch_run_id": 16002,
        "feature_entry_launch_artifact_digest": "sha256:" + "11" * 32,
        "feature_entry_run_id": 16003,
        "feature_entry_artifact_digest": "sha256:" + "12" * 32,
        "feature_entry_handoff_artifact_digest": "sha256:" + "13" * 32,
        "feature_subjects_sha256": "14" * 32,
        "entry_summary_sha256": "15" * 32,
        "entry_handoff_sha256": "16" * 32,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "17" * 20,
        "canonical_ledger_commit_sha": "17" * 20,
        "universe_run_id": 16004,
        "universe_artifact_digest": "sha256:" + "18" * 32,
        "universe_handoff_sha256": "19" * 32,
        "price_path_run_id": 16005,
        "price_path_artifact_digest": "sha256:" + "1a" * 32,
        "price_path_handoff_sha256": "1b" * 32,
        "feature_subjects": 456,
        "snapshot_kind": "first_major_dump_confirmation",
        "target_run_completed": True,
        "target_run_successful": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "phase3_feature_values_computed": False,
        "phase3_feature_entry_ready": True,
        "workflow_dispatch_performed": False,
    }


def test_first_wave_plan_dispatches_four_safe_nodes():
    report = build_phase3_first_wave_plan(entry_completion())
    assert report["dispatch_count"] == 4
    assert {
        row["node_id"] for row in report["dispatches"]
    } == {
        "canonical_transfer",
        "price_features",
        "chain_regime",
        "venue_mechanics",
    }
    validated = validate_phase3_first_wave_plan(report)
    assert validated["outcome_rows_consumed"] is False


def launch_receipt():
    return {
        "version": "phase3-first-wave-launch-receipt-v1",
        "first_wave_control_run_id": 16101,
        "first_wave_plan_run_id": 16102,
        "first_wave_plan_artifact_digest": "sha256:" + "21" * 32,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "22" * 20,
        "canonical_ledger_commit_sha": "22" * 20,
        "target_run_ids": {
            "canonical_transfer": 16103,
            "price_features": 16104,
            "chain_regime": 16105,
            "venue_mechanics": 16106,
        },
        "target_runs_created": 4,
        "target_runs_waited_for_completion": False,
        "outcome_rows_consumed": False,
        "workflow_dispatch_performed": True,
    }


def test_first_wave_launch_requires_unique_targets():
    report = validate_phase3_first_wave_launch_receipt(launch_receipt())
    assert len(report["target_run_ids"]) == 4


def completion_receipt():
    return {
        "version": "phase3-first-wave-completion-receipt-v1",
        "first_wave_completion_control_run_id": 16201,
        "first_wave_launch_run_id": 16202,
        "first_wave_launch_artifact_digest": "sha256:" + "31" * 32,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "32" * 20,
        "canonical_ledger_commit_sha": "32" * 20,
        "outputs": {
            key: {
                "run_id": 16300 + index,
                "artifact_digest": "sha256:" + f"{40+index:02x}" * 32,
                "handoff_artifact_digest": "sha256:" + f"{50+index:02x}" * 32,
                "handoff_sha256": f"{60+index:02x}" * 32,
                "feature_subjects": 456,
            }
            for index, key in enumerate((
                "canonical_transfer",
                "price_features",
                "chain_regime",
                "venue_mechanics",
            ))
        },
        "target_runs_completed": 4,
        "all_target_runs_successful": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "workflow_dispatch_performed": False,
    }


def test_first_wave_completion_has_equal_subject_coverage():
    report = validate_phase3_first_wave_completion_receipt(
        completion_receipt()
    )
    assert report["feature_subjects"] == 456
