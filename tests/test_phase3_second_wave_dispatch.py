from hlp.data.phase3_second_wave_dispatch import (
    build_phase3_second_wave_plan,
    validate_phase3_second_wave_plan,
    validate_phase3_second_wave_launch_receipt,
    validate_phase3_second_wave_completion_receipt,
)


def first_completion():
    return {
        "version": "phase3-first-wave-completion-receipt-v1",
        "first_wave_completion_control_run_id": 17001,
        "first_wave_launch_run_id": 17002,
        "first_wave_launch_artifact_digest": "sha256:" + "11" * 32,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "12" * 20,
        "canonical_ledger_commit_sha": "12" * 20,
        "feature_entry_run_id": 17003,
        "feature_entry_artifact_digest": "sha256:" + "13" * 32,
        "feature_entry_handoff_sha256": "14" * 32,
        "expected_feature_subjects": 456,
        "outputs": {
            "canonical_transfer": {
                "run_id": 17004,
                "artifact_digest": "sha256:" + "15" * 32,
                "handoff_artifact_digest": "sha256:" + "16" * 32,
                "handoff_sha256": "17" * 32,
                "universe_tokens": 1234,
                "transfer_rows": 98765,
            },
            "price_features": {
                "run_id": 17005,
                "artifact_digest": "sha256:" + "18" * 32,
                "handoff_artifact_digest": "sha256:" + "19" * 32,
                "handoff_sha256": "1a" * 32,
                "feature_subjects": 456,
            },
            "chain_regime": {
                "run_id": 17006,
                "artifact_digest": "sha256:" + "1b" * 32,
                "handoff_artifact_digest": "sha256:" + "1c" * 32,
                "handoff_sha256": "1d" * 32,
                "feature_subjects": 456,
            },
            "venue_mechanics": {
                "run_id": 17007,
                "artifact_digest": "sha256:" + "1e" * 32,
                "handoff_artifact_digest": "sha256:" + "1f" * 32,
                "handoff_sha256": "20" * 32,
                "feature_subjects": 456,
            },
        },
        "target_runs_completed": 4,
        "all_target_runs_successful": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "workflow_dispatch_performed": False,
    }


def test_second_wave_plan_uses_transfer_parent():
    report = build_phase3_second_wave_plan(first_completion())
    assert report["dispatch_count"] == 4
    assert all(
        row["inputs"]["canonical_transfer_run_id"] == "17004"
        for row in report["dispatches"]
    )
    validated = validate_phase3_second_wave_plan(report)
    assert validated["feature_subjects"] == 456


def launch_receipt():
    plan = build_phase3_second_wave_plan(first_completion())
    return {
        "version": "phase3-second-wave-launch-receipt-v1",
        "second_wave_control_run_id": 17101,
        "second_wave_plan_run_id": 17102,
        "second_wave_plan_artifact_digest": "sha256:" + "21" * 32,
        "execution_branch": plan["execution_branch"],
        "execution_head_sha": plan["execution_head_sha"],
        "canonical_ledger_commit_sha": plan["canonical_ledger_commit_sha"],
        "feature_entry_run_id": plan["feature_entry_run_id"],
        "feature_entry_artifact_digest": plan[
            "feature_entry_artifact_digest"
        ],
        "feature_entry_handoff_sha256": plan[
            "feature_entry_handoff_sha256"
        ],
        "feature_subjects": plan["feature_subjects"],
        "canonical_transfer": plan["canonical_transfer"],
        "prior_feature_outputs": plan["prior_feature_outputs"],
        "target_run_ids": {
            "early_recipient": 17103,
            "holder": 17104,
            "lifecycle": 17105,
            "redistribution": 17106,
        },
        "target_runs_created": 4,
        "target_runs_waited_for_completion": False,
        "outcome_rows_consumed": False,
        "workflow_dispatch_performed": True,
    }


def test_second_wave_launch_has_four_unique_targets():
    report = validate_phase3_second_wave_launch_receipt(
        launch_receipt()
    )
    assert len(report["target_run_ids"]) == 4


def completion_receipt():
    launch = launch_receipt()
    return {
        "version": "phase3-second-wave-completion-receipt-v1",
        "second_wave_completion_control_run_id": 17201,
        "second_wave_launch_run_id": 17202,
        "second_wave_launch_artifact_digest": "sha256:" + "31" * 32,
        "execution_branch": launch["execution_branch"],
        "execution_head_sha": launch["execution_head_sha"],
        "canonical_ledger_commit_sha": launch[
            "canonical_ledger_commit_sha"
        ],
        "feature_entry_run_id": launch["feature_entry_run_id"],
        "feature_entry_artifact_digest": launch[
            "feature_entry_artifact_digest"
        ],
        "feature_entry_handoff_sha256": launch[
            "feature_entry_handoff_sha256"
        ],
        "expected_feature_subjects": launch["feature_subjects"],
        "canonical_transfer": launch["canonical_transfer"],
        "prior_feature_outputs": launch["prior_feature_outputs"],
        "outputs": {
            key: {
                "run_id": 17300 + index,
                "artifact_digest": "sha256:" + f"{40+index:02x}" * 32,
                "handoff_artifact_digest": "sha256:" + f"{50+index:02x}" * 32,
                "handoff_sha256": f"{60+index:02x}" * 32,
                "feature_subjects": 456,
            }
            for index, key in enumerate((
                "early_recipient",
                "holder",
                "lifecycle",
                "redistribution",
            ))
        },
        "target_runs_completed": 4,
        "all_target_runs_successful": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "workflow_dispatch_performed": False,
    }


def test_second_wave_completion_preserves_equal_subject_coverage():
    report = validate_phase3_second_wave_completion_receipt(
        completion_receipt()
    )
    assert report["feature_subjects"] == 456
    assert len(report["outputs"]) == 4
