from pathlib import Path


WORKFLOWS = [
    "phase1-pons-v1-registry-recovery.yml",
    "phase1-pons-full-quote-audit.yml",
    "phase1-pons-v2-stock-oracle-full.yml",
    "phase1-pons-v2-curve-full.yml",
    "phase1-pons-v2-transition-full.yml",
    "phase1-pons-weth-usdg-anchor-full.yml",
    "phase1-pons-v2-v4-full.yml",
    "phase1-pons-v2-lifecycle-eligibility.yml",
    "phase1-pons-stock-oracle-full.yml",
    "phase1-pons-v1-v3-full.yml",
    "phase1-pons-v1-lifecycle-eligibility.yml",
    "phase1-pons-eligible-universe-freeze.yml",
    "phase1-pons-representative-sample-freeze.yml",
    "phase1-pons-v3-quote-fallback-full.yml",
    "phase1-pons-v4-quote-fallback-full.yml",
    "phase1-pons-quote-fallback-full.yml",
    "phase1-pons-v4-quote-continuation.yml",
    "phase1-pons-skhy-v3-weth-continuation.yml",
    "phase1-pons-skhy-v3-weth-segmented.yml",
    "phase1-pons-skhy-v4-known-pool-continuation.yml",
    "phase1-pons-skhy-v4-known-pool-segmented.yml",
    "phase1-pons-representative-transfers-full.yml",
    "phase1-pons-representative-evidence-chain.yml",
    "phase1-pons-acquisition-accounting.yml",
    "phase1-pons-viability-route-measurement.yml",
]

MATRIX_WORKFLOWS = {
    "phase1-pons-v1-registry-recovery.yml",
    "phase1-pons-v2-stock-oracle-full.yml",
    "phase1-pons-v2-curve-full.yml",
    "phase1-pons-v2-transition-full.yml",
    "phase1-pons-weth-usdg-anchor-full.yml",
    "phase1-pons-v2-v4-full.yml",
    "phase1-pons-stock-oracle-full.yml",
    "phase1-pons-v1-v3-full.yml",
}


def _workflow(name: str) -> str:
    return (
        Path(__file__).parents[1] / ".github" / "workflows" / name
    ).read_text()


def _embedded_python_blocks(content: str) -> list[str]:
    lines = content.splitlines()
    blocks: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.strip() != "python - <<'PY'":
            index += 1
            continue

        indent = len(line) - len(line.lstrip())
        body: list[str] = []
        index += 1
        while index < len(lines):
            current = lines[index]
            current_indent = len(current) - len(current.lstrip())
            if current.strip() == "PY" and current_indent == indent:
                break
            body.append(
                current[indent:]
                if len(current) >= indent
                else current.lstrip()
            )
            index += 1
        else:
            raise AssertionError("unterminated embedded Python heredoc")

        blocks.append("\n".join(body) + "\n")
        index += 1
    return blocks


def test_critical_phase1_workflow_python_heredocs_compile():
    critical = (
        "phase1-pons-v1-v3-recover-gaps.yml",
        "phase1-pons-v1-lifecycle-eligibility.yml",
        "phase1-pons-v2-v4-recover-gaps.yml",
        "phase1-pons-v2-lifecycle-eligibility.yml",
        "phase1-pons-recovered-completion-chain.yml",
        "phase1-pons-post-eligibility-evidence-chain.yml",
        "phase1-pons-representative-evidence-chain.yml",
        "phase1-pons-representative-evidence-one-shot.yml",
        "phase1-pons-representative-transfers-full.yml",
        "phase1-pons-acquisition-accounting.yml",
        "phase1-pons-acquisition-viability-projection.yml",
        "phase1-pons-viability-route-measurement.yml",
        "phase1-pons-final-acceptance-chain.yml",
        "phase1-pons-acceptance-gate.yml",
        "phase1-pons-pass-closeout-one-shot.yml",
        "phase1-pons-readiness-audit.yml",
        "phase1-pons-v2-v4-filter-comparison.yml",
        "phase1-pons-skhy-v3-weth-continuation.yml",
        "phase1-pons-skhy-v3-weth-segmented.yml",
        "phase1-pons-skhy-v4-known-pool-continuation.yml",
        "phase1-pons-skhy-v4-known-pool-segmented.yml",
        "phase1-pons-v3-quote-fallback-full.yml",
        "phase1-pons-v4-quote-fallback-full.yml",
    )
    for name in critical:
        blocks = _embedded_python_blocks(_workflow(name))
        assert blocks, name
        for index, block in enumerate(blocks):
            compile(
                block,
                f"{name}:embedded-python-{index}",
                "exec",
            )


def test_critical_upload_artifact_steps_have_local_configuration():
    for name in WORKFLOWS:
        lines = _workflow(name).splitlines()
        for index, line in enumerate(lines):
            if "uses: actions/upload-artifact@v4" not in line:
                continue

            use_indent = len(line) - len(line.lstrip())
            if line.lstrip().startswith("- uses:"):
                step_indent = use_indent
                step_start = index
            else:
                step_indent = use_indent - 2
                step_start = index
                while step_start >= 0:
                    candidate = lines[step_start]
                    candidate_indent = len(candidate) - len(candidate.lstrip())
                    if (
                        candidate_indent == step_indent
                        and candidate.lstrip().startswith("- ")
                    ):
                        break
                    step_start -= 1
                assert step_start >= 0, (name, index + 1)

            step_end = len(lines)
            for end in range(index + 1, len(lines)):
                candidate = lines[end]
                candidate_indent = len(candidate) - len(candidate.lstrip())
                if (
                    candidate_indent == step_indent
                    and candidate.lstrip().startswith("- ")
                ):
                    step_end = end
                    break

            block = lines[step_start:step_end]
            assert any(row.strip() == "with:" for row in block), (
                name,
                index + 1,
                block,
            )
            assert any(row.strip().startswith("path:") for row in block), (
                name,
                index + 1,
                block,
            )


def test_pons_heavy_workflows_never_poll_other_runs():
    forbidden = (
        "time.sleep(",
        "for attempt in range",
        "Wait for recovered",
        "Wait for V2",
        "Wait for all original",
    )
    for name in WORKFLOWS:
        content = _workflow(name)
        for needle in forbidden:
            assert needle not in content, (
                f"{name} must fail fast on unavailable prerequisites; "
                f"runner-side polling is forbidden: {needle!r}"
            )


def test_pons_heavy_workflows_have_concurrency_locks():
    for name in WORKFLOWS:
        content = _workflow(name)
        assert "concurrency:" in content, name
        expected = "group: " + name.removesuffix(".yml") + "-${{ github.ref }}"
        assert expected in content, name
        assert "cancel-in-progress:" in content, name


def test_archive_matrix_workflows_are_small_and_bounded():
    for name in MATRIX_WORKFLOWS:
        content = _workflow(name)
        assert "max-parallel: 2" in content, name
        if name == "phase1-pons-v2-v4-full.yml":
            assert "SHARD_COUNT: '192'" in content, name
            assert "timeout-minutes: 30" in content, name
            assert content.count("--global-pool-scan") == 1, name
        elif name == "phase1-pons-v1-v3-full.yml":
            assert "SHARD_COUNT: '240'" in content, name
            assert "timeout-minutes: 40" in content, name
        elif name == "phase1-pons-v2-curve-full.yml":
            assert "SHARD_COUNT: '64'" in content, name
            assert "timeout-minutes: 25" in content, name
        elif name == "phase1-pons-weth-usdg-anchor-full.yml":
            assert "SHARD_COUNT: '128'" in content, name
            assert "timeout-minutes: 25" in content, name
        else:
            assert "SHARD_COUNT: '16'" in content, name
            assert "timeout-minutes: 35" in content, name
        if name in {
            "phase1-pons-v1-v3-full.yml",
            "phase1-pons-v2-v4-full.yml",
            "phase1-pons-weth-usdg-anchor-full.yml",
        }:
            assert 'printf -v SHARD "%03d" "$SHARD_INDEX"' in content, name
            assert 'printf -v SHARD "%02d" "$SHARD_INDEX"' not in content, name
        assert "max-parallel: 4" not in content, name
        assert content.count("id: upload_shard") == 1, name
        assert content.count("id: retry_upload_shard") == 1, name
        assert content.count("name: Retry shard artifact upload") == 1, name
        assert content.count("name: Final shard artifact upload retry") == 1, name
        assert content.count("steps.upload_shard.outcome == 'failure'") == 1, name
        assert content.count(
            "steps.retry_upload_shard.outcome == 'failure'"
        ) == 1, name
        assert content.count("overwrite: true") == 2, name


def test_downstream_pricing_artifact_uploads_are_retry_safe():
    segment_workflows = (
        "phase1-pons-skhy-v3-weth-continuation.yml",
        "phase1-pons-skhy-v4-known-pool-continuation.yml",
    )
    for name in segment_workflows:
        content = _workflow(name)
        assert content.count("id: upload_segment") == 1, name
        assert content.count("id: retry_upload_segment") == 1, name
        assert content.count("steps.upload_segment.outcome == 'failure'") == 1, name
        assert content.count(
            "steps.retry_upload_segment.outcome == 'failure'"
        ) == 1, name
        assert content.count("overwrite: true") == 2, name
        assert content.count("id: download_input") == 1, name
        assert content.count("id: retry_download_input") == 1, name
        assert content.count(
            "steps.download_input.outcome == 'failure'"
        ) == 2, name
        assert content.count(
            "steps.retry_download_input.outcome == 'failure'"
        ) == 2, name
        assert content.count("rm -rf audit") + content.count("rm -rf prior") == 2, name

    segmented_workflows = (
        "phase1-pons-skhy-v3-weth-segmented.yml",
        "phase1-pons-skhy-v4-known-pool-segmented.yml",
    )
    for name in segmented_workflows:
        content = _workflow(name)
        assert content.count("id: upload_segmented") == 1, name
        assert content.count("id: retry_upload_segmented") == 1, name
        assert content.count(
            "steps.upload_segmented.outcome == 'failure'"
        ) == 1, name
        assert content.count(
            "steps.retry_upload_segmented.outcome == 'failure'"
        ) == 1, name
        assert content.count("overwrite: true") == 2, name
        assert content.count("id: download_segments") == 1, name
        assert content.count("id: retry_download_segments") == 1, name
        assert content.count(
            "steps.download_segments.outcome == 'failure'"
        ) == 2, name
        assert content.count(
            "steps.retry_download_segments.outcome == 'failure'"
        ) == 2, name
        assert content.count("rm -rf segments") == 2, name

    quote_workflows = (
        "phase1-pons-v3-quote-fallback-full.yml",
        "phase1-pons-v4-quote-fallback-full.yml",
    )
    for name in quote_workflows:
        content = _workflow(name)
        for upload_id in ("routes", "shard", "full"):
            assert content.count(f"id: upload_{upload_id}") == 1, (
                name,
                upload_id,
            )
            assert content.count(f"id: retry_upload_{upload_id}") == 1, (
                name,
                upload_id,
            )
            assert content.count(
                f"steps.upload_{upload_id}.outcome == 'failure'"
            ) == 1, (name, upload_id)
            assert content.count(
                f"steps.retry_upload_{upload_id}.outcome == 'failure'"
            ) == 1, (name, upload_id)
        assert content.count("overwrite: true") == 6, name
        for download_id in (
            "routes",
            "shards",
            "merge_routes",
        ):
            assert content.count(f"id: download_{download_id}") == 1, (
                name,
                download_id,
            )
            assert content.count(
                f"id: retry_download_{download_id}"
            ) == 1, (name, download_id)
            assert content.count(
                f"steps.download_{download_id}.outcome == 'failure'"
            ) == 2, (name, download_id)
            assert content.count(
                f"steps.retry_download_{download_id}.outcome == 'failure'"
            ) == 2, (name, download_id)
        assert content.count("rm -rf routes") == 4, name
        assert content.count("rm -rf downloads") == 2, name
        assert (
            "      - uses: actions/upload-artifact@v4\n"
            "      - uses: actions/upload-artifact@v4"
        ) not in content, name


def test_quote_fallback_recovery_plan_and_final_artifacts_are_retry_safe():
    for name in (
        "phase1-pons-v3-quote-fallback-recover-gaps.yml",
        "phase1-pons-v4-quote-fallback-recover-gaps.yml",
    ):
        content = _workflow(name)
        for output_id in ("plan", "full"):
            assert content.count(f"id: upload_{output_id}") == 1, (
                name,
                output_id,
            )
            assert content.count(
                f"id: retry_upload_{output_id}"
            ) == 1, (name, output_id)
            assert content.count(
                f"steps.upload_{output_id}.outcome == 'failure'"
            ) == 1, (name, output_id)
            assert content.count(
                f"steps.retry_upload_{output_id}.outcome == 'failure'"
            ) == 1, (name, output_id)


def test_generic_quote_fallback_artifact_handoff_is_retry_safe():
    content = _workflow("phase1-pons-quote-fallback-full.yml")
    for venue in ("v3", "v4"):
        assert content.count(f"id: download_{venue}") == 1, venue
        assert content.count(f"id: retry_download_{venue}") == 1, venue
        assert content.count(
            f"steps.download_{venue}.outcome == 'failure'"
        ) == 2, venue
        assert content.count(
            f"steps.retry_download_{venue}.outcome == 'failure'"
        ) == 2, venue
        assert content.count(f"rm -rf {venue}") == 2, venue
    assert content.count("id: upload_merged") == 1
    assert content.count("id: retry_upload_merged") == 1
    assert content.count(
        "steps.upload_merged.outcome == 'failure'"
    ) == 1
    assert content.count(
        "steps.retry_upload_merged.outcome == 'failure'"
    ) == 1
    assert content.count("overwrite: true") == 2


def test_lifecycle_artifact_handoffs_are_retry_safe():
    contracts = {
        "phase1-pons-v1-lifecycle-eligibility.yml": (
            "registry",
            "quotes",
            "anchor",
            "oracle",
        ),
        "phase1-pons-v2-lifecycle-eligibility.yml": (
            "registry",
            "curve",
            "transition",
            "anchor",
            "oracle",
            "fallback",
        ),
    }
    for name, inputs in contracts.items():
        content = _workflow(name)
        for input_id in inputs:
            assert content.count(f"id: download_{input_id}") == 1, (
                name,
                input_id,
            )
            assert content.count(
                f"id: retry_download_{input_id}"
            ) == 1, (name, input_id)
            assert content.count(
                f"steps.download_{input_id}.outcome == 'failure'"
            ) == 2, (name, input_id)
            assert content.count(
                f"steps.retry_download_{input_id}.outcome == 'failure'"
            ) == 2, (name, input_id)
            assert content.count(f"rm -rf {input_id}") == 2, (
                name,
                input_id,
            )
        assert content.count("id: upload_lifecycle") == 1, name
        assert content.count("id: retry_upload_lifecycle") == 1, name
        assert content.count(
            "steps.upload_lifecycle.outcome == 'failure'"
        ) == 1, name
        assert content.count(
            "steps.retry_upload_lifecycle.outcome == 'failure'"
        ) == 1, name
        assert content.count("overwrite: true") == 2, name


def test_representative_transfer_recovery_preserves_successful_work():
    content = _workflow("phase1-pons-representative-transfers-full.yml")

    assert content.count("id: download_sample") == 6
    assert content.count("id: retry_download_sample") == 6
    assert content.count(
        "steps.download_sample.outcome == 'failure'"
    ) == 12
    assert content.count(
        "steps.retry_download_sample.outcome == 'failure'"
    ) == 12
    assert content.count("rm -rf sample") == 12

    assert content.count("id: upload_plan") == 1
    assert content.count("id: retry_upload_plan") == 1
    assert content.count("steps.upload_plan.outcome == 'failure'") == 1
    assert content.count(
        "steps.retry_upload_plan.outcome == 'failure'"
    ) == 1

    assert content.count("id: upload_shard") == 4
    assert content.count("id: retry_upload_shard") == 4
    assert content.count(
        "steps.upload_shard.outcome == 'failure'"
    ) == 4
    assert content.count(
        "steps.retry_upload_shard.outcome == 'failure'"
    ) == 4

    assert content.count("id: download_plan") == 1
    assert content.count("id: retry_download_plan") == 1
    assert content.count(
        "steps.download_plan.outcome == 'failure'"
    ) == 2
    assert content.count(
        "steps.retry_download_plan.outcome == 'failure'"
    ) == 2
    assert content.count("rm -rf plan") == 2

    assert content.count("id: upload_full") == 1
    assert content.count("id: retry_upload_full") == 1
    assert content.count("steps.upload_full.outcome == 'failure'") == 1
    assert content.count(
        "steps.retry_upload_full.outcome == 'failure'"
    ) == 1
    assert content.count("overwrite: true") == 12
    assert content.count("TRANSIENT_METADATA_HTTP_CODES = {") == 2
    assert content.count("for retry_index in range(3):") == 2
    assert content.count(
        "representative transfer metadata retry loop exhausted"
    ) == 2
    assert content.count("import urllib.error") == 2
    assert content.count("select_equivalent_artifact_retry(") == 2
    assert content.count(
        "representative transfer retry artifacts"
    ) == 2
    assert "duplicate shard artifact indexes" not in content

    for prior in ("acquire_1", "acquire_2", "acquire_3"):
        assert content.count(
            f"needs.{prior}.result == 'failure'"
        ) == 1, prior

    merge_line = next(
        line
        for line in content.splitlines()
        if line.strip().startswith("if: ${{ always()")
        and "needs.acquire_4.result" in line
    )
    assert "result == 'failure'" not in merge_line


def test_representative_intermediate_outputs_are_retry_safe():
    workflows = (
        "phase1-pons-representative-sample-freeze.yml",
        "phase1-pons-representative-market-paths.yml",
        "phase1-pons-representative-priced-paths.yml",
        "phase1-pons-representative-dex-crosscheck.yml",
    )
    for name in workflows:
        content = _workflow(name)
        assert content.count("id: upload_output") == 1, name
        assert content.count("id: retry_upload_output") == 1, name
        assert content.count(
            "steps.upload_output.outcome == 'failure'"
        ) == 1, name
        assert content.count(
            "steps.retry_upload_output.outcome == 'failure'"
        ) == 1, name
        assert content.count("overwrite: true") == 2, name


    dex = _workflow("phase1-pons-representative-dex-crosscheck.yml")
    for source in (
        "sample",
        "v1",
        "v2",
        "priced_paths",
        "registry",
        "transition",
    ):
        assert dex.count(f"id: download_{source}") == 1, source
        assert dex.count(f"id: retry_download_{source}") == 1, source
        assert dex.count(
            f"steps.download_{source}.outcome == 'failure'"
        ) == 2, source
        assert dex.count(
            f"steps.retry_download_{source}.outcome == 'failure'"
        ) == 2, source


def test_post_viability_artifact_reads_retry_transient_failures():
    projection = _workflow(
        "phase1-pons-acquisition-viability-projection.yml"
    )
    assert projection.count("id: download_accounting") == 1
    assert projection.count("id: retry_download_accounting") == 1
    assert projection.count(
        "steps.download_accounting.outcome == 'failure'"
    ) == 2
    assert projection.count(
        "steps.retry_download_accounting.outcome == 'failure'"
    ) == 2
    assert projection.count("rm -rf accounting") == 2

    gate = _workflow("phase1-pons-acceptance-gate.yml")
    for source in ("eligible", "representative", "viability"):
        assert gate.count(f"id: download_{source}") == 1, source
        assert gate.count(f"id: retry_download_{source}") == 1, source
        assert gate.count(
            f"steps.download_{source}.outcome == 'failure'"
        ) == 2, source
        assert gate.count(
            f"steps.retry_download_{source}.outcome == 'failure'"
        ) == 2, source
        assert gate.count(f"rm -rf {source}") == 2, source

    closeout = _workflow("phase1-pons-pass-closeout-one-shot.yml")
    assert closeout.count("id: download_acceptance") == 1
    assert closeout.count("id: retry_download_acceptance") == 1
    assert closeout.count(
        "steps.download_acceptance.outcome == 'failure'"
    ) == 2
    assert closeout.count(
        "steps.retry_download_acceptance.outcome == 'failure'"
    ) == 2
    assert closeout.count("rm -rf acceptance") == 2

    final = _workflow("phase1-pons-final-acceptance-chain.yml")
    assert final.count("id: download_evidence_handoff") == 1
    assert final.count("id: retry_download_evidence_handoff") == 1
    assert final.count(
        "steps.download_evidence_handoff.outcome == 'failure'"
    ) == 2
    assert final.count(
        "steps.retry_download_evidence_handoff.outcome == 'failure'"
    ) == 2
    assert final.count("rm -rf evidence-handoff") == 2

    route_downloads = (
        "pons_registry_primary",
        "pons_registry_secondary",
        "pons_v1_v3",
        "pons_v2_curve",
        "pons_v2_transition",
        "pons_v2_v4",
        "weth_usdg_anchor",
        "stock_oracle",
        "quote_v3_fallback",
        "quote_v4_fallback",
    )
    for route in route_downloads:
        assert final.count(f"id: download_route_{route}") == 1, route
        assert final.count(
            f"id: retry_download_route_{route}"
        ) == 1, route
        assert final.count(
            f"steps.download_route_{route}.outcome == 'failure'"
        ) == 2, route
        assert final.count(
            f"steps.retry_download_route_{route}.outcome == 'failure'"
        ) == 2, route


def test_viability_route_measurement_is_manual_bounded_guarded_and_canonical():
    content = _workflow("phase1-pons-viability-route-measurement.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    for route in (
        "pons_registry",
        "pons_v1_v3",
        "pons_v2_curve",
        "pons_v2_transition",
        "pons_v2_v4",
        "weth_usdg_anchor",
        "stock_oracle",
        "quote_v3_fallback",
        "quote_v4_fallback",
    ):
        assert f"          - {route}" in content
    assert 'default: "54436036"' in content
    assert 'default: "54486035"' in content
    assert "viability measurement exceeds 50000-block ceiling" in content
    assert "hi - lo + 1 > 50_000" in content
    assert "Verify approved evidence before any viability RPC" in content
    assert "viability measurement evidence run ID must be positive" in content
    assert "viability measurement evidence run is not successful" in content
    assert "viability measurement evidence workflow path is not" in content
    assert "viability measurement evidence branch changed" in content
    assert "viability measurement evidence artifacts missing" in content
    assert "viability measurement evidence-ready retry " in content
    assert "artifacts are not equivalent" in content
    assert "evidence_artifact_id" in content
    assert (
        "artifact-ids: ${{ steps.evidence.outputs.evidence_artifact_id }}"
        in content
    )
    assert "Validate evidence handoff contents before viability RPC" in content
    assert "viability measurement evidence handoff is not ready" in content
    assert "viability measurement evidence handoff run mismatch" in content
    assert "viability measurement evidence handoff source mismatch" in content
    assert "viability measurement evidence representative count changed" in content
    assert "viability measurement evidence hash is invalid" in content
    assert "representative_sample_sha256" in content
    assert "representative_token_set_sha256" in content
    assert "representative_source_coverage_sha256" in content
    assert "viability measurement runner-smoke run changed" in content
    assert "viability measurement runner-smoke universe SHA changed" in content
    assert "viability measurement runner-smoke outcomes SHA changed" in content
    assert "phase1-pons-post-eligibility-evidence-ready" in content
    assert "phase1-pons-eligible-universe" in content
    assert "phase1-pons-representative-validation" in content
    assert content.count("needs: preflight") == 2
    assert "rpc-v1-registry-window" in content
    assert "rpc-v2-registry-window" in content
    assert "rpc-v3-pons-tape" in content
    assert "rpc-v2-curve-tape" in content
    assert "rpc-v2-transition-tape" in content
    assert "rpc-v2-v4-tape" in content
    assert "rpc-v1-price-path" in content
    assert "rpc-pons-stock-oracle-lifecycle" in content
    assert "rpc-v3-quote-route-tape" in content
    assert "rpc-v4-quote-route-tape" in content
    assert "registry_v2:" in content
    assert (
        "if: ${{ needs.preflight.result == 'success' && "
        "inputs.route == 'pons_registry' }}"
        in content
    )
    assert "shared measurement range must postdate V2 deployment" in content
    assert "phase1-pons-v3-quote-fallback-full" in content
    assert "phase1-pons-v4-quote-fallback-full" in content
    assert "quote fallback measurement requires fallback artifact run ID" in content
    assert "run-name: phase1 route ${{ inputs.route }} sequence=${{ inputs.sequence_id }}" in content
    assert 'sequence_id:' in content
    assert 'evidence_run_id:' in content
    assert 'source_eligibility_run_id:' in content
    assert '"measurement_run_id": int(' in content
    assert '"measurement_head_sha": os.environ["GITHUB_SHA"]' in content
    assert '"evidence_run_id": evidence_run_id' in content
    assert '"source_eligibility_run_id": source_run_id' in content
    assert '"fallback_artifact_run_id": fallback_run_id' in content
    assert '"registry_generation": (' in content
    assert '"v1" if route == "pons_registry" else None' in content
    assert '"registry_generation": "v2"' in content
    assert "pons_registry V2 measurement source run changed" in content
    assert "pons_registry V2 evidence run ID cannot be negative" in content
    assert content.count(
        '"measurement_run_id": int('
    ) >= 2
    assert content.count(
        '"measurement_head_sha": os.environ["GITHUB_SHA"]'
    ) >= 2
    assert "viability measurement source eligibility run changed" in content
    assert "viability measurement evidence run ID cannot be negative" in content
    assert '"sequence_id": os.environ.get("SEQUENCE_ID", "")' in content
    assert content.count("id: upload_primary") == 1
    assert content.count("id: retry_upload_primary") == 1
    assert content.count("steps.upload_primary.outcome == 'failure'") == 1
    assert content.count(
        "steps.retry_upload_primary.outcome == 'failure'"
    ) == 1
    assert content.count("id: upload_secondary") == 1
    assert content.count("id: retry_upload_secondary") == 1
    assert content.count("steps.upload_secondary.outcome == 'failure'") == 1
    assert content.count(
        "steps.retry_upload_secondary.outcome == 'failure'"
    ) == 1
    assert "timeout-minutes: 30" in content

def test_full_quote_audit_has_short_fail_fast_bound():
    content = _workflow("phase1-pons-full-quote-audit.yml")
    assert "timeout-minutes: 20" in content
    assert "timeout-minutes: 75" not in content



BACKFILL_WORKFLOWS = {
    "phase1-pons-full-registry.yml",
    "phase1-pons-full-census.yml",
    "phase1-pons-v1-registry-recovery.yml",
    "phase1-pons-v2-registry-freeze.yml",
    "phase1-pons-full-quote-audit.yml",
    "phase1-pons-v2-stock-oracle-full.yml",
    "phase1-pons-v2-curve-full.yml",
    "phase1-pons-v2-transition-full.yml",
    "phase1-pons-weth-usdg-anchor-full.yml",
    "phase1-pons-v2-v4-full.yml",
    "phase1-pons-v2-lifecycle-eligibility.yml",
    "phase1-pons-stock-oracle-full.yml",
    "phase1-pons-v1-v3-full.yml",
    "phase1-pons-v1-lifecycle-eligibility.yml",
    "phase1-pons-eligible-universe-freeze.yml",
    "phase1-pons-representative-sample-freeze.yml",
    "phase1-pons-v3-quote-fallback-full.yml",
    "phase1-pons-v4-quote-fallback-full.yml",
    "phase1-pons-quote-fallback-full.yml",
    "phase1-pons-v4-quote-continuation.yml",
    "phase1-pons-skhy-v3-weth-continuation.yml",
    "phase1-pons-skhy-v3-weth-segmented.yml",
    "phase1-pons-skhy-v4-known-pool-continuation.yml",
    "phase1-pons-skhy-v4-known-pool-segmented.yml",
    "phase1-pons-v2-curve-recover-tail-one-shot.yml",
    "phase1-pons-weth-usdg-anchor-recover-tail-one-shot.yml",
    "phase1-pons-v2-transition-recover-gaps.yml",
    "phase1-pons-v2-v4-recover-gaps.yml",
    "phase1-pons-v1-v3-recover-gaps.yml",
    "phase1-pons-v3-quote-fallback-recover-gaps.yml",
    "phase1-pons-v4-quote-fallback-recover-gaps.yml",
    "phase1-pons-stock-oracle-promote-v2-delta.yml",
    "phase1-pons-representative-transfers-full.yml",
    "phase1-pons-representative-evidence-chain.yml",
    "phase1-pons-viability-route-measurement.yml",
}


def test_full_history_backfills_are_manual_only():
    for name in BACKFILL_WORKFLOWS:
        content = _workflow(name)
        trigger_block = content.split("\npermissions:", 1)[0]
        assert "workflow_dispatch:" in trigger_block, name
        assert "\n  push:" not in trigger_block, (
            f"{name} must not auto-start a full-history backfill on code pushes"
        )



NETWORK_SMOKE_WORKFLOWS = {
    "phase1-network-smoke.yml",
    "phase1-hoodfun-curve-mcap-smoke.yml",
    "phase1-v1-usd-path-smoke.yml",
    "phase1-v2-full-priced-smoke.yml",
    "phase1-pons-research-smoke.yml",
    "phase1-v2-shared-curve-smoke.yml",
    "phase1-v2-graduation-v4-smoke.yml",
    "phase1-dex-pool-census.yml",
    "phase1-pons-v1-multigen-smoke.yml",
    "phase1-v1-shared-tape-smoke.yml",
    "phase1-pons-representative-dex-crosscheck.yml",
    "phase1-blockscout-transaction-smoke.yml",
    "phase1-blockscout-v2-smoke.yml",
    "phase1-pons-v2-v4-filter-comparison.yml",
}


def test_secondary_network_smokes_are_manual_only():
    for name in NETWORK_SMOKE_WORKFLOWS:
        content = _workflow(name)
        trigger_block = content.split("\npermissions:", 1)[0]
        assert "workflow_dispatch:" in trigger_block, name
        assert "\n  push:" not in trigger_block, (
            f"{name} must not consume RPC runners on ordinary pushes"
        )



def test_blockscout_transaction_smoke_is_bounded_and_identity_checked():
    content = _workflow("phase1-blockscout-transaction-smoke.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "MAX_BLOCK_LOOKBACK = 20" in content
    assert "https://rpc.mainnet.chain.robinhood.com" in content
    assert 'rpc("eth_chainId", [])' in content
    assert "int(chain_id, 16) != 4663" in content
    assert "/api/v2/transactions/" in content
    assert "blockscout_reachable" in content
    assert "transaction_identity_match" in content
    assert "Blockscout transaction hash does not match Robinhood RPC" in content
    assert "Blockscout transaction block does not match Robinhood RPC" in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "time.sleep(" not in content


def test_v2_v4_filter_comparison_is_manual_bounded_and_guarded():
    content = _workflow("phase1-pons-v2-v4-filter-comparison.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "\n  workflow_call:" not in trigger_block
    assert "confirm_comparison" in content
    assert "V2/V4 filter comparison exceeds 5000-block ceiling" in content
    assert "blocked while a live venue " in content
    assert "rescue is active" in content
    assert "phase1-pons-live-venue-rescue-one-shot.yml" in content
    assert 'TRANSITION_RUN_ID: \'33912452330\'' in content
    assert content.count("rpc-v2-v4-tape") == 2
    assert content.count("--global-pool-scan") == 1
    assert content.count("--chunk-size 2000") == 2
    assert '"request_bytes_sent"' in content
    assert '"response_bytes_received"' in content
    assert '"exact_data_match": exact_match' in content
    assert '"server_side_unsupported"' in content
    assert '"equivalent"' in content
    assert '"mismatch"' in content
    assert "digest(global_data) == digest(server_data)" in content
    assert "if: ${{ always() }}" in content
    assert "Fail closed on canonical mismatch" in content
    assert "time.sleep(" not in content


def test_venue_terminal_snapshot_binding_schema_matches_launcher():
    launcher = _workflow("phase1-pons-live-venue-rescue-one-shot.yml")
    recoveries = (
        _workflow("phase1-pons-v1-v3-recover-gaps.yml"),
        _workflow("phase1-pons-v2-v4-recover-gaps.yml"),
    )

    def binding_keys(content, marker):
        lines = content.splitlines()
        start = next(
            index
            for index, line in enumerate(lines)
            if marker in line
        )
        keys = []
        for line in lines[start + 1 :]:
            stripped = line.strip()
            if stripped == "}":
                break
            if stripped.startswith('"') and '":' in stripped:
                keys.append(stripped.split('":', 1)[0].strip('"'))
        return keys

    expected = [
        "run_id",
        "status",
        "conclusion",
        "head_sha",
        "display_title",
        "run_attempt",
        "reusable_gap_ids",
        "missing_success_artifacts",
        "non_success_gap_artifacts",
        "plan_artifact_present",
        "canonical_artifact_present",
    ]
    assert binding_keys(
        launcher,
        "prior_terminal_binding = {",
    ) == expected

    for recovery in recoveries:
        assert "build_rescue_terminal_binding" in recovery
        assert "rescue_terminal_binding_sha256" in recovery
        assert "terminal_binding = build_rescue_terminal_binding(" in recovery
        for key in expected:
            assert f"{key}=" in recovery
        assert "observed_snapshot_sha256 = (" in recovery
        assert "rescue_terminal_binding_sha256(" in recovery
        coverage = recovery.split(
            "Discover reusable prior ",
            1,
        )[1].split("- id: plan", 1)[0]
        assert "hashlib.sha256(" not in coverage
        assert 'separators=(",", ":")' not in coverage

    assert "prior_terminal_snapshot_sha256 = hashlib.sha256(" in launcher
    assert "sort_keys=True" in launcher
    assert 'separators=(",", ":")' in launcher


def test_v2_eligibility_fails_fast_on_uncovered_quote_assets():
    content = _workflow("phase1-pons-v2-lifecycle-eligibility.yml")
    assert "if uncovered:" in content
    assert "cannot replay V2 lifecycle with uncovered quote assets" in content
    assert '"owned_quote_assets": 30' in content
    assert '"v3_routes": 26' in content
    assert '"v4_routes": 4' in content
    assert '"v3_v4_overlap_assets": 0' in content
    assert "generic quote fallback ownership contract changed" in content



def test_curve_range_recovery_is_manual_small_and_bounded():
    content = _workflow("phase1-pons-v2-curve-recover-range.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "max-parallel: 2" in content
    assert "SHARD_COUNT: '4'" in content
    assert "recovery range exceeds 200000-block ceiling" in content
    assert "timeout-minutes: 20" in content
    assert content.count("id: upload_range_shard") == 1
    assert content.count("id: retry_upload_range_shard") == 1
    assert content.count("name: Retry range shard artifact upload") == 1
    assert content.count("name: Final range shard artifact upload retry") == 1
    assert content.count("steps.upload_range_shard.outcome == 'failure'") == 1
    assert (
        content.count("steps.retry_upload_range_shard.outcome == 'failure'") == 1
    )
    assert content.count("overwrite: true") == 2
    assert "time.sleep(" not in content



def test_anchor_range_recovery_is_manual_small_and_bounded():
    content = _workflow("phase1-pons-weth-usdg-anchor-recover-range.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "artifact_suffix" in content
    assert "phase1-pons-anchor-range-${{ inputs.artifact_suffix }}-" in content
    assert (
        "phase1-pons-anchor-recovered-range-${{ inputs.artifact_suffix }}"
        in content
    )
    assert "max-parallel: 2" in content
    assert "SHARD_COUNT: '4'" in content
    assert "recovery range exceeds 200000-block ceiling" in content
    assert "timeout-minutes: 20" in content
    assert content.count("id: upload_range_shard") == 1
    assert content.count("id: retry_upload_range_shard") == 1
    assert content.count("name: Retry range shard artifact upload") == 1
    assert content.count("name: Final range shard artifact upload retry") == 1
    assert content.count("steps.upload_range_shard.outcome == 'failure'") == 1
    assert (
        content.count("steps.retry_upload_range_shard.outcome == 'failure'") == 1
    )
    assert content.count("overwrite: true") == 2
    assert "time.sleep(" not in content



def test_cancelled_anchor_gap_repair_is_manual_sequential_and_exact():
    content = _workflow(
        "phase1-pons-weth-usdg-anchor-cancelled-gap-repair.yml"
    )
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "confirm_repair" in content
    assert 'from_block: "52169619"' in content
    assert 'to_block: "52319618"' in content
    assert 'artifact_suffix: "gap-018"' in content
    assert 'from_block: "53219619"' in content
    assert 'to_block: "53369618"' in content
    assert 'artifact_suffix: "gap-025"' in content
    assert "needs: repair_018" in content
    assert "needs.repair_018.result == 'success'" in content
    assert (
        "./.github/workflows/"
        "phase1-pons-weth-usdg-anchor-recover-range.yml"
        in content
    )


def test_anchor_recovered_promotion_is_manual_exact_and_streaming():
    content = _workflow(
        "phase1-pons-weth-usdg-anchor-promote-recovered.yml"
    )
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert 'default: "33912536839"' in content
    assert 'default: "33925648293"' in content
    assert 'default: "33957294304"' in content
    assert 'default: "33970898635"' in content
    assert "phase1-pons-anchor-recovered-range-*" in content
    assert "select_anchor_source_ranges" in content
    assert '"preserved": 14' in content
    assert '"partial_recovery": 1' in content
    assert '"gap_recovery": 32' in content
    assert '"range_repair": 2' in content
    assert "(52_169_619, 52_319_618)" in content
    assert "(53_219_619, 53_369_618)" in content
    assert "promoted_recovered_weth_usdg_anchor" in content
    assert "pons-weth-usdg-anchor-full.jsonl" in content
    assert "pons-weth-usdg-anchor-initial.json" in content
    assert "pons-weth-usdg-anchor-summary.json" in content
    assert "no_unexplained_block_gaps" in content
    assert "state_rpc_response_bytes" in content
    assert "state_rpc_route" in content
    assert "rows = []" not in content
    assert "time.sleep(" not in content


def test_curve_gap_recovery_is_manual_gap_aware_and_bounded():
    content = _workflow("phase1-pons-v2-curve-recover-gaps.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "plan_missing_subranges" in content
    assert "prior_gap_run_id" in content
    assert 'Path("prior-gaps").glob("curve-gap-*.jsonl")' in content
    assert '"source": path.parent.name' in content
    assert 'default: "50000"' in content
    assert "max_gap_blocks must be between 1 and 50000" in content
    assert "V2 curve gap plan exceeds 240 matrix jobs" in content
    assert "max-parallel: 2" in content
    assert "timeout-minutes: 20" in content
    assert "matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}" in content
    assert "time.sleep(" not in content



def test_anchor_gap_recovery_is_manual_gap_aware_and_bounded():
    content = _workflow("phase1-pons-weth-usdg-anchor-recover-gaps.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "plan_missing_subranges" in content
    assert "prior_gap_run_id" in content
    assert "prior_gap_run_id_2" in content
    assert 'Path("prior-gaps").glob("anchor-gap-*.jsonl")' in content
    assert 'Path("prior-gaps-2").glob("anchor-gap-*.jsonl")' in content
    assert '"source": path.parent.name' in content
    assert 'default: "50000"' in content
    assert "max_gap_blocks must be between 1 and 50000" in content
    assert "anchor gap plan exceeds 240 matrix jobs" in content
    assert "max-parallel: 2" in content
    assert "timeout-minutes: 20" in content
    assert "matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}" in content
    assert "time.sleep(" not in content



def test_transition_gap_recovery_is_manual_gap_aware_and_bounded():
    content = _workflow("phase1-pons-v2-transition-recover-gaps.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "plan_missing_subranges" in content
    assert "prior_gap_run_id" in content
    assert "graduations-gap" in content
    assert "registrations-gap" in content
    assert "transition artifact families disagree" in content
    assert "manifest_gap_aware_transition_recovery" in content
    assert 'default: "150000"' in content
    assert "max_gap_blocks must be between 1 and 150000" in content
    assert "transition gap plan exceeds 240 matrix jobs" in content
    assert "max-parallel: 2" in content
    assert "timeout-minutes: 20" in content
    assert "matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}" in content
    assert "time.sleep(" not in content


def test_single_wave_gap_recoveries_retry_transient_artifact_uploads():
    workflows = (
        "phase1-pons-v2-curve-recover-gaps.yml",
        "phase1-pons-weth-usdg-anchor-recover-gaps.yml",
        "phase1-pons-v2-transition-recover-gaps.yml",
        "phase1-pons-v3-quote-fallback-recover-gaps.yml",
        "phase1-pons-v4-quote-fallback-recover-gaps.yml",
    )
    for name in workflows:
        content = _workflow(name)
        assert content.count("id: upload_gap") == 1, name
        assert content.count("id: retry_upload_gap") == 1, name
        assert content.count("name: Retry gap artifact upload") == 1, name
        assert content.count("name: Final gap artifact upload retry") == 1, name
        assert content.count("steps.upload_gap.outcome == 'failure'") == 1, name
        assert (
            content.count("steps.retry_upload_gap.outcome == 'failure'") == 1
        ), name
        expected_overwrites = (
            6 if "quote-fallback" in name else 2
        )
        assert content.count("overwrite: true") == expected_overwrites, name


def test_v4_gap_recovery_is_manual_gap_aware_and_bounded():
    content = _workflow("phase1-pons-v2-v4-recover-gaps.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "plan_missing_subranges" in content
    assert "coalesce_covered_ranges" in content
    assert "select_contiguous_cover" in content
    assert "candidate_source_files" in content
    assert "dropped_overlapping_source_files" in content
    assert 'manifest.get("path") == path.name' in content
    assert 'with path.open("rb") as handle:' in content
    assert "local_digest = hashlib.sha256()" in content
    assert content.count("import hashlib") == 4
    merge_block = content.split(
        "- name: Merge recovered V4 event tape",
        1,
    )[1].split("- uses: actions/upload-artifact@v4", 1)[0]
    assert "import hashlib" in merge_block
    assert "digest = hashlib.sha256()" in merge_block
    assert 'local_digest.hexdigest() == manifest["sha256"]' in content
    assert "prior_gap_run_id" in content
    lineage_block = content.split(
        "def plan_for(run_id):",
        1,
    )[1].split("seen = set()", 1)[0]
    assert 'run.get("status") != "completed"' in lineage_block
    assert 'run.get("conclusion")' not in lineage_block
    assert "v4-events-gap" in content
    assert "manifest_gap_aware_v4_recovery" in content
    assert content.count("--global-pool-scan") == 4
    assert "server_side_topic1_registered_pool_ids" not in content
    assert 'default: "50000"' in content
    assert "max_gap_blocks must be between 1 and 100000" in content
    assert "V4 gap plan exceeds four serialized 240-job waves" in content
    assert content.count("id: upload_gap") == 4
    assert content.count("id: retry_upload_gap") == 4
    assert content.count("name: Retry gap artifact upload") == 4
    assert content.count("name: Final gap artifact upload retry") == 4
    assert content.count("steps.upload_gap.outcome == 'failure'") == 4
    assert content.count("steps.retry_upload_gap.outcome == 'failure'") == 4
    assert content.count("overwrite: true") == 12
    assert content.count("continue-on-error: true") >= 17
    assert content.count("fetch_github_actions_json(") == 7
    assert "urllib.request.urlopen" not in content
    assert content.count("id: download_transition") == 5
    assert content.count("id: retry_download_transition") == 5
    assert content.count(
        "steps.download_transition.outcome == 'failure'"
    ) == 10
    assert content.count(
        "steps.retry_download_transition.outcome == 'failure'"
    ) == 10
    assert content.count("rm -rf transition") == 10
    assert content.count("id: upload_plan") == 1
    assert content.count("id: retry_upload_plan") == 1
    assert content.count(
        "name: Retry V2/V4 gap-plan artifact upload"
    ) == 1
    assert content.count(
        "name: Final V2/V4 gap-plan artifact upload retry"
    ) == 1
    assert content.count("steps.upload_plan.outcome == 'failure'") == 1
    assert content.count(
        "steps.retry_upload_plan.outcome == 'failure'"
    ) == 1
    plan_upload_block = content.split(
        "id: upload_plan",
        1,
    )[1].split("  recover_1:", 1)[0]
    assert plan_upload_block.count("overwrite: true") == 2
    assert content.count("id: upload_full") == 1
    assert content.count("id: retry_upload_full") == 1
    assert content.count("name: Retry canonical V2/V4 artifact upload") == 1
    assert content.count(
        "name: Final canonical V2/V4 artifact upload retry"
    ) == 1
    assert content.count("steps.upload_full.outcome == 'failure'") == 1
    assert content.count(
        "steps.retry_upload_full.outcome == 'failure'"
    ) == 1
    canonical_upload_block = content.split(
        "id: upload_full",
        1,
    )[1]
    assert canonical_upload_block.count("overwrite: true") == 2
    assert "frozen parent recovery is blocked while source is active" in content
    assert "Verify frozen V2 transition input" in content
    assert "V2 transition run ID changed: " in content
    assert "V2 transition run is not successful" in content
    assert "V2 transition workflow path changed" in content
    assert "V2 transition branch changed" in content
    assert "V2 transition launch commit changed" in content
    assert "V2 transition artifact identity is ambiguous" in content
    assert "V2 transition manifest identity is ambiguous" in content
    assert "V2 transition manifest changed: " in content
    assert "V2 transition data identity is ambiguous" in content
    assert "actual_digest = hashlib.sha256()" in content
    assert "actual_records = 0" in content
    assert 'checks["actual_sha256"]' in content
    assert 'checks["actual_records"]' in content
    assert '"actual_sha256": actual_digest.hexdigest()' in content
    assert '"actual_records": actual_records' in content
    assert "33912452330" in content
    assert "phase1-pons-v2-transition-full.yml" in content
    assert "7ce5eac5c1980e8618173e1a8ff0effb06ecb327" in content
    assert "pons-v2-registrations-full.jsonl.manifest.json" in content
    assert "8cc55b761e10c8643a907389602ca5f7790bd7df99cee2d00fbe120a9cd40e93" in content
    assert "3_638" in content
    assert content.count("Download every original V2/V4 shard artifact") == 1
    assert content.count("Discover original V2/V4 shard coverage") == 1
    assert "indexed_shard_bounds" in content
    assert "source-metadata/v2-v4-original-shards.json" in content
    assert '"planning_source_bytes_downloaded": 0' in content
    assert "acquire / v2_v4" in content
    assert "acquire / v2_v4_recovery" in content
    assert "V2/V4 source job pagination exceeded 1000" in content
    assert "V2/V4 empty source is not proven by skipped " in content
    assert "source-metadata/v2-v4-empty-source-proof.json" in content
    assert '"empty_source_proven": empty_source_proof is not None' in content
    assert "V2/V4 recovery has no source coverage and no " in content
    assert "V2/V4 empty-source proof run ID changed" in content
    assert "V2/V4 empty-source proof job states changed" in content
    assert "V2/V4 merge source job pagination exceeded 1000" in content
    assert "V2/V4 merge empty source is not proven by skipped " in content
    assert '"empty_source_proven": empty_source_proven' in content
    assert content.count('"empty_source_proven"') >= 2
    assert "Discover reusable prior V2/V4 gap coverage" in content
    assert "source-metadata/v2-v4-prior-gap-coverage.json" in content
    assert "source-metadata/v2-v4-prior-gap-generations.json" in content
    assert '"planned_ranges": [' in content
    assert '"gap_blocks": int(plan["gap_blocks"])' in content
    assert '"gap_wave_job_counts": [' in content
    assert '"successful_sources": list(' in content
    assert "split_range" in content
    assert "immediate_prior_id == 34_234_471_190" in content
    assert "expected_generation_2_ranges = split_range(" in content
    assert "max_blocks=50_000" in content
    assert "V2/V4 generation 2 prior lineage changed" in content
    assert "V2/V4 generation 2 successful source set changed" in content
    assert "V2/V4 generation 2 max gap size changed" in content
    assert "V2/V4 generation 2 planned job count changed" in content
    assert "V2/V4 generation 2 planned block count changed" in content
    assert "V2/V4 generation 2 wave shape changed" in content
    assert "V2/V4 generation 2 deterministic plan changed" in content
    assert "V2/V4 generation 2 gap 053 bounds changed" in content
    assert "29_491_846" in content
    assert "29_541_845" in content
    assert '"generation_2_plan_fingerprint_valid": (' in content
    assert '"reusable_ranges": [' in content
    assert '"successful_jobs_missing_artifacts"' in content
    assert '"non_success_gap_artifacts"' in content
    assert "V2/V4 immediate prior generation metadata " in content
    assert "expected_retry_cover = coalesce_covered_ranges(" in content
    assert "observed_retry_cover = coalesce_covered_ranges(" in content
    assert "V2/V4 retry ranges do not exactly reconstruct " in content
    assert "V2/V4 retry job accounting changed under " in content
    assert '"exact_range_reconstruction": True' in content
    assert '"prior_retry_accounting": prior_retry_accounting' in content
    assert "V2/V4 retry planner" in content
    assert "planned retry jobs:" in content
    assert "retry waves:" in content
    assert "prior planned gaps:" in content
    assert "reusable prior gaps:" in content
    assert "launcher expected reusable gaps:" in content
    assert "exact prior-plan reconstruction:" in content
    assert "expected_prior_reusable_gap_count" in content
    assert "EXPECTED_PRIOR_REUSABLE_GAP_COUNT" in content
    assert "expected_prior_terminal_snapshot_sha256" in content
    assert "EXPECTED_PRIOR_TERMINAL_SNAPSHOT_SHA256" in content
    assert "V2/V4 expected prior terminal snapshot SHA-256 " in content
    assert "V2/V4 generation 3 requires launcher-pinned " in content
    assert "terminal_binding = build_rescue_terminal_binding(" in content
    assert "rescue_terminal_binding_sha256(" in content
    assert "observed_snapshot_sha256 = hashlib.sha256(" not in content
    assert "V2/V4 launcher/child prior terminal " in content
    assert '"terminal_snapshot_sha256": (' in content
    assert "V2/V4 launcher/planner reusable prior-gap " in content
    assert "expected_prior_reusable_count = None" in content
    assert "V2/V4 expected reusable prior-gap count " in content
    assert "immediate_prior_id == 34_234_471_190" in content
    assert "V2/V4 generation 3 requires launcher-pinned " in content
    assert "launcher_expected_reusable_gap_count" in content
    assert "V2/V4 launcher expected prior reusable gaps " in content
    assert '"planning_prior_gap_jsonl_bytes_downloaded": 0' in content
    prior_coverage_block = content.split(
        "Discover reusable prior V2/V4 gap coverage",
        1,
    )[1].split("- id: plan", 1)[0]
    assert "for gap_id, row in observed.items():" in prior_coverage_block
    assert "if gap_id not in planned:" in prior_coverage_block
    assert "successful_repair_gap_ids" in prior_coverage_block
    assert 'str(row.get("conclusion") or "") == "success"' in prior_coverage_block
    assert "successful_gap_ids = successful_repair_gap_ids(cursor)" in prior_coverage_block
    assert "if gap_id not in successful_gap_ids:" in prior_coverage_block
    assert "ignored_non_success_artifacts += 1" in prior_coverage_block
    assert (
        prior_coverage_block.index("if gap_id not in planned:")
        < prior_coverage_block.index("if gap_id not in successful_gap_ids:")
    )
    assert "len(observed) != len(planned)" not in prior_coverage_block
    assert "len(observed) == len(planned)" not in prior_coverage_block
    assert content.count(
        r'gap_pattern = re.compile(r"^phase1-pons-v2-v4-gap-(\d+)$")'
    ) == 1
    assert (
        r'gap_pattern = re.compile(r"^phase1-pons-v2-v4-gap-(\\d+)$")'
        not in content
    )
    assert "V2/V4 source artifact pagination exceeded 2000" in content
    assert content.count(
        r'name_pattern = re.compile(r"^phase1-pons-v2-v4-(\d+)$")'
    ) == 2
    assert (
        r'name_pattern = re.compile(r"^phase1-pons-v2-v4-(\\d+)$")'
        not in content
    )
    assert "original_shard_artifacts" in content
    assert "duplicate V2/V4 shard file while downloading" in content
    assert "Download recursive paginated V2/V4 gap artifacts" in content
    assert "V2/V4 merge gap artifact pagination " in content
    assert "select_equivalent_artifact_retry" in content
    assert content.count("select_equivalent_artifact_retry(") >= 5
    assert "prior gap coverage duplicate retry artifacts " in content
    assert "are not equivalent" in content
    assert "collapsed_equivalent_retry_artifacts" in content
    assert "V2/V4 merge duplicate retry artifacts " in content
    assert "V2/V4 merge prior gap lineage contains a cycle" in content
    assert "V2/V4 merge prior gap lineage exceeds 20 generations" in content
    assert "prior recovery plan retry artifacts are not " in content
    assert "prior gap coverage plan retry artifacts are not " in content
    assert "V2/V4 merge prior plan retry artifacts are not " in content
    assert "V2/V4 merge prior gap plan file identity " in content
    assert "V2/V4 merge prior gap partial source changed" in content
    assert "V2/V4 merge prior gap snapshot head changed" in content
    assert "V2/V4 merge prior gap start block changed" in content
    assert "V2/V4 merge prior gap artifact is not bound " in content
    assert "V2/V4 merge prior gap job pagination " in content
    assert content.count("def successful_repair_gap_ids(") == 2
    assert content.count(
        "successful_gap_ids = successful_repair_gap_ids(cursor)"
    ) == 2
    assert content.count(
        'str(row.get("conclusion") or "") == "success"'
    ) == 2
    assert "ignored_gap_ids = [" in content
    assert "if gap_id not in successful_gap_ids" in content
    assert "prior_ignored_non_success_artifacts" in content
    assert 'Path("prior-gaps") / str(cursor)' in content
    assert 'Path("prior-gaps").rglob("v4-events-gap-*.jsonl")' in content
    assert "current V2/V4 gap artifact count does not match " in content
    assert "duplicate V2/V4 gap file while " in content
    assert "V2/V4 merge gap artifact is not bound " in content
    assert "V2/V4 merge gap manifest identity " in content
    assert "V2/V4 merge gap manifest range " in content
    assert "V2/V4 merge gap source changed: " in content
    assert "V2/V4 merge gap chain changed: " in content
    assert "V2/V4 merge gap protocol changed: " in content
    assert "V2/V4 merge gap frozen input changed: " in content
    assert "V2/V4 merge gap filter mode changed: " in content
    assert '"source") or "") != "evm_json_rpc"' in content
    assert 'provenance.get("chain_id", -1)' in content
    assert "pons_v2_v4_price_events" in content
    assert 'provenance.get("registrations")' in content
    assert "pons-v2-registrations-full.jsonl" in content
    assert "global_poolmanager_topic_then_registry" in content
    assert "observed_bounds != expected_bounds" in content
    assert "V2/V4 merge current plan retry artifacts are not " in content
    assert "V2/V4 merge current gap plan file identity " in content
    assert "current_plan_bytes = archive.read(" in content
    assert '(Path("plan") / plan_name).write_bytes(current_plan_bytes)' in content
    assert "name: phase1-pons-v2-v4-gap-plan\n          path: plan" not in content
    assert "V2/V4 merge current gap partial source changed" in content
    assert "V2/V4 merge current gap snapshot head changed" in content
    assert "V2/V4 merge current gap start block changed" in content
    assert "V2/V4 merge current gap prior lineage changed" in content
    assert "current V2/V4 gap artifact IDs do not match " in content
    assert content.count("validate_gap_plan_jobs(") == 4
    assert "prior gap coverage plan structure changed: " in content
    assert "V2/V4 generated gap plan is invalid: " in content
    assert "V2/V4 merge prior gap plan structure changed: " in content
    assert "V2/V4 merge current gap plan structure changed: " in content
    assert "CURRENT_GAP_COUNT: ${{ needs.plan.outputs.gap_count }}" in content
    assert "CURRENT_RUN_ID: ${{ github.run_id }}" in content
    assert "pattern: phase1-pons-v2-v4-gap-*" not in content
    assert "pattern: phase1-pons-v2-v4-*" not in content
    assert content.count("fetch_github_actions_artifact_zip(") == 5
    assert "decode_json=False" not in content
    assert "Verify recursive prior recovery lineage" in content
    assert "prior recovery plan lacks bound lineage metadata" in content
    assert "prior recovery partial run does not match current" in content
    assert "prior recovery lineage contains a cycle" in content
    assert '"partial_run_id": int("${{ inputs.partial_run_id }}")' in content
    assert '"prior_gap_run_id": (' in content
    assert "phase1-pons-full-eligibility-acquisition-one-shot.yml" in content
    assert "c53b3a63156976a5873752c332fa7578011249b0" in content
    assert content.count("max-parallel: 2") == 4
    assert content.count("timeout-minutes: 30") == 4
    assert content.count("timeout-minutes: 45") == 1
    assert content.count("timeout-minutes: 90") == 1
    for index in range(1, 5):
        assert (
            "matrix_"
            + str(index)
            + ": ${{ steps.plan.outputs.matrix_"
            + str(index)
            + " }}"
            in content
        )
        assert (
            "matrix: ${{ fromJSON(needs.plan.outputs.matrix_"
            + str(index)
            + ") }}"
            in content
        )
        assert f"gap_count_{index}" in content
    assert "gap_wave_job_counts" in content
    assert "needs: [plan, recover_1]" in content
    assert "needs: [plan, recover_2]" in content
    assert "needs: [plan, recover_3]" in content
    assert "needs: [plan, recover_1, recover_2, recover_3, recover_4]" in content
    for index in range(1, 4):
        assert (
            f"needs.recover_{index}.result == 'failure'"
            in content
        )
    merge_gate = content.split(
        "  merge:",
        1,
    )[1].split("    runs-on:", 1)[0]
    assert "result == 'failure'" not in merge_gate
    assert "time.sleep(" not in content


def test_stock_oracle_delta_promotion_is_manual_bounded_and_fail_closed():
    content = _workflow("phase1-pons-stock-oracle-promote-v2-delta.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "MAX_DELTA_BLOCKS: '100000'" in content
    assert "prior_delta_run_id" in content
    assert "plan_missing_subranges" in content
    assert "prior_successful_ranges" in content
    assert "gap_count" in content
    assert "oracle delta plan exceeds 240 matrix jobs" in content
    assert "matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}" in content
    assert "max-parallel: 2" in content
    assert "timeout-minutes: 20" in content
    assert "expected_full={len(expected_rows)}" in content
    assert "existing_v2={len(existing_tokens)}" in content
    assert "expected exactly one full-Pons stock-feed delta" in content
    assert "promoted_v2_oracle_plus_full_pons_delta" in content
    assert "promoted oracle does not exactly cover full-Pons stock feeds" in content
    assert "time.sleep(" not in content


def test_v4_quote_fallback_uses_cumulative_forward_probe():
    content = _workflow("phase1-pons-v4-quote-fallback-full.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert 'default: "33926428274"' in content
    assert 'default: "phase1-pons-residual-v4-forward-probe"' in content
    assert 'default: "pons-residual-v4-forward-probe.jsonl"' in content
    assert "select_v4_quote_routes" in content
    assert "phase1-pons-v3-quote-fallback-full" in content
    assert "v3_run_id" in content
    assert "skhy_v4_run_id" in content
    assert "phase1-pons-skhy-v4-known-pool-segmented" in content
    assert "25-route V3 fallback requires resolved SKHY V4" in content
    assert "V4 fallback must select four or five unique routes" in content
    assert "SKHY must be owned by exactly one of canonical V3 or V4" in content
    assert '"ownership_mode": ownership_mode' in content
    assert "externally_resolved_assets" in content
    assert "residual_quote_assets" in content
    assert (
        "- uses: actions/upload-artifact@v4\n"
        "      - uses: actions/upload-artifact@v4"
    ) not in content
    assert "SHARD_COUNT: '128'" in content
    assert 'printf -v SHARD "%03d" "$SHARD_INDEX"' in content
    assert "max-parallel: 2" in content


def test_v3_quote_fallback_is_reusable_with_frozen_route_runs():
    content = _workflow("phase1-pons-v3-quote-fallback-full.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert 'default: "33921477647"' in content
    assert 'default: "33923160281"' in content
    assert "pons-select-v3-quote-routes" in content
    assert "phase1-pons-skhy-v3-weth-segmented" in content
    assert "phase1-pons-weth-usdg-anchor-full" in content
    assert "skhy_weth_run_id" in content
    assert "anchor_run_id" in content
    assert "merge_v3_quote_routes" in content
    assert "searched_to_snapshot_head" in content
    assert "canonical V3 fallback must select 25 or 26 unique routes" in content
    assert "SKHY must be owned by exactly one of V3 or the residual set" in content
    assert "causal_v3_routes_with_optional_delayed_skhy_weth" in content
    assert "--anchor-initial anchor/pons-weth-usdg-anchor-initial.json" in content
    assert "--anchor-events anchor/pons-weth-usdg-anchor-full.jsonl" in content
    assert "SHARD_COUNT: '128'" in content
    assert 'printf -v SHARD "%03d" "$SHARD_INDEX"' in content
    assert "max-parallel: 2" in content


def test_generic_quote_fallback_owns_exact_26_v3_plus_4_v4():
    content = _workflow("phase1-pons-quote-fallback-full.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "phase1-pons-v3-quote-fallback-full" in content
    assert "phase1-pons-v4-quote-fallback-full" in content
    assert "generic fallback requires exact 26/4 or 25/5 V3/V4" in content
    assert "generic fallback requires exactly one SKHY venue owner" in content
    assert "26/4 generic fallback requires SKHY ownership in V3" in content
    assert "25/5 generic fallback requires SKHY ownership in V4" in content
    assert "V3/V4 fallback ownership overlaps" in content
    assert "route ownership and merged quote/USD ownership disagree" in content
    assert "merged quote fallback must own exactly 30 feedless quote" in content


def test_v4_quote_gap_recovery_is_manual_gap_aware_and_bounded():
    content = _workflow("phase1-pons-v4-quote-fallback-recover-gaps.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "plan_missing_subranges" in content
    assert "prior_gap_run_id" in content
    assert "v4-quote-events-gap" in content
    assert "manifest_gap_aware_v4_quote_recovery" in content
    assert "activation_by_pool" in content
    assert 'int(row["block_number"]) >= (' in content
    assert 'default: "100000"' in content
    assert "max_gap_blocks must be between 1 and 100000" in content
    assert "V4 quote gap plan exceeds 240 matrix jobs" in content
    assert "phase1-pons-v4-quote-routes-selected" in content
    assert "max-parallel: 2" in content
    assert "timeout-minutes: 30" in content
    assert "matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}" in content
    assert "time.sleep(" not in content


def test_v3_quote_gap_recovery_is_manual_gap_aware_and_bounded():
    content = _workflow("phase1-pons-v3-quote-fallback-recover-gaps.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "plan_missing_subranges" in content
    assert "prior_gap_run_id" in content
    assert "v3-quote-events-gap" in content
    assert "manifest_gap_aware_v3_quote_recovery" in content
    assert 'default: "100000"' in content
    assert "max_gap_blocks must be between 1 and 100000" in content
    assert "V3 quote gap plan exceeds 240 matrix jobs" in content
    assert "phase1-pons-v3-quote-routes-selected" in content
    assert "max-parallel: 2" in content
    assert "timeout-minutes: 30" in content
    assert "matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}" in content
    assert "time.sleep(" not in content


def test_v1_v3_gap_recovery_is_manual_gap_aware_and_bounded():
    content = _workflow("phase1-pons-v1-v3-recover-gaps.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "plan_missing_subranges" in content
    assert "coalesce_covered_ranges" in content
    assert "select_contiguous_cover" in content
    assert "candidate_source_files" in content
    assert "dropped_overlapping_source_files" in content
    assert 'manifest.get("path") == path.name' in content
    assert 'with path.open("rb") as handle:' in content
    assert "local_digest = hashlib.sha256()" in content
    assert content.count("import hashlib") == 4
    merge_block = content.split(
        "- name: Merge recovered V1 V3 event tape",
        1,
    )[1].split("- uses: actions/upload-artifact@v4", 1)[0]
    assert "import hashlib" in merge_block
    assert "digest = hashlib.sha256()" in merge_block
    assert 'local_digest.hexdigest() == manifest["sha256"]' in content
    assert "prior_gap_run_id" in content
    assert "v1-v3-events-gap" in content
    assert "manifest_gap_aware_v1_v3_recovery" in content
    assert 'default: "50000"' in content
    assert "max_gap_blocks must be between 1 and 100000" in content
    assert "V1 V3 gap plan exceeds four serialized 240-job waves" in content
    assert content.count("id: upload_gap") == 4
    assert content.count("id: retry_upload_gap") == 4
    assert content.count("name: Retry gap artifact upload") == 4
    assert content.count("name: Final gap artifact upload retry") == 4
    assert content.count("steps.upload_gap.outcome == 'failure'") == 4
    assert content.count("steps.retry_upload_gap.outcome == 'failure'") == 4
    assert content.count("id: upload_plan") == 1
    assert content.count("id: retry_upload_plan") == 1
    assert "Retry V1/V3 gap-plan artifact upload" in content
    assert "Final V1/V3 gap-plan artifact upload retry" in content
    assert content.count("id: upload_full") == 1
    assert content.count("id: retry_upload_full") == 1
    assert "Retry canonical V1/V3 artifact upload" in content
    assert "Final canonical V1/V3 artifact upload retry" in content
    assert content.count("overwrite: true") == 12
    assert content.count("continue-on-error: true") >= 15
    assert content.count("fetch_github_actions_json(") == 7
    assert "urllib.request.urlopen" not in content
    assert content.count("id: download_registry") == 5
    assert content.count("id: retry_download_registry") == 5
    assert content.count(
        "steps.download_registry.outcome == 'failure'"
    ) == 10
    assert content.count(
        "steps.retry_download_registry.outcome == 'failure'"
    ) == 10
    assert content.count("rm -rf registry") == 10
    assert "frozen parent recovery is blocked while source is active" in content
    assert "Verify frozen V1 registry input" in content
    assert "V1 registry run ID changed: " in content
    assert "V1 registry run is not successful" in content
    assert "V1 registry workflow path changed" in content
    assert "V1 registry branch changed" in content
    assert "V1 registry launch commit changed" in content
    assert "V1 registry artifact identity is ambiguous" in content
    assert "V1 registry manifest identity is ambiguous" in content
    assert "V1 registry manifest changed: " in content
    assert "V1 registry data identity is ambiguous" in content
    assert "actual_digest = hashlib.sha256()" in content
    assert "actual_records = 0" in content
    assert 'checks["actual_sha256"]' in content
    assert 'checks["actual_records"]' in content
    assert '"actual_sha256": actual_digest.hexdigest()' in content
    assert '"actual_records": actual_records' in content
    assert "33911022718" in content
    assert "phase1-pons-v1-registry-recovery.yml" in content
    assert "6506e15224b83b12cfd85b607d3fdb55a0d3b026" in content
    assert "pons-full-launch-registry.jsonl.manifest.json" in content
    assert "c75b93b5b8ace0caad3376b5e79c6dcdb9ba675fce9085f6db7458f3694d30ed" in content
    assert "494_639" in content
    assert content.count("Download every original V1/V3 shard artifact") == 1
    assert content.count("Discover original V1/V3 shard coverage") == 1
    assert "indexed_shard_bounds" in content
    assert "source-metadata/v1-v3-original-shards.json" in content
    assert '"planning_source_bytes_downloaded": 0' in content
    assert "Discover reusable prior V1/V3 gap coverage" in content
    assert "source-metadata/v1-v3-prior-gap-coverage.json" in content
    assert "expected_prior_reusable_gap_count" in content
    assert "EXPECTED_PRIOR_REUSABLE_GAP_COUNT" in content
    assert "expected_prior_terminal_snapshot_sha256" in content
    assert "EXPECTED_PRIOR_TERMINAL_SNAPSHOT_SHA256" in content
    assert "V1/V3 launcher prior binding inputs must be supplied " in content
    assert "V1/V3 expected prior terminal snapshot SHA-256 " in content
    assert "V1/V3 launcher prior binding requires prior gap run" in content
    assert "V1/V3 launcher/planner reusable prior-gap " in content
    assert "terminal_binding = build_rescue_terminal_binding(" in content
    assert "rescue_terminal_binding_sha256(" in content
    assert "observed_snapshot_sha256 = hashlib.sha256(" not in content
    assert "V1/V3 launcher/child prior terminal " in content
    assert '"phase1-pons-v1-v3-full"' in content
    assert "observed_groups = {}" in content
    assert "collapsed_retry_artifacts = 0" in content
    assert '"planning_prior_gap_jsonl_bytes_downloaded": 0' in content
    prior_coverage_block = content.split(
        "Discover reusable prior V1/V3 gap coverage",
        1,
    )[1].split("- id: plan", 1)[0]
    assert "for gap_id, row in observed.items():" in prior_coverage_block
    assert "if gap_id not in planned:" in prior_coverage_block
    assert "successful_repair_gap_ids" in prior_coverage_block
    assert 'str(row.get("conclusion") or "") == "success"' in prior_coverage_block
    assert "successful_gap_ids = successful_repair_gap_ids(cursor)" in prior_coverage_block
    assert "if gap_id not in successful_gap_ids:" in prior_coverage_block
    assert "ignored_non_success_artifacts += 1" in prior_coverage_block
    assert (
        prior_coverage_block.index("if gap_id not in planned:")
        < prior_coverage_block.index("if gap_id not in successful_gap_ids:")
    )
    assert "len(observed) != len(planned)" not in prior_coverage_block
    assert "len(observed) == len(planned)" not in prior_coverage_block
    assert content.count(
        r'gap_pattern = re.compile(r"^phase1-pons-v1-v3-gap-(\d+)$")'
    ) == 1
    assert (
        r'gap_pattern = re.compile(r"^phase1-pons-v1-v3-gap-(\\d+)$")'
        not in content
    )
    assert "V1/V3 source artifact pagination exceeded 2000" in content
    assert content.count(
        r'name_pattern = re.compile(r"^phase1-pons-v1-v3-(\d+)$")'
    ) == 2
    assert (
        r'name_pattern = re.compile(r"^phase1-pons-v1-v3-(\\d+)$")'
        not in content
    )
    assert "original_shard_artifacts" in content
    assert "duplicate V1/V3 shard file while downloading" in content
    assert "Download recursive paginated V1/V3 gap artifacts" in content
    assert "V1/V3 merge gap artifact pagination " in content
    assert "select_equivalent_artifact_retry" in content
    assert "prior recovery plan retry artifacts are not " in content
    assert "prior gap coverage plan retry artifacts are not " in content
    assert "prior gap coverage duplicate retry artifacts " in content
    assert "are not equivalent" in content
    assert "V1/V3 merge duplicate retry artifacts " in content
    assert "V1/V3 merge prior plan retry artifacts are not " in content
    assert "V1/V3 merge current plan retry artifacts are not " in content
    assert "V1/V3 merge contains duplicate gap artifact IDs" not in content
    assert "prior gap coverage has duplicate gap artifacts" not in content
    assert "V1/V3 merge prior gap lineage contains a cycle" in content
    assert "V1/V3 merge prior gap lineage exceeds 20 generations" in content
    assert "V1/V3 merge prior gap artifact is not bound " in content
    assert "V1/V3 merge prior gap job pagination " in content
    assert content.count("def successful_repair_gap_ids(") == 2
    assert content.count(
        "successful_gap_ids = successful_repair_gap_ids(cursor)"
    ) == 2
    assert content.count(
        'str(row.get("conclusion") or "") == "success"'
    ) == 2
    assert "ignored_gap_ids = [" in content
    assert "if gap_id not in successful_gap_ids" in content
    assert "prior_ignored_non_success_artifacts" in content
    assert "current V1/V3 gap artifact count does not match " in content
    assert "duplicate V1/V3 gap file while " in content
    assert "V1/V3 merge gap artifact is not bound " in content
    assert "V1/V3 merge gap manifest identity " in content
    assert "V1/V3 merge gap manifest range " in content
    assert "V1/V3 merge gap source changed: " in content
    assert "V1/V3 merge gap chain changed: " in content
    assert "V1/V3 merge gap protocol changed: " in content
    assert "V1/V3 merge gap frozen input changed: " in content
    assert "V1/V3 merge gap filter mode changed: " in content
    assert '"source") or "") != "evm_json_rpc"' in content
    assert 'provenance.get("chain_id", -1)' in content
    assert "uniswap_v3_shared_price_tape" in content
    assert 'provenance.get("registry")' in content
    assert "pons-full-launch-registry.jsonl" in content
    assert "global_topic_then_registry" in content
    assert "observed_bounds != expected_bounds" in content
    assert "V1/V3 merge current gap plan artifact " in content
    assert "V1/V3 merge current gap plan file identity " in content
    assert "current_plan_bytes = archive.read(" in content
    assert '(Path("plan") / plan_name).write_bytes(current_plan_bytes)' in content
    assert "name: phase1-pons-v1-v3-gap-plan\n          path: plan" not in content
    assert "V1/V3 merge current gap partial source changed" in content
    assert "V1/V3 merge current gap snapshot head changed" in content
    assert "V1/V3 merge current gap start block changed" in content
    assert "V1/V3 merge current gap prior lineage changed" in content
    assert "current V1/V3 gap artifact IDs do not match " in content
    assert content.count("validate_gap_plan_jobs(") == 4
    assert "prior gap coverage plan structure changed: " in content
    assert "V1/V3 generated gap plan is invalid: " in content
    assert "V1/V3 merge prior gap plan structure changed: " in content
    assert "V1/V3 merge current gap plan structure changed: " in content
    assert "CURRENT_GAP_COUNT: ${{ needs.plan.outputs.gap_count }}" in content
    assert "CURRENT_RUN_ID: ${{ github.run_id }}" in content
    assert 'Path("prior-gaps").rglob("v1-v3-events-gap-*.jsonl")' in content
    assert "pattern: phase1-pons-v1-v3-gap-*" not in content
    assert "pattern: phase1-pons-v1-v3-*" not in content
    assert content.count("fetch_github_actions_artifact_zip(") == 5
    assert "decode_json=False" not in content
    assert "Verify recursive prior recovery lineage" in content
    assert "prior recovery plan lacks bound lineage metadata" in content
    assert "prior recovery partial run does not match current" in content
    assert "prior recovery lineage exceeds 20 generations" in content
    assert '"partial_run_id": int("${{ inputs.partial_run_id }}")' in content
    assert '"prior_gap_run_id": (' in content
    assert "phase1-pons-full-eligibility-acquisition-one-shot.yml" in content
    assert "c53b3a63156976a5873752c332fa7578011249b0" in content
    assert "Pons V1 pools missing V3 Initialize" in content
    assert content.count("max-parallel: 2") == 4
    assert content.count("timeout-minutes: 30") == 4
    assert content.count("timeout-minutes: 45") == 1
    assert content.count("timeout-minutes: 90") == 1
    for index in range(1, 5):
        assert (
            "matrix_"
            + str(index)
            + ": ${{ steps.plan.outputs.matrix_"
            + str(index)
            + " }}"
            in content
        )
        assert (
            "matrix: ${{ fromJSON(needs.plan.outputs.matrix_"
            + str(index)
            + ") }}"
            in content
        )
        assert f"gap_count_{index}" in content
    assert "gap_wave_job_counts" in content
    assert "needs: [plan, recover_1]" in content
    assert "needs: [plan, recover_2]" in content
    assert "needs: [plan, recover_3]" in content
    assert "needs: [plan, recover_1, recover_2, recover_3, recover_4]" in content
    for index in range(1, 4):
        assert (
            f"needs.recover_{index}.result == 'failure'"
            in content
        )
    merge_gate = content.split(
        "  merge:",
        1,
    )[1].split("    runs-on:", 1)[0]
    assert "result == 'failure'" not in merge_gate
    assert "time.sleep(" not in content


def test_v1_v3_full_is_reusable_with_frozen_registry():
    content = _workflow("phase1-pons-v1-v3-full.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert 'default: "33911022718"' in content
    assert "SHARD_COUNT: '240'" in content
    assert "timeout-minutes: 40" in content
    assert "max-parallel: 2" in content


def test_v1_eligibility_is_reusable_with_frozen_quote_audit():
    content = _workflow("phase1-pons-v1-lifecycle-eligibility.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert 'default: "33911022718"' in content
    assert 'default: "33923299711"' in content
    assert 'default: "phase1-pons-full-quote-audit-current"' in content
    assert "V1 quote coverage is not complete" in content
    assert "Validate frozen V1 lifecycle input manifests" in content
    assert "required V1 lifecycle manifest is missing" in content
    assert "timeout-minutes: 60" in content
    assert "Resolve canonical V1 V3 selected shard artifacts" in content
    assert "resolve_v1_v3_canonical_shard_bindings" in content
    assert "resolve_v1_v3_canonical_shard_bindings" in content
    assert "select_equivalent_artifact_retry" in content
    assert "V1 lifecycle canonical V1/V3 artifact" in content
    assert "V1 lifecycle selected V1/V3 shard " in content
    assert "canonical_manifest_exact_artifacts" in content
    assert "selected_shards_by_run" in content
    assert "ThreadPoolExecutor" in content
    assert "max_workers=4" in content
    assert "V1 lifecycle canonical shard binding changed" in content
    assert "selected V1/V3 shard data SHA changed" in content
    assert "selected V1/V3 shard data record count changed" in content
    assert "pattern: phase1-pons-v1-v3-*" not in content
    assert "v3-shards/current" not in content
    assert "v3-shards/partial" not in content
    assert "v3-shards/prior" not in content
    assert "--v3-events-dir v3-shards" in content
    assert "--v3-events-manifest v3/pons-v1-v3-full.jsonl.manifest.json" in content
    assert "V1 lifecycle manifest snapshot mismatch" in content
    assert "Bind V1 lifecycle source run provenance" in content
    assert '"v1_v3_run_id": int(os.environ["V1_V3_RUN_ID"])' in content
    assert '"source_registry_run_id": int(' in content
    assert "frozen V1 lifecycle SHA changed" in content
    assert "c75b93b5b8ace0caad3376b5e79c6dcdb9ba675fce9085f6db7458f3694d30ed" in content
    assert "c822fe8d66f6b24ee496ccd20203cc81023e113ba0f66fa4188a5be49dd346dc" in content


def test_v2_v4_full_is_reusable_with_frozen_transition():
    content = _workflow("phase1-pons-v2-v4-full.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert 'default: "33912452330"' in content
    assert "max-parallel: 2" in content
    assert "SHARD_COUNT: '192'" in content
    assert "timeout-minutes: 30" in content


def test_quote_fallback_merge_is_reusable_without_network_trigger():
    content = _workflow("phase1-pons-quote-fallback-full.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "pons-merge-quote-usd-tapes" in content
    assert "merged quote fallback must have exactly 25 causal initial" in content
    assert "merged quote fallback must own exactly 30 feedless quote" in content
    assert "owned_quote_assets" in content
    assert "SNAPSHOT_HEAD: '54486035'" in content
    assert '--snapshot-head "$SNAPSHOT_HEAD"' in content


def test_v2_eligibility_is_reusable_with_frozen_known_inputs():
    content = _workflow("phase1-pons-v2-lifecycle-eligibility.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert 'default: "33912235341"' in content
    assert 'default: "33936232604"' in content
    assert 'default: "33912452330"' in content
    assert "cannot replay V2 lifecycle with uncovered quote assets" in content
    assert "Validate frozen V2 lifecycle input manifests" in content
    assert "required lifecycle manifest is missing" in content
    assert "timeout-minutes: 60" in content
    assert 'provenance.get("storage_mode") != "sharded_artifacts"' in content
    assert "Resolve canonical V2 V4 selected shard artifacts" in content
    assert "resolve_v2_v4_canonical_shard_bindings" in content
    assert "select_equivalent_artifact_retry" in content
    assert "V2 lifecycle canonical V2/V4 artifact" in content
    assert "V2 lifecycle selected V2/V4 shard " in content
    assert "canonical_manifest_exact_artifacts" in content
    assert "selected_shards_by_run" in content
    assert "ThreadPoolExecutor" in content
    assert "max_workers=4" in content
    assert "V2 lifecycle canonical shard binding changed" in content
    assert "selected V2/V4 shard data SHA changed" in content
    assert "selected V2/V4 shard data record count changed" in content
    assert "pattern: phase1-pons-v2-v4-*" not in content
    assert "v4-shards/current" not in content
    assert "v4-shards/partial" not in content
    assert "v4-shards/prior" not in content
    assert "--v4-events-dir v4-shards" in content
    assert "--v4-events-manifest v4/pons-v2-v4-full.jsonl.manifest.json" in content
    assert "lifecycle manifest snapshot mismatch" in content
    assert "Bind V2 lifecycle source run provenance" in content
    assert '"v4_run_id": int(os.environ["V4_RUN_ID"])' in content
    assert '"fallback_run_id": int(os.environ["FALLBACK_RUN_ID"])' in content
    assert "frozen lifecycle SHA changed" in content
    assert "validated_manifest_count" in content
    assert "771c9147ef1a84bd673532842972e16e0ee12cae1513a41b402f53b5c444c50b" in content


def test_eligible_universe_freeze_is_reusable_and_fails_closed():
    content = _workflow("phase1-pons-eligible-universe-freeze.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "cannot freeze complete $100k universe while eligibility" in content
    assert "required eligibility manifest is missing" in content
    assert "eligibility manifest snapshot mismatch" in content
    assert "eligibility manifest record mismatch" in content
    assert '"v1_eligibility_sha256": v1_manifest["sha256"]' in content
    assert '"v2_eligibility_sha256": v2_manifest["sha256"]' in content
    assert '"v1_v3_run_id": v1_v3_run_id' in content
    assert '"v2_v4_run_id": v2_v4_run_id' in content
    assert "eligibility lifecycle venue provenance missing" in content
    assert "lifecycle_run_id != 33_982_556_591" in content
    assert '"validated_v1_v3_run_id": v1_v3_run_id' in content
    assert '"validated_v2_v4_run_id": v2_v4_run_id' in content
    assert "268_688" in content
    assert "225_951" in content
    assert "eligibility artifact has invalid status values" in content
    assert "id: upload_universe" in content
    assert "id: retry_upload_universe" in content
    assert "Retry eligible universe artifact upload" in content
    assert "Final eligible universe artifact upload retry" in content
    for source in ("v1", "v2"):
        assert content.count(f"id: download_{source}") == 1, source
        assert content.count(f"id: retry_download_{source}") == 1, source
        assert content.count(
            f"steps.download_{source}.outcome == 'failure'"
        ) == 2, source
        assert content.count(
            f"steps.retry_download_{source}.outcome == 'failure'"
        ) == 2, source
        assert content.count(f"rm -rf {source}") == 2, source


def test_skhy_known_pool_continuation_is_manual_bounded_and_frozen():
    content = _workflow("phase1-pons-skhy-v4-known-pool-continuation.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert 'default: "33926428274"' in content
    assert 'default: "100000"' in content
    assert "forward_blocks must be between 1 and 100000" in content
    assert "expected_prior_search_end" in content
    assert "output_artifact_name" in content
    assert "0x84cab63bc87912e71ad199ff14a0ba45de68fef8" in content
    assert "0x8107f97277321f2899eba8d6721411e34cf368c6e24c9f0abb1658733e548601" in content
    assert 'default: "52863525"' in content
    assert "--known-pool-only" in content
    assert 'row.get("continuation_mode") != "known_pool_only"' in content
    assert "continue_needed" in content
    assert "route_ready" in content
    assert "search_to_block" in content
    assert "GITHUB_OUTPUT" in content
    assert "timeout-minutes: 30" in content
    assert "time.sleep(" not in content


def test_representative_evidence_one_shot_is_guarded_and_unarmed():
    content = _workflow("phase1-pons-representative-evidence-one-shot.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "push:" in trigger_block
    assert "workflow_dispatch:" not in trigger_block
    assert ".github/phase1-pons-representative-evidence.json" in content
    assert "startsWith(github.event.head_commit.message" in content
    assert "contains(github.event.head_commit.message" not in content
    assert "launch representative evidence generation " in content
    assert 'r"launch representative evidence generation (\\d+)"' in content
    assert "launch message must be exactly one line" in content
    assert "launch requires an exact generation" in content
    assert "launch/config generation mismatch" in content
    assert "generation must increment " in content
    assert "by exactly one" in content
    assert "launch must be a direct " in content
    assert "single-parent commit" in content
    assert "launch must modify exactly " in content
    assert "the guarded config file" in content
    assert "representative evidence config is not armed" in content
    assert "validation_generation != 1" in content
    assert "previous_validation_generation != 1" in content
    assert "required run IDs must be positive" in content
    assert "phase1-pons-live-venue-rescue-one-shot.yml/runs" in content
    assert "cannot overlap active venue rescue" in content
    assert "rescue_pattern.fullmatch(title)" in content
    assert "phase1-pons-v1-lifecycle-eligibility" in content
    assert "phase1-pons-v2-lifecycle-eligibility" in content
    assert "phase1-pons-quote-fallback-full" in content
    assert "phase1-pons-eligible-universe" in content
    assert "Download frozen eligible universe" in content
    assert "pons-eligible-universe-summary.json" in content
    assert "pons-eligible-100k-universe.jsonl.manifest.json" in content
    assert "representative eligibility V1/V3 provenance mismatch" in content
    assert "representative eligibility V2/V4 provenance mismatch" in content
    assert "representative eligibility universe remains incomplete" in content
    assert "representative eligibility universe SHA mismatch" in content
    assert "representative eligibility V1 lifecycle run mismatch" in content
    assert "representative eligibility V2 lifecycle run mismatch" in content
    assert "representative eligibility manifest V1/V3 mismatch" in content
    assert "representative eligibility manifest V2/V4 mismatch" in content
    assert 'summary.get("all_pons_launches", -1)' in content
    assert "494_639" in content
    assert "268_688" in content
    assert "225_951" in content
    assert "phase1-pons-v1-v3-full" in content
    assert "phase1-pons-v2-v4-full" in content
    assert "phase1-pons-full-eligibility-acquisition-one-shot.yml" in content
    assert "phase1-pons-recovered-completion-one-shot.yml" in content
    assert "phase1-pons-representative-evidence-chain.yml" in content
    assert 'oracle_run_id: "33974681334"' in content
    assert 'runner_smoke_run_id: "33920762592"' in content
    assert 'registry_run_id: "33911022718"' in content
    assert 'v2_curve_run_id: "33936232604"' in content
    assert 'transition_run_id: "33912452330"' in content
    assert 'quote_audit_run_id: "33923299711"' in content
    assert 'anchor_run_id: "33972109927"' in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content

    config = (
        Path(__file__).parents[1]
        / ".github"
        / "phase1-pons-representative-evidence.json"
    ).read_text()
    assert '"generation": 0' in config
    assert '"validation_generation": 1' in config
    assert '"eligibility_run_id": 0' in config
    assert '"v1_v3_run_id": 0' in config
    assert '"v2_v4_run_id": 0' in config
    assert '"prior_transfer_run_id": 0' in config


def test_viability_pons_registry_launcher_is_guarded_and_pinned():
    content = _workflow(
        "phase1-pons-viability-pons-registry-one-shot.yml"
    )
    assert "phase1-pons-viability-guarded-route.yml" in content
    assert "launch viability pons_registry" in content
    assert 'route: "pons_registry"' in content
    assert "sequence_id: ${{ github.sha }}" in content
    assert "workflow_dispatch:" not in content

def test_full_eligibility_one_shot_is_guarded_and_pinned():
    content = _workflow(
        "phase1-pons-full-eligibility-acquisition-one-shot.yml"
    )
    assert "phase1-pons-full-eligibility-acquisition-chain.yml" in content
    assert "launch full eligibility acquisition" in content
    assert 'oracle_run_id: "33974681334"' in content
    assert 'anchor_run_id: "33972109927"' in content
    assert "workflow_dispatch:" not in content


def test_full_eligibility_acquisition_chain_serializes_heavy_market_tapes():
    content = _workflow(
        "phase1-pons-full-eligibility-acquisition-chain.yml"
    )
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "phase1-pons-stock-oracle-full" in content
    assert "canonical stock oracle must contain 23 feeds" in content
    assert 'summary.get("delta_symbols") != ["DELL"]' in content
    assert "needs: preflight" in content
    assert "needs.preflight.result == 'success'" in content
    assert "phase1-pons-v1-v3-full.yml" in content
    assert "phase1-pons-v1-v3-recover-gaps.yml" in content
    assert "phase1-pons-v2-v4-full.yml" in content
    assert "phase1-pons-v2-v4-recover-gaps.yml" in content
    assert "needs.v1_v3.result == 'failure'" in content
    assert "needs.v1_v3_recovery.result == 'success'" in content
    assert "needs.v2_v4.result == 'failure'" in content
    assert "needs.v2_v4_recovery.result == 'success'" in content
    assert content.count('partial_run_id: ${{ format(\'{0}\', github.run_id) }}') == 2
    assert content.count('max_gap_blocks: "50000"') == 2
    assert "phase1-pons-pricing-eligibility-chain.yml" in content
    assert content.count("format('{0}', github.run_id)") == 4
    assert "cancel-in-progress: false" in content


def test_final_acceptance_chain_requires_nine_distinct_route_runs():
    content = _workflow("phase1-pons-final-acceptance-chain.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "cancel-in-progress: false" in content
    assert "Verify evidence and nine route provenance before acceptance work" in content
    assert "final acceptance eligible and representative runs must" in content
    assert "final acceptance evidence workflow path is not allowed" in content
    assert "final acceptance evidence artifacts missing" in content
    assert "final acceptance evidence-ready retry artifacts " in content
    assert "are not equivalent" in content
    assert "evidence_artifact_id" in content
    assert (
        "artifact-ids: ${{ steps.provenance.outputs.evidence_artifact_id }}"
        in content
    )
    assert "Validate full evidence handoff identity before acceptance" in content
    assert "final acceptance evidence handoff is not ready" in content
    assert "final acceptance evidence handoff run mismatch" in content
    assert "final acceptance evidence handoff source changed" in content
    assert "final acceptance handoff evidence workflow path changed" in content
    assert "normal_evidence_path = (" in content
    assert "recovered_evidence_path = (" in content
    assert "final acceptance normal evidence is marked recovered" in content
    assert "final acceptance normal evidence routing changed" in content
    assert "final acceptance recovered evidence is not marked " in content
    assert "urllib.request.Request(" in content
    assert 'GITHUB_TOKEN: ${{ github.token }}' in content
    assert "final acceptance evidence hash is invalid" in content
    assert "representative_sample_sha256" in content
    assert "representative_token_set_sha256" in content
    assert "representative_source_coverage_sha256" in content
    assert "final acceptance runner-smoke run changed" in content
    assert "final acceptance runner-smoke universe SHA changed" in content
    assert "final acceptance runner-smoke outcomes SHA changed" in content
    assert "final acceptance route workflow path mismatch" in content
    assert "final acceptance route measurement artifacts missing" in content
    assert "Verify route measurement artifact contents" in content
    assert content.count("actions/download-artifact@v4") >= 10
    assert "final acceptance route measurement content mismatch" in content
    assert '"from_block": 54_436_036' in content
    assert '"to_block": 54_486_035' in content
    assert '"processed_block_span": 50_000' in content
    assert '"measurement_run_id": run_id' in content
    assert '"measurement_head_sha": head_sha' in content
    assert '"evidence_run_id": evidence_run_id' in content
    assert '"source_eligibility_run_id": 33_982_556_591' in content
    assert '"sequence_id": head_sha' in content
    assert 'registry_generation="v2"' in content
    assert "final acceptance route source changed" in content
    assert "final acceptance route evidence changed" in content
    assert "final acceptance route launch ledger changed" in content
    assert "final acceptance route launch slot was not empty" in content
    assert "source_eligibility_run_id" in content
    assert "needs: preflight" in content
    assert "needs.preflight.result == 'success'" in content
    for route in (
        "pons_registry",
        "pons_v1_v3",
        "pons_v2_curve",
        "pons_v2_transition",
        "pons_v2_v4",
        "weth_usdg_anchor",
        "stock_oracle",
        "quote_v3_fallback",
        "quote_v4_fallback",
    ):
        assert f"{route}_run_id:" in content
    assert "build_phase1_route_plan" in content
    assert "final acceptance route order changed" in content
    assert "nine distinct evidence run IDs" in content
    assert "phase1-pons-acquisition-accounting.yml" in content
    assert "phase1-pons-acquisition-viability-projection.yml" in content
    assert "phase1-pons-acceptance-gate.yml" in content
    assert "accounting_run_id: ${{ format('{0}', github.run_id) }}" in content
    assert "viability_projection_run_id: ${{ format('{0}', github.run_id) }}" in content
    assert "eligible_universe_run_id: ${{ inputs.eligibility_run_id }}" in content
    assert "representative_validation_run_id: ${{ inputs.representative_run_id }}" in content

def test_pricing_eligibility_chain_branches_on_frozen_skhy_completion():
    content = _workflow("phase1-pons-pricing-eligibility-chain.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "needs.skhy_v3.outputs.completion_status" in content
    assert "searched_to_snapshot_head" in content
    assert "needs.skhy_v4.outputs.route_ready == 'true'" in content
    assert "needs.skhy_v3.outputs.completion_status == 'route_resolved'" in content
    assert "phase1-pons-skhy-v4-known-pool-segmented.yml" in content
    assert "phase1-pons-v3-quote-fallback-full.yml" in content
    assert "phase1-pons-v3-quote-fallback-recover-gaps.yml" in content
    assert "needs.v3_fallback_recovery.result == 'success'" in content
    assert "phase1-pons-v4-quote-fallback-full.yml" in content
    assert "phase1-pons-v4-quote-fallback-recover-gaps.yml" in content
    assert "needs.v4_fallback_recovery.result == 'success'" in content
    assert content.count('max_gap_blocks: "100000"') == 2
    assert "phase1-pons-quote-fallback-full.yml" in content
    assert "phase1-pons-v1-lifecycle-eligibility.yml" in content
    assert "phase1-pons-v2-lifecycle-eligibility.yml" in content
    assert "phase1-pons-eligible-universe-freeze.yml" in content
    assert "format('{0}', github.run_id)" in content
    assert "cancel-in-progress: false" in content


def test_skhy_v4_one_shot_launcher_is_explicit_and_guarded():
    content = _workflow(
        "phase1-pons-skhy-v4-known-pool-segmented-one-shot.yml"
    )
    assert "phase1-pons-skhy-v4-known-pool-segmented.yml" in content
    assert "launch SKHY V4 known-pool continuation" in content
    assert 'prior_probe_run_id: "33926428274"' in content
    assert "workflow_dispatch:" not in content


def test_skhy_segmented_continuation_is_manual_sequential_and_complete():
    content = _workflow(
        "phase1-pons-skhy-v4-known-pool-segmented.yml"
    )
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert content.count(
        "uses: ./.github/workflows/"
        "phase1-pons-skhy-v4-known-pool-continuation.yml"
    ) == 17
    assert content.count('forward_blocks: "100000"') == 17
    for index in range(16):
        assert f"needs: segment_{index}" in content
        assert (
            f"needs.segment_{index}.outputs.continue_needed == 'true'"
            in content
        )
        assert f"phase1-pons-skhy-v4-segment-{index}" in content
    assert "phase1-pons-skhy-v4-segment-16" in content
    assert "pattern: phase1-pons-skhy-v4-segment-*" in content
    assert '"continuation_segments": latest_index + 1' in content
    assert '"max_blocks_per_segment": 100000' in content
    assert "phase1-pons-skhy-v4-known-pool-segmented" in content
    assert "segmented SKHY continuation ended before snapshot head" in content
    assert '"remaining_unsearched_blocks": remaining' in content
    assert "max_blocks_per_segment" in content
    assert "jobs.finalize.outputs.completion_status" in content
    assert "steps.freeze.outputs.route_ready" in content
    assert "GITHUB_OUTPUT" in content
    assert "time.sleep(" not in content


def test_v4_quote_continuation_is_reusable_without_push_trigger():
    content = _workflow("phase1-pons-v4-quote-continuation.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "known_pool_only" in content
    assert "EXTRA+=(--known-pool-only)" in content

def test_representative_evidence_chain_threads_one_parent_run_and_resumes_transfers():
    content = _workflow("phase1-pons-representative-evidence-chain.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "cancel-in-progress: false" in content
    assert "phase1-pons-representative-sample-freeze.yml" in content
    assert "phase1-pons-representative-market-paths.yml" in content
    assert content.count("phase1-pons-representative-transfers-full.yml") == 1
    assert "phase1-pons-representative-priced-paths.yml" in content
    assert "phase1-pons-representative-dex-crosscheck.yml" in content
    assert "phase1-pons-representative-validation.yml" in content
    assert content.count("v1_eligibility_run_id: ${{ inputs.eligibility_run_id }}") == 3
    assert content.count("v2_eligibility_run_id: ${{ inputs.eligibility_run_id }}") == 3
    assert "v1_v3_run_id:" in content
    assert "v2_v4_run_id:" in content
    assert (
        "inputs.v1_v3_run_id != '' && inputs.v1_v3_run_id || "
        "inputs.eligibility_run_id"
    ) in content
    assert (
        "inputs.v2_v4_run_id != '' && inputs.v2_v4_run_id || "
        "inputs.eligibility_run_id"
    ) in content
    assert "fallback_run_id: ${{ inputs.eligibility_run_id }}" in content
    assert "prior_run_id: ${{ inputs.prior_transfer_run_id }}" in content
    assert "registry_run_id: ${{ inputs.registry_run_id }}" in content
    assert "v2_curve_run_id: ${{ inputs.v2_curve_run_id }}" in content
    assert "transition_run_id: ${{ inputs.transition_run_id }}" in content
    assert "quote_audit_run_id: ${{ inputs.quote_audit_run_id }}" in content
    assert "anchor_run_id: ${{ inputs.anchor_run_id }}" in content
    assert "oracle_run_id: ${{ inputs.oracle_run_id }}" in content
    assert "fallback_run_id: ${{ inputs.eligibility_run_id }}" in content
    assert "transfers_retry:" not in content
    assert "needs.transfers.result == 'success'" in content
    assert content.count("format('{0}', github.run_id)") >= 10
    assert "import urllib.error" in content
    assert "transient_http_codes = {" in content
    assert "for attempt in range(3):" in content
    assert "representative preflight metadata retry loop exhausted" in content
    for source in ("preflight_v1", "preflight_v2"):
        assert content.count(f"id: download_{source}") == 1, source
        assert content.count(f"id: retry_download_{source}") == 1, source
        assert content.count(
            f"steps.download_{source}.outcome == 'failure'"
        ) == 2, source
        assert content.count(
            f"steps.retry_download_{source}.outcome == 'failure'"
        ) == 2, source
    assert "time.sleep(" not in content

def test_representative_sample_freeze_is_reusable_and_pinned():
    content = _workflow("phase1-pons-representative-sample-freeze.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert 'default: "33920762592"' in content
    assert "4861b2af1d549eb41c53341a07f6de71dce4d9486b769543c1376beab9c19ab9" in content
    assert "6fb40693b77d7434d4e579a2225fed2c65061841a5ea9d0ba56f785071fc6ef2" in content
    assert "frozen runner smoke must contain exactly five eligible" in content
    assert "runner_smoke_universe_sha256" in content
    assert "runner_smoke_outcomes_sha256" in content
    assert "representative runner cohort drifted from frozen smoke " in content
    assert "evidence: expected=" in content
    assert '"runner_tokens": sorted(sample_runner_tokens)' in content
    assert '"failure_tokens": failure_tokens' in content
    assert "representative_sample_identity" in content
    assert "pons-representative-sample-identity.json" in content
    assert '"sample_sha256": identity["sample_sha256"]' in content
    assert '"token_set_sha256": identity["token_set_sha256"]' in content
    assert '"validated_v1_v3_run_id": v1_v3_run_id' in content
    assert '"validated_v2_v4_run_id": v2_v4_run_id' in content
    assert "representative sample lifecycle venue " in content
    assert "provenance missing: {field} " in content
    assert "representative sample lifecycle venue run " in content
    assert 'versions != {"v1": 4, "v2": 1}' in content
    assert "--runners 5 --failures 5" in content
    assert "representative sample must freeze exactly five runners" in content
    assert "representative sample must contain both Pons generations" in content
    for source in ("v1", "v2", "smoke"):
        assert content.count(f"id: download_{source}") == 1, source
        assert content.count(f"id: retry_download_{source}") == 1, source
        assert content.count(
            f"steps.download_{source}.outcome == 'failure'"
        ) == 2, source
        assert content.count(
            f"steps.retry_download_{source}.outcome == 'failure'"
        ) == 2, source
        assert content.count(f"rm -rf {source}") == 2, source
    assert "time.sleep(" not in content

def test_representative_transfer_backfill_is_manual_resumable_and_bounded():
    content = _workflow("phase1-pons-representative-transfers-full.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "prior_run_id" in content
    assert "plan_missing_subranges" in content
    assert 'default: "100000"' in content
    call_block = content.split("  workflow_call:", 1)[1].split(
        "\npermissions:", 1
    )[0]
    assert "max_blocks:" in call_block
    assert 'default: "100000"' in call_block
    assert "required: false" in call_block
    assert "max_blocks must be between 1 and 200000" in content
    assert "representative transfer plan exceeds four serialized " in content
    assert "require_representative_sample_identity" in content
    assert "pons-representative-sample-summary.json" in content
    assert '"sample_sha256": sample_sha256' in content
    assert '"token_set_sha256": token_set_sha256' in content
    assert "prior transfer shard sample identity mismatch" in content
    assert "prior transfer shard token-set identity mismatch" in content
    assert "representative transfer shard sample identity " in content
    assert "representative transfer shard token-set identity " in content
    assert "representative transfer merge requires exactly 10 " in content
    assert (
        "Download every prior representative transfer shard artifact"
        in content
    )
    assert (
        "Download every representative transfer shard artifact for merge"
        in content
    )
    assert "representative transfer artifact pagination " in content
    assert "exceeded 2000" in content
    assert (
        'r"^phase1-pons-representative-transfer-(\\d+)$"'
        in content
    )
    assert "pattern: phase1-pons-representative-transfer-*" not in content
    assert content.count("fetch_github_actions_artifact_zip(") == 2
    assert 'CURRENT_RUN_ID: ${{ github.run_id }}' in content
    assert "prior representative transfer run has no shard artifacts" in content
    assert 'f"{label} representative transfer run has no "' in content
    assert '"shard artifacts"' in content
    assert content.count("max-parallel: 2") == 4
    assert content.count("timeout-minutes: 30") == 4
    assert content.count("timeout-minutes: 45") == 1
    assert content.count("timeout-minutes: 90") == 1
    for index in range(1, 5):
        assert (
            "matrix_"
            + str(index)
            + ": ${{ steps.plan.outputs.matrix_"
            + str(index)
            + " }}"
            in content
        )
        assert (
            "matrix: ${{ fromJSON(needs.plan.outputs.matrix_"
            + str(index)
            + ") }}"
            in content
        )
        assert f"gap_count_{index}" in content
    assert "gap_wave_job_counts" in content
    assert "needs: [plan, acquire_1]" in content
    assert "needs: [plan, acquire_2]" in content
    assert "needs: [plan, acquire_3]" in content
    assert (
        "needs: [plan, acquire_1, acquire_2, acquire_3, acquire_4]"
        in content
    )
    assert "time.sleep(" not in content

def test_phase1_acceptance_gate_is_manual_artifact_only_and_fail_closed():
    content = _workflow("phase1-pons-acceptance-gate.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "phase1-pons-eligible-universe" in content
    assert "phase1-pons-representative-validation" in content
    assert "phase1-pons-acquisition-viability-projection" in content
    assert "Verify acceptance caller and evidence provenance" in content
    assert "acceptance eligible and representative artifacts must" in content
    assert "acceptance viability projection must come from the" in content
    assert "acceptance gate direct caller is not allowed" in content
    assert "phase1-pons-viability-ledger-finalize-one-shot.yml" in content
    assert "phase1-pons-final-acceptance-chain.yml" in content
    assert "acceptance evidence workflow path is not allowed" in content
    assert "acceptance evidence artifacts missing" in content
    assert "select_equivalent_artifact_retry" in content
    assert "acceptance evidence retry artifacts are not " in content
    assert "eligible_artifact_id" in content
    assert "representative_artifact_id" in content
    assert (
        "artifact-ids: ${{ steps.provenance.outputs.eligible_artifact_id }}"
        in content
    )
    assert (
        "artifact-ids: ${{ steps.provenance.outputs."
        "representative_artifact_id }}"
        in content
    )
    assert "acceptance current run is missing viability projection" in content
    assert "artifact_rows_cache = {}" in content
    assert "acceptance viability projection retry artifacts " in content
    assert "are not equivalent" in content
    assert "viability_artifact_id" in content
    assert (
        "artifact-ids: ${{ steps.provenance.outputs.viability_artifact_id }}"
        in content
    )
    assert "build_phase1_acceptance_report" in content
    assert "REQUIRED_PHASE1_ACQUISITION_ROUTES" in content
    assert 'phase1_acceptance_status"] != "pass"' in content
    assert "id: upload_acceptance" in content
    assert "id: retry_upload_acceptance" in content
    assert "Retry Phase 1 acceptance artifact upload" in content
    assert "Final Phase 1 acceptance artifact upload retry" in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "RpcClient" not in content
    assert "GeckoTerminalClient" not in content
    assert "time.sleep(" not in content


def test_phase1_viability_projection_is_manual_artifact_only_and_fail_closed():
    content = _workflow(
        "phase1-pons-acquisition-viability-projection.yml"
    )
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "phase1-pons-acquisition-accounting" in content
    assert "Resolve exact acquisition accounting artifact" in content
    assert "select_equivalent_artifact_retry" in content
    assert "viability accounting retry artifacts are not equivalent" in content
    assert (
        "artifact-ids: ${{ steps.accounting_artifact.outputs.artifact_id }}"
        in content
    )
    assert "id: upload_projection" in content
    assert "id: retry_upload_projection" in content
    assert "Retry acquisition viability projection upload" in content
    assert "Final acquisition viability projection upload retry" in content
    assert "build_phase1_route_plan" in content
    assert "project_phase1_acquisition_plan" in content
    assert "route_plan_json" in content
    assert "route -> evidence run IDs" in content
    assert "zero_cost_route_evidence" in content
    assert "does not mark Phase 1 PASS" in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "RpcClient" not in content
    assert "GeckoTerminalClient" not in content
    assert "time.sleep(" not in content


def test_phase1_acquisition_accounting_is_manual_github_only_and_bounded():
    content = _workflow("phase1-pons-acquisition-accounting.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "actions: read" in content
    assert "run_ids_json" in content
    assert "at most 50 positive integer run IDs" in content
    assert "summarize_action_run" in content
    assert "summarize_phase1_runs" in content
    assert "id: upload_accounting" in content
    assert "id: retry_upload_accounting" in content
    assert "Retry acquisition accounting artifact upload" in content
    assert "Final acquisition accounting artifact upload retry" in content
    assert "steps.upload_accounting.outcome == 'failure'" in content
    assert "steps.retry_upload_accounting.outcome == 'failure'" in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "max-parallel:" not in content
    assert "time.sleep(" not in content

def test_skhy_v3_weth_continuation_is_manual_known_pool_and_bounded():
    content = _workflow(
        "phase1-pons-skhy-v3-weth-continuation.yml"
    )
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert 'default: "33921477647"' in content
    assert "0x84cab63bc87912e71ad199ff14a0ba45de68fef8" in content
    assert "0x13f78b235d19141f572986afcaab66ce7744b4ef" in content
    assert "SKHY_WETH_FEE: '3000'" in content
    assert "SKHY_FIRST_PONS_USE: '52263525'" in content
    assert "forward_blocks must be between 1 and 100000" in content
    assert 'deployment-block "$SKHY_WETH_POOL"' in content
    assert "--archive" in content
    assert "rpc-pons-delayed-v3-weth-routes" in content
    assert '--quote-token "$SKHY_TOKEN"' in content
    assert "continue_needed" in content
    assert "next_from_block" in content
    assert "route_ready" in content
    assert "first_observed_usd_price" in content
    assert "deferred to event-ordered WETH/USD anchor replay" in content
    assert "timeout-minutes: 30" in content
    assert "max-parallel:" not in content
    assert "time.sleep(" not in content


def test_skhy_v3_weth_segmented_is_manual_sequential_and_early_stopping():
    content = _workflow(
        "phase1-pons-skhy-v3-weth-segmented.yml"
    )
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert content.count(
        "phase1-pons-skhy-v3-weth-continuation.yml"
    ) == 23
    assert content.count('forward_blocks: "100000"') == 23
    for index in range(22):
        assert (
            f"needs.segment_{index}.outputs.continue_needed == 'true'"
            in content
        )
        assert (
            f"needs.segment_{index}.outputs.next_from_block"
            in content
        )
    assert '"max_blocks_per_segment": 100000' in content
    assert "if: ${{ always() }}" in content
    assert "searched_to_snapshot_head" in content
    assert "route_resolved" in content
    assert "jobs.finalize.outputs.completion_status" in content
    assert "steps.freeze.outputs.route_ready" in content
    assert "GITHUB_OUTPUT" in content
    assert "max_blocks_per_segment" in content
    assert "max-parallel:" not in content
    assert "time.sleep(" not in content


def test_representative_explorer_crosscheck_is_manual_public_and_bounded():
    content = _workflow(
        "phase1-pons-representative-explorer-crosscheck.yml"
    )
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "access_reverified" in content
    assert "known 403" in content
    assert "if: ${{ inputs.access_reverified == true }}" in content
    assert "phase1-pons-representative-sample" in content
    assert "phase1-pons-representative-market-paths" in content
    assert "phase1-pons-representative-priced-paths" in content
    assert "BlockscoutClient" in content
    assert "build_representative_explorer_targets" in content
    assert "build_representative_explorer_token_summaries" in content
    assert "10 <= len(targets) <= 40" in content
    assert "blockscout_requests" in content
    assert "blockscout_response_bytes" in content
    assert "transaction_identity_and_block" in content
    assert "raw chain" in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "RpcClient" not in content
    assert "GeckoTerminalClient" not in content
    assert "time.sleep(" not in content


def test_representative_dex_crosscheck_is_manual_independent_and_bounded():
    content = _workflow("phase1-pons-representative-dex-crosscheck.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "GeckoTerminalClient" in content
    assert "geckoterminal_public_api" in content
    assert "not canonical historical truth" in content
    assert "phase1-pons-representative-priced-paths" in content
    assert "priced_path_run_id" in content
    assert "select_representative_dex_price_checkpoints" in content
    assert "targeted_swap_price_tokens" in content
    assert "targeted_swap_price_checkpoints" in content
    assert "representative DEX cross-check requires exactly 10" in content
    assert "independent DEX pool reconciliation failed" in content
    assert "timeout-minutes: 30" in content
    assert "logical_gecko_requests > 40" in content
    assert "max_gecko_attempts = logical_gecko_requests * client.attempts" in content
    assert "representative DEX logical request budget exceeded" in content
    assert "representative DEX HTTP attempt budget exceeded" in content
    assert "require_representative_sample_identity" in content
    assert "priced-path sample identity" in content
    assert '"sample_sha256": sample_identity["sample_sha256"]' in content
    assert '"token_set_sha256": sample_identity["token_set_sha256"]' in content
    assert "geckoterminal_logical_request_budget" in content
    assert "geckoterminal_http_attempt_budget" in content
    assert 'default: "33911022718"' in content
    assert 'default: "33912452330"' in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "time.sleep(" not in content



def test_representative_market_paths_are_manual_artifact_only_and_bounded():
    content = _workflow("phase1-pons-representative-market-paths.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "phase1-pons-representative-sample" in content
    assert "phase1-pons-full-registry-recovered" in content
    assert "phase1-pons-v1-v3-full" in content
    assert "phase1-pons-v2-curve-full" in content
    assert "phase1-pons-v2-transition-full" in content
    assert "phase1-pons-v2-v4-full" in content
    assert "build_representative_market_path_rows" in content
    assert "summarize_representative_market_paths" in content
    assert "summarize_sharded_manifest_coverage" in content
    assert "pons-representative-market-source-coverage.json" in content
    assert "require_representative_sample_identity" in content
    assert '"sample_sha256": sample_identity["sample_sha256"]' in content
    assert '"token_set_sha256": sample_identity["token_set_sha256"]' in content
    assert "representative market-path sample V1/V3 lineage mismatch" in content
    assert "representative market-path sample V2/V4 lineage mismatch" in content
    assert 'sample_summary.get("validated_v1_v3_run_id", -1)' in content
    assert 'sample_summary.get("validated_v2_v4_run_id", -1)' in content
    assert "no provider requests" in content
    assert 'default: "33911022718"' in content
    assert 'default: "33936232604"' in content
    assert 'default: "33912452330"' in content
    for source in (
        "sample",
        "registry",
        "v1v3",
        "v1v3_current",
        "v1v3_partial",
        "v1v3_prior",
        "v2curve",
        "transition",
        "v2v4",
        "v2v4_current",
        "v2v4_partial",
        "v2v4_prior",
    ):
        assert content.count(f"id: download_{source}") == 1, source
        assert content.count(f"id: retry_download_{source}") == 1, source
        assert content.count(
            f"steps.download_{source}.outcome == 'failure'"
        ) == 2, source
        assert content.count(
            f"steps.retry_download_{source}.outcome == 'failure'"
        ) == 2, source
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "RpcClient" not in content
    assert "GeckoTerminalClient" not in content
    assert "time.sleep(" not in content


def test_representative_priced_paths_are_manual_artifact_only_and_bounded():
    content = _workflow("phase1-pons-representative-priced-paths.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "phase1-pons-representative-sample" in content
    assert "phase1-pons-representative-market-paths" in content
    assert "phase1-pons-weth-usdg-anchor-full" in content
    assert "phase1-pons-stock-oracle-full" in content
    assert "phase1-pons-quote-fallback-full" in content
    assert "build_v1_market_cap_points" in content
    assert "build_v2_curve_market_cap_points" in content
    assert "build_v2_graduation_seed_points" in content
    assert "build_v2_v4_market_cap_points" in content
    assert "validate_representative_priced_path_rows" in content
    assert "summarize_representative_priced_paths" in content
    assert "summarize_sharded_manifest_coverage" in content
    assert "summarize_snapshot_manifest_coverage" in content
    assert "pons-representative-pricing-source-coverage.json" in content
    assert "require_representative_sample_identity" in content
    assert "market-path sample " in content
    assert "identity mismatch: {field}" in content
    assert '"sample_sha256": sample_identity["sample_sha256"]' in content
    assert '"token_set_sha256": sample_identity["token_set_sha256"]' in content
    for source in (
        "sample",
        "market_paths",
        "quotes",
        "anchor",
        "oracle",
        "fallback",
    ):
        assert content.count(f"id: download_{source}") == 1, source
        assert content.count(f"id: retry_download_{source}") == 1, source
        assert content.count(
            f"steps.download_{source}.outcome == 'failure'"
        ) == 2, source
        assert content.count(
            f"steps.retry_download_{source}.outcome == 'failure'"
        ) == 2, source
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "RpcClient" not in content
    assert "GeckoTerminalClient" not in content
    assert "time.sleep(" not in content


def test_representative_validation_is_manual_artifact_only_and_fail_closed():
    content = _workflow("phase1-pons-representative-validation.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "phase1-pons-representative-sample" in content
    assert "phase1-pons-v1-lifecycle-eligibility" in content
    assert "phase1-pons-v2-lifecycle-eligibility" in content
    assert "phase1-pons-representative-transfers-full" in content
    assert "phase1-pons-representative-market-paths" in content
    assert "market_path_run_id" in content
    assert "phase1-pons-representative-priced-paths" in content
    assert "priced_path_run_id" in content
    assert "pons-representative-priced-path-summary.jsonl" in content
    assert "phase1-pons-representative-dex-crosscheck" in content
    assert "phase1-pons-representative-explorer-crosscheck" not in content
    assert "explorer_crosscheck_run_id" not in content
    assert "pons-representative-explorer-token-summary.jsonl" not in content
    assert "build_representative_validation_rows" in content
    assert "summarize_representative_validation" in content
    assert "validate_representative_coverage_report" in content
    assert "pons-representative-source-coverage.jsonl" in content
    assert "source_coverage_sha256" in content
    assert "representative market path V1 venue run mismatch" in content
    assert "representative market path V2 venue run mismatch" in content
    assert "representative V1 lifecycle/market venue run mismatch" in content
    assert "representative V2 lifecycle/market venue run mismatch" in content
    assert "representative lifecycle venue provenance missing" in content
    assert "v1_v3_run_id:" in content
    assert "v2_v4_run_id:" in content
    assert 'v1_v3_run = int("${{ inputs.v1_v3_run_id }}")' in content
    assert 'v2_v4_run = int("${{ inputs.v2_v4_run_id }}")' in content
    for source_input in (
        "registry_run_id:",
        "v2_curve_run_id:",
        "transition_run_id:",
        "quote_audit_run_id:",
        "anchor_run_id:",
        "oracle_run_id:",
        "fallback_run_id:",
    ):
        assert source_input in content
    assert "representative market path {field} mismatch" in content
    assert "representative priced path {field} mismatch" in content
    assert "representative DEX registry run mismatch" in content
    assert "representative DEX transition run mismatch" in content
    assert "v1_eligibility_sha256" in content
    assert "v2_eligibility_sha256" in content
    assert "runner_smoke_run_id" in content
    assert "runner_smoke_universe_sha256" in content
    assert "runner_smoke_outcomes_sha256" in content
    assert "representative validation runner smoke run mismatch" in content
    assert "representative validation runner smoke universe SHA mismatch" in content
    assert "representative validation runner smoke outcomes SHA mismatch" in content
    assert "representative validation sample V1/V3 lineage mismatch" in content
    assert "representative validation sample V2/V4 lineage mismatch" in content
    assert 'sample_summary.get("validated_v1_v3_run_id", -1)' in content
    assert 'sample_summary.get("validated_v2_v4_run_id", -1)' in content
    assert "require_representative_sample_identity" in content
    assert "sample identity " in content
    assert "mismatch: {field}" in content
    assert '"sample_sha256": sample_identity["sample_sha256"]' in content
    assert '"token_set_sha256": sample_identity["token_set_sha256"]' in content
    assert "pons-v1-lifecycle-eligibility.jsonl.manifest.json" in content
    assert "pons-v2-lifecycle-eligibility.jsonl.manifest.json" in content
    assert "representative validation must contain exactly 10" in content
    assert "id: upload_representative" in content
    assert "id: retry_upload_representative" in content
    assert "Retry representative validation artifact upload" in content
    assert "Final representative validation artifact upload retry" in content
    for source in (
        "sample",
        "v1",
        "v2",
        "transfers",
        "market_paths",
        "priced_paths",
        "dex",
    ):
        assert content.count(f"id: download_{source}") == 1, source
        assert content.count(f"id: retry_download_{source}") == 1, source
        assert content.count(
            f"steps.download_{source}.outcome == 'failure'"
        ) == 2, source
        assert content.count(
            f"steps.retry_download_{source}.outcome == 'failure'"
        ) == 2, source
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "time.sleep(" not in content


def test_representative_chain_preflights_frozen_support_before_sample():
    content = _workflow("phase1-pons-representative-evidence-chain.yml")
    assert "Verify frozen representative support inputs" in content
    assert "representative support run IDs changed" in content
    assert "representative quote audit artifact changed" in content
    assert "representative support run is not successful" in content
    assert "representative support workflow path changed" in content
    assert "representative support branch changed" in content
    assert "representative support artifact missing or expired" in content
    assert "representative eligibility run is not successful" in content
    assert "representative eligibility branch changed" in content
    assert "representative eligibility artifacts missing" in content
    assert "representative {label} artifact missing" in content
    assert "phase1-pons-live-venue-rescue-one-shot.yml/runs" in content
    assert "representative chain cannot overlap active venue rescue" in content
    assert "Verify lifecycle venue provenance before representative RPC" in content
    assert "representative lifecycle venue provenance missing" in content
    assert "representative lifecycle venue provenance mismatch" in content
    assert "pons-v1-lifecycle-eligibility.jsonl.manifest.json" in content
    assert "pons-v2-lifecycle-eligibility.jsonl.manifest.json" in content
    assert "sample:" in content
    assert "needs: preflight" in content
    assert "needs.preflight.result == 'success'" in content
    for token in (
        "phase1-pons-stock-oracle-promote-v2-delta-one-shot.yml",
        "phase1-pons-stock-oracle-full",
        "phase1-pons-research-smoke.yml",
        "phase1-pons-research-smoke",
        "phase1-pons-v1-registry-recovery.yml",
        "phase1-pons-full-registry-recovered",
        "phase1-pons-v2-curve-gap-recovery-optimized-one-shot.yml",
        "phase1-pons-v2-curve-full",
        "phase1-pons-v2-transition-full.yml",
        "phase1-pons-v2-transition-full",
        "phase1-pons-quote-audit-one-shot.yml",
        "phase1-pons-full-quote-audit-current",
        "phase1-pons-anchor-promote-recovered-one-shot.yml",
        "phase1-pons-weth-usdg-anchor-full",
    ):
        assert token in content


def test_live_acquisition_checkpoint_launcher_is_pinned_and_artifact_only():
    content = _workflow(
        "phase1-pons-live-acquisition-checkpoint-one-shot.yml"
    )
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "push:" in trigger_block
    assert "workflow_dispatch:" not in trigger_block
    assert "launch live acquisition checkpoint" in content
    assert 'run_ids_json: "[33982556591]"' in content
    assert 'require_successful_runs: false' in content
    assert "phase1-pons-acquisition-accounting.yml" in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "RpcClient" not in content
    assert "time.sleep(" not in content


def test_live_venue_rescue_launcher_is_pinned_guarded_and_two_wave():
    content = _workflow("phase1-pons-live-venue-rescue-one-shot.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "push:" in trigger_block
    assert "workflow_dispatch:" not in trigger_block
    assert "launch V1 V3 rescue" in content
    assert "launch V2 V4 rescue" in content
    assert content.count(
        "startsWith(github.event.head_commit.message, 'launch V1 V3 rescue')"
    ) == 3
    assert content.count(
        "startsWith(github.event.head_commit.message, 'launch V2 V4 rescue')"
    ) == 3
    assert "contains(github.event.head_commit.message, 'launch V" not in content
    assert "live venue rescue is blocked while source parent is active" in content
    assert "live venue rescue is unnecessary for complete source " in content
    assert "requested_artifacts" in content
    assert "phase1-pons-v1-v3-full" in content
    assert "phase1-pons-v2-v4-full" in content
    assert "live venue rescue requires exactly one venue target" in content
    assert "live venue rescue is blocked while another rescue " in content
    assert "group: phase1-pons-live-venue-rescue-${{ github.ref }}" in content
    assert "cancel-in-progress: false" in content
    assert "active_siblings" in content
    assert "fresh_active_siblings = []" in content
    assert "live venue rescue fresh sibling pagination " in content
    assert "live venue rescue sibling state changed before " in content
    assert '"fresh_active_sibling_rescues": fresh_active_siblings' in content
    assert "terminal_target_runs" in content
    assert "terminal_target_runs.sort(" in content
    assert 'key=lambda row: int(row["id"])' in content
    assert "reverse=True" in content
    assert "prior_plan_artifact" in content
    assert "prior_gap_prefix" in content
    assert "prior_gap_pattern = re.compile(" in content
    assert "re.escape(prior_gap_prefix)" in content
    assert 'r"(\\d+)$"' in content
    assert "prior_gap_pattern.fullmatch(name)" in content
    assert "successful_repair_gap_ids" in content
    assert "live venue rescue job pagination exceeded 1000" in content
    assert 'str(row.get("conclusion") or "") == "success"' in content
    assert "artifact_gap_ids = set()" in content
    assert "reusable_gap_ids = sorted(" in content
    assert "successful_gap_ids & artifact_gap_ids" in content
    assert "successful_gap_ids - artifact_gap_ids" in content
    assert "artifact_gap_ids - successful_gap_ids" in content
    assert '"reusable_gap_count": len(reusable_gap_ids)' in content
    assert '"missing_success_artifacts"' in content
    assert '"non_success_gap_artifacts"' in content
    assert "prior_reusable_gap_count=" in content
    assert "prior_missing_success_artifacts=" in content
    assert "prior_non_success_gap_artifacts=" in content
    assert "Venue rescue terminal preflight" in content
    assert "requested_artifact" in content
    assert "LAUNCH_MESSAGE: ${{ github.event.head_commit.message }}" in content
    assert "LAUNCH_VALIDATION_GENERATION: '10'" in content
    assert "VALIDATION_GENERATION: ${{ env.LAUNCH_VALIDATION_GENERATION }}" in content
    assert 'os.environ["VALIDATION_GENERATION"]' in content
    assert "requested_generation + 7" in content
    assert "V2/V4 rescue validation generation changed: " in content
    assert '"validation_generation": validation_generation' in content
    assert "BEFORE_SHA: ${{ github.event.before }}" in content
    assert "CURRENT_SHA: ${{ github.sha }}" in content
    assert 're.fullmatch(r"[0-9a-f]{40}", before_sha)' in content
    assert 're.fullmatch(r"[0-9a-f]{40}", current_sha)' in content
    assert 'f"/repos/{repo}/commits/{current_sha}"' in content
    assert "launch must be a direct " in content
    assert "launch commit must change " in content
    assert "exactly one file" in content
    assert "phase1-pons-live-venue-rescue-one-shot.yml" in content
    assert "launch commit changed the " in content
    assert "launch wrapper status changed" in content
    assert "changed_lines = [" in content
    assert "LAUNCH_VALIDATION_GENERATION: '(\\d+)'" in content
    assert "launch commit contains " in content
    assert "non-marker changes" in content
    assert "launch marker diff changed" in content
    assert "launch marker must increment " in content
    assert "by exactly one" in content
    assert "launch marker does not match " in content
    assert '"launch_commit_sha": current_sha' in content
    assert '"launch_parent_sha": before_sha' in content
    assert '"launch_marker_from": old_validation_generation' in content
    assert '"launch_marker_to": new_validation_generation' in content
    assert "# validation-generation:" not in content
    assert "generation_pattern = re.compile(" in content
    assert 'r" generation (\\d+)$"' in content
    assert 'r" generation (\\d+)(?:\\b|$)"' not in content
    assert "generation_pattern.fullmatch(display_title)" in content
    assert "display_title.startswith(launch_marker)" not in content
    assert "launch requires an explicit " in content
    assert "raw_launch_message = str(" in content
    assert "raw_launch_message != launch_message" in content
    assert "launch message must be exactly " in content
    assert '"one line"' in content
    assert "target_plan_job_name = (" in content
    assert '"v1_v3_rescue / plan"' in content
    assert '"v2_v4_rescue / plan"' in content
    assert "def target_plan_succeeded(source_run_id):" in content
    assert "?filter=all&per_page=100&page={page}" in content
    assert "generation-plan job " in content
    assert "consumed_generation_runs = {}" in content
    assert "unconsumed_terminal_generations = []" in content
    assert "target_plan_succeeded(int(row[\"id\"]))" in content
    assert "ambiguous_consumed_generations = {" in content
    assert "len(set(run_ids)) > 1" in content
    assert "consumed generation history " in content
    assert "consumed_generations = sorted(" in content
    assert "max(consumed_generations, default=0) + 1" in content
    assert '"consumed_generations": consumed_generations' in content
    assert '"consumed_generation_runs": {' in content
    assert "consumed generation runs:" in content
    assert '"unconsumed_terminal_generations": (' in content
    assert "consumed generations:" in content
    assert "unconsumed terminal generations:" in content
    assert "live venue rescue generation is not monotonic: " in content
    assert "expected_prior_consumed_run_id = \"\"" in content
    assert "requested_generation >= 2" in content
    assert "prior_generation = requested_generation - 1" in content
    assert "consumed_generation_runs.get(prior_generation, [])" in content
    assert 'venue_label = "V1/V3" if rescue_v1 else "V2/V4"' in content
    assert "next rescue generation requires " in content
    assert "exactly one consumed immediate prior generation" in content
    assert "is_expected_consumed_prior" in content
    assert "can_select_plan_only" in content
    assert "next rescue generation did not select " in content
    assert "the immediate consumed prior run" in content
    assert '"requested_generation": requested_generation' in content
    assert '"expected_generation": expected_generation' in content
    assert "rescue_v2 and requested_generation == 3" in content
    assert "expected_prior_run_id = 34_234_471_190" in content
    assert "0e146b6f46491caab81f00a241fd29611a252c4c" in content
    assert "launch V2 V4 rescue generation 2" in content
    assert "V2/V4 generation 3 pinned prior run is unavailable" in content
    assert "V2/V4 generation 3 prior launch SHA changed" in content
    assert "V2/V4 generation 3 prior launch title changed" in content
    assert "V2/V4 generation 3 must reuse pinned generation 2 run" in content
    assert "selected_prior_row = None" in content
    assert "selected_prior_reusable_gap_ids = []" in content
    assert "prior_terminal_snapshot = None" in content
    assert "selected prior rescue is not terminal on fresh snapshot" in content
    assert "selected prior rescue identity changed during " in content
    assert "fresh_artifacts = artifacts(" in content
    assert "prior_plan_artifact not in fresh_artifacts" in content
    assert "selected prior rescue plan artifact disappeared " in content
    assert 'str(fresh_prior.get("conclusion") or "") == "success"' in content
    assert "requested_artifact in fresh_artifacts" in content
    assert "fresh prior snapshot is canonically complete: " in content
    assert '"plan_artifact_present": (' in content
    assert '"canonical_artifact_present": (' in content
    assert "fresh_successful_gap_ids" in content
    assert "repair_job_terminal_snapshot" in content
    assert "repair_job_pattern = re.compile(" in content
    assert "?filter=all&per_page=100&page={page}" in content
    assert "live venue rescue terminal job pagination " in content
    assert "selected prior rescue still has nonterminal " in content
    assert '"repair_job_count": fresh_job_snapshot[' in content
    assert '"repair_job_counts": fresh_job_snapshot["counts"]' in content
    assert "gap_id_counts = {}" in content
    assert "gap_id_counts.get(gap_id, 0) + 1" in content
    assert "duplicate_gap_ids = sorted(" in content
    assert "selected prior rescue has duplicate repair gap " in content
    assert '"duplicate_repair_gap_ids": fresh_job_snapshot[' in content
    assert '"repair_nonterminal_count": len(' in content
    assert "fresh_reusable_gap_ids = sorted(" in content
    assert "selected prior rescue reconciliation changed " in content
    assert '"run_attempt": fresh_prior.get("run_attempt")' in content
    assert '"updated_at": fresh_prior.get("updated_at")' in content
    assert '"prior_terminal_snapshot": prior_terminal_snapshot' in content
    assert "import hashlib" in content
    assert "prior_terminal_binding = {" in content
    assert "prior_terminal_snapshot_sha256 = hashlib.sha256(" in content
    assert '"snapshot_binding_sha256": (' in content
    assert "prior_terminal_snapshot_sha256=" in content
    assert "steps.guard.outputs.prior_terminal_snapshot_sha256" in content
    assert (
        "expected_prior_terminal_snapshot_sha256: "
        "${{ needs.preflight.outputs.prior_terminal_snapshot_sha256 }}"
        in content
    )
    assert "V2/V4 generation 3 fresh prior snapshot is missing" in content
    assert "V2/V4 generation 3 fresh prior launch SHA changed" in content
    assert "V2/V4 generation 3 fresh prior launch title changed" in content
    assert '"live venue rescue is unnecessary because prior "' in content
    assert '"successful canonical rescue is complete: "' in content
    assert 'str(candidate.get("conclusion") or "") == "success"' in content
    assert "requested_artifact in candidate_artifacts" in content
    assert "requested_artifacts = {requested_artifact}" in content
    assert "and (has_gap or can_select_plan_only)" in content
    assert "prior_gap_run_id = candidate_id" in content
    prior_selection = content.split(
        "successful_gap_ids = successful_repair_gap_ids(",
        1,
    )[1].split("requested_artifacts = {requested_artifact}", 1)[0]
    assert 'candidate["conclusion"]' not in prior_selection
    assert "candidate.get(\"conclusion\")" not in prior_selection
    assert 'prior_gap_run_id: ${{ needs.preflight.outputs.prior_gap_run_id }}' in content
    assert content.count(
        'prior_gap_run_id: ${{ needs.preflight.outputs.prior_gap_run_id }}'
    ) == 2
    assert (
        "expected_prior_reusable_gap_count: "
        "${{ needs.preflight.outputs.prior_reusable_gap_count }}"
        in content
    )
    assert content.count(
        "expected_prior_reusable_gap_count: "
        "${{ needs.preflight.outputs.prior_reusable_gap_count }}"
    ) == 2
    assert content.count(
        "expected_prior_terminal_snapshot_sha256: "
        "${{ needs.preflight.outputs.prior_terminal_snapshot_sha256 }}"
    ) == 2
    assert 'prior_gap_run_id: ""' not in content
    assert "steps.guard.outputs.prior_gap_run_id" in content
    assert "steps.guard.outputs.prior_reusable_gap_count" in content
    assert "steps.guard.outputs.prior_missing_success_artifacts" in content
    assert "steps.guard.outputs.prior_non_success_gap_artifacts" in content
    assert "GITHUB_OUTPUT" in content
    assert "GITHUB_STEP_SUMMARY" in content
    assert "import urllib.error" in content
    assert "transient_http_codes = {" in content
    for code in ("403", "408", "409", "425", "429", "500", "502", "503", "504"):
        assert code in content
    assert "def get(path, attempts=3):" in content
    assert "attempt_count <= 0" in content
    assert "urllib.error.HTTPError" in content
    assert "urllib.error.URLError" in content
    assert "attempt + 1 < attempt_count" in content
    assert "live venue rescue GitHub API retry loop exhausted" in content
    assert "CURRENT_RUN_ID: ${{ github.run_id }}" in content
    assert "BRANCH: ${{ github.ref_name }}" in content
    assert "phase1-pons-live-venue-rescue-one-shot.yml" in content
    assert "live venue rescue run pagination exceeded 1000" in content
    assert '"rescue_target": (' in content
    assert "missing_requested_artifacts" in content
    assert "live venue rescue source workflow path changed" in content
    assert "live venue rescue source branch changed" in content
    assert "live venue rescue launch branch changed" in content
    assert "live venue rescue source launch commit changed" in content
    assert "c53b3a63156976a5873752c332fa7578011249b0" in content
    assert "phase1-pons-full-eligibility-acquisition-one-shot.yml" in content
    assert content.count("needs: preflight") == 2
    assert content.count("needs.preflight.result == 'success'") == 2
    assert content.count('partial_run_id: "33982556591"') == 2
    assert 'source_registry_run_id: "33911022718"' in content
    assert 'transition_run_id: "33912452330"' in content
    assert content.count('max_gap_blocks: "50000"') == 2
    assert "phase1-pons-v1-v3-recover-gaps.yml" in content
    assert "phase1-pons-v2-v4-recover-gaps.yml" in content
    assert "time.sleep(" not in content


def test_eligible_universe_promotion_is_artifact_only_and_reusable():
    content = _workflow("phase1-pons-eligible-universe-promote.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "phase1-pons-eligible-universe-freeze.yml" in content
    assert content.count(
        "inputs.source_eligibility_run_id"
    ) == 2
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "RpcClient" not in content
    assert "time.sleep(" not in content


def test_eligible_universe_promotion_launcher_is_pinned_and_guarded():
    content = _workflow(
        "phase1-pons-eligible-universe-promote-one-shot.yml"
    )
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "push:" in trigger_block
    assert "workflow_dispatch:" not in trigger_block
    assert "launch eligible universe promotion" in content
    assert 'source_eligibility_run_id: "33982556591"' in content
    assert "phase1-pons-eligible-universe-promote.yml" in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content



def test_post_eligibility_evidence_handoff_is_guarded_and_reusable():
    chain = _workflow("phase1-pons-post-eligibility-evidence-chain.yml")
    trigger_block = chain.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "source eligibility parent is not completed successfully" in chain
    assert "phase1-pons-eligible-universe-promote.yml" in chain
    assert "phase1-pons-representative-evidence-chain.yml" in chain
    assert "phase1-pons-post-eligibility-evidence-ready" in chain
    assert '"recovery_mode": False' in chain
    assert "validate_post_eligibility_evidence_bundle" in chain
    assert "expected_lifecycle_run_id=source_run_id" in chain
    assert "expected_v1_v3_run_id=source_run_id" in chain
    assert "expected_v2_v4_run_id=source_run_id" in chain
    assert "**validation" in chain
    assert "id: upload_evidence_ready" in chain
    assert "id: retry_upload_evidence_ready" in chain
    assert "Retry evidence-ready artifact upload" in chain
    assert "Final evidence-ready artifact upload retry" in chain

    launcher = _workflow(
        "phase1-pons-post-eligibility-evidence-one-shot.yml"
    )
    assert ".github/phase1-pons-evidence-launch.txt" in launcher
    assert "launch Phase 1 evidence handoff" in launcher
    assert 'source_eligibility_run_id: "33982556591"' in launcher



def test_viability_guarded_route_is_evidence_gated_before_rpc():
    content = _workflow("phase1-pons-viability-guarded-route.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_call:" in trigger_block
    assert "workflow_dispatch:" not in trigger_block
    assert "\n  push:" not in trigger_block
    assert ".github/phase1-pons-viability-ready.json" in content
    assert ".github/phase1-pons-viability-runs.json" in content
    assert "viability evidence readiness is not armed" in content
    assert "viability run ledger is not armed" in content
    assert "viability run ledger evidence does not match readiness" in content
    assert "viability run ledger route set changed" in content
    assert "viability route already recorded in ledger" in content
    assert "viability route ledger run ID cannot be negative" in content
    assert "ROUTE: ${{ inputs.route }}" in content
    assert "33_982_556_591" in content
    assert "phase1-pons-post-eligibility-evidence-ready" in content
    assert "phase1-post-eligibility-evidence-ready.json" in content
    assert "evidence-ready retry artifacts are not equivalent" in content
    assert "evidence_artifact_id" in content
    assert (
        "artifact-ids: ${{ steps.check.outputs.evidence_artifact_id }}"
        in content
    )
    assert "evidence handoff lifecycle run ID must be positive" in content
    assert "normal_evidence_path = (" in content
    assert "recovered_evidence_path = (" in content
    assert "viability handoff evidence workflow path changed" in content
    assert "viability normal evidence is marked recovered" in content
    assert "normal evidence handoff routing changed" in content
    assert "viability recovered evidence is not marked recovered" in content
    assert 'evidence = get(' in content
    assert "evidence_path = str(" in content
    assert "evidence handoff snapshot head changed" in content
    assert "evidence handoff Pons launch count changed" in content
    assert "evidence handoff eligible universe is empty" in content
    assert "evidence handoff representative token count changed" in content
    for field in (
        "eligible_universe_sha256",
        "representative_validation_sha256",
        "representative_sample_sha256",
        "representative_token_set_sha256",
        "representative_source_coverage_sha256",
        "v1_eligibility_sha256",
        "v2_eligibility_sha256",
        "runner_smoke_universe_sha256",
        "runner_smoke_outcomes_sha256",
    ):
        assert field in content
    assert "evidence handoff hash is invalid" in content
    assert "evidence handoff runner-smoke run changed" in content
    assert "evidence handoff runner-smoke universe SHA changed" in content
    assert "evidence handoff runner-smoke outcomes SHA changed" in content
    assert '"evidence_hashes": evidence_hashes' in content
    assert "evidence lifecycle/pricing workflow path is not allowed" in content
    assert "evidence lifecycle/pricing run is missing fallback" in content
    assert "phase1-pons-v3-quote-fallback-full" in content
    assert "phase1-pons-v4-quote-fallback-full" in content
    assert "phase1-pons-quote-fallback-full" in content
    assert "quote_fallback_run_id" in content
    assert "evidence_run_id: ${{ steps.check.outputs.evidence_run_id }}" in content
    assert (
        "eligibility_run_id: ${{ needs.preflight.outputs.quote_fallback_run_id }}"
        in content
    )
    assert (
        "evidence_run_id: ${{ needs.preflight.outputs.evidence_run_id }}"
        in content
    )
    assert (
        "source_eligibility_run_id: "
        "${{ needs.preflight.outputs.source_eligibility_run_id }}"
        in content
    )
    assert (
        "\n      eligibility_run_id: "
        "${{ needs.preflight.outputs.source_eligibility_run_id }}"
        not in content
    )
    assert "phase1-pons-representative-validation" in content
    assert "phase1-pons-viability-route-measurement.yml" in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "time.sleep(" not in content


def test_viability_has_nine_individual_guarded_launchers():
    wrappers = {
        "pons_registry": "phase1-pons-viability-pons-registry-one-shot.yml",
        "pons_v1_v3": "phase1-pons-viability-pons-v1-v3-one-shot.yml",
        "pons_v2_curve": "phase1-pons-viability-pons-v2-curve-one-shot.yml",
        "pons_v2_transition": (
            "phase1-pons-viability-pons-v2-transition-one-shot.yml"
        ),
        "pons_v2_v4": "phase1-pons-viability-pons-v2-v4-one-shot.yml",
        "weth_usdg_anchor": (
            "phase1-pons-viability-weth-usdg-anchor-one-shot.yml"
        ),
        "stock_oracle": "phase1-pons-viability-stock-oracle-one-shot.yml",
        "quote_v3_fallback": (
            "phase1-pons-viability-quote-v3-fallback-one-shot.yml"
        ),
        "quote_v4_fallback": (
            "phase1-pons-viability-quote-v4-fallback-one-shot.yml"
        ),
    }
    assert len(wrappers) == 9
    for route, workflow in wrappers.items():
        content = _workflow(workflow)
        assert f"launch viability {route}" in content
        assert "phase1-pons-viability-guarded-route.yml" in content
        assert f'route: "{route}"' in content
        assert "sequence_id: ${{ github.sha }}" in content
        assert "cancel-in-progress: false" in content
        assert "workflow_dispatch:" not in content


def test_viability_ledger_finalizer_validates_nine_distinct_runs():
    content = _workflow(
        "phase1-pons-viability-ledger-finalize-one-shot.yml"
    )
    assert ".github/phase1-pons-viability-runs.json" in content
    assert ".github/phase1-pons-viability-ready.json" in content
    assert "viability ledger evidence run does not match readiness" in content
    assert "viability readiness source run changed" in content
    assert "launch Phase 1 final acceptance" in content
    assert "viability run ledger is not armed" in content
    assert "nine distinct route run IDs" in content
    assert "phase1-pons-post-eligibility-evidence-ready" in content
    assert "phase1-pons-eligible-universe" in content
    assert "phase1-pons-representative-validation" in content
    for workflow_name in (
        "phase1-pons-viability-pons-registry-one-shot",
        "phase1-pons-viability-pons-v1-v3-one-shot",
        "phase1-pons-viability-pons-v2-curve-one-shot",
        "phase1-pons-viability-pons-v2-transition-one-shot",
        "phase1-pons-viability-pons-v2-v4-one-shot",
        "phase1-pons-viability-weth-usdg-anchor-one-shot",
        "phase1-pons-viability-stock-oracle-one-shot",
        "phase1-pons-viability-quote-v3-fallback-one-shot",
        "phase1-pons-viability-quote-v4-fallback-one-shot",
    ):
        assert workflow_name in content
    assert 'run.get("path")' in content
    assert "viability route workflow path mismatch" in content
    assert "viability route measurement artifacts missing" in content
    assert "json_file_at_ref" in content
    assert ".github/phase1-pons-viability-ready.json" in content
    assert ".github/phase1-pons-viability-runs.json" in content
    assert "viability route evidence changed since launch" in content
    assert "viability route ledger evidence changed since launch" in content
    assert "viability route launch slot was not empty" in content
    assert "require_ancestor" in content
    assert "head is not an ancestor of finalizer HEAD" in content
    assert '"route_launch_evidence_bound": True' in content
    assert '"evidence_and_routes_are_ancestors": True' in content
    assert "phase1-pons-viability-measurement-pons_registry-primary" in content
    assert "phase1-pons-viability-measurement-pons_registry-secondary" in content
    assert "artifact_names(run_id)" in content
    assert 'run.get("name") != expected[route]' not in content
    assert "phase1-pons-final-acceptance-chain.yml" in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "time.sleep(" not in content


def test_phase1_readiness_audit_is_artifact_only_and_guarded():
    content = _workflow("phase1-pons-readiness-audit.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "phase1-pons-viability-ready.json" in content
    assert "phase1-pons-viability-runs.json" in content
    assert "phase1-readiness-report.json" in content
    assert "phase1-pons-readiness-audit" in content
    assert "build_phase1_readiness_report" in content
    assert "Resolve armed evidence run and exact handoff artifact" in content
    assert "phase1-pons-post-eligibility-evidence-ready" in content
    assert "readiness evidence-ready retry artifacts are not " in content
    assert "equivalent" in content
    assert "evidence_artifact_id" in content
    assert (
        "artifact-ids: ${{ steps.evidence.outputs.evidence_artifact_id }}"
        in content
    )
    assert "phase1-post-eligibility-evidence-ready.json" in content
    assert "evidence_handoff=evidence_handoff" in content
    assert "evidence_handoff_errors" in content
    assert '"path": run.get("path")' in content
    assert "json_file_at_ref" in content
    assert "launch_readiness_evidence_run_id" in content
    assert "launch_ledger_evidence_run_id" in content
    assert "launch_route_slot" in content
    assert "launch_ledger_routes" in content
    assert "latest_recovery_run" in content
    assert "recovery_discovery" in content
    assert "reject_recovery_candidate" in content
    assert '"completed_success_candidates": 0' in content
    assert '"selected_run_id": 0' in content
    assert '"active_run": None' in content
    assert '"latest_terminal_run": None' in content
    assert "def job_diagnostics(run_id):" in content
    assert '"problem_jobs": problem_jobs' in content
    assert '"repair_wave_counts": repair_wave_counts' in content
    assert 'wave_marker = "/ recover_"' in content
    assert 'wave_text in {"1", "2", "3", "4"}' in content
    assert 'matrix_marker = (' in content
    assert 'f"/ recover_{wave_text} ("' in content
    assert "def recovery_progress(venue, run_id, diagnostics):" in content
    assert '"repair_progress": active_progress' in content
    assert '"repair_progress": terminal_progress' in content
    assert 'planned_repairs = int(plan["gap_job_count"])' in content
    assert '"planned_repairs": planned_repairs' in content
    assert '"materialized_repairs": materialized_repairs' in content
    assert '"successful_repairs": successful_repairs' in content
    assert "materialized={repair_progress.get('materialized_repairs', 0)}/" in content
    assert "materialized={terminal_progress.get('materialized_repairs', 0)}/" in content
    assert '"failed_repairs": failed_repairs' in content
    assert '"remaining_repairs": remaining_repairs' in content
    assert '"progress_percent": progress_percent' in content
    assert '"current_wave": current_wave' in content
    assert "first_unresolved_wave" in content
    assert 'state = "failed"' in content
    assert 'state = "incomplete"' in content
    assert 'state = "active"' in content
    assert 'current_wave is None and state == "active"' in content
    assert "current_wave = first_unresolved_wave" in content
    assert '"job_plan_drift"' in content
    assert '"over_materialized"' in content
    assert '"unexpected_jobs"' in content
    assert "Repair progress:" in content
    assert "Terminal repair progress:" in content
    assert "Repair waves:" in content
    assert "if key in failed_states and len(problem_jobs) < 20:" in content
    assert 'diagnostics["latest_terminal_run"] is None' in content
    assert '"conclusion": row.get("conclusion")' in content
    assert "Latest terminal rescue" in content
    assert "Problem jobs:" in content
    assert '"launch V1 V3 rescue"' in content
    assert '"launch V2 V4 rescue"' in content
    assert "launch_pattern = re.compile(" in content
    assert 'r" generation (\\d+)$"' in content
    assert 'r" generation (\\\\d+)$"' not in content
    assert "re.escape(launch_marker)" in content
    assert "launch_pattern.fullmatch(display_title)" in content
    assert "if not display_title.startswith(" not in content
    assert "launch_marker" in content
    assert 'row.get("display_title") or ""' in content
    assert '"display_title": display_title' in content
    assert 'diagnostics["active_run"] is None' in content
    assert "active_jobs = job_diagnostics(active_run_id)" in content
    assert '"**active_jobs"' not in content
    assert "**active_jobs" in content
    assert "Active rescue {active_run.get('run_id', 0)}" in content
    assert '"rejection_counts": {}' in content
    assert '"rejected_candidates": []' in content
    assert "if len(rejected) < 20:" in content
    assert '"workflow_path_mismatch"' in content
    assert '"canonical_artifact_missing"' in content
    assert '"manifest_invalid"' in content
    assert '"lineage_invalid"' in content
    assert 'diagnostics["selected_run_id"] = run_id' in content
    assert "Recovery discovery {venue}" in content
    assert "completed-success-candidates=" in content
    assert "recovery run pagination exceeded 1000" in content
    assert "per_page=100&page={page}" in content
    assert "recovery_manifest_valid" in content
    assert "select_equivalent_artifact_retry" in content
    assert "resolve_v1_v3_canonical_shard_bindings" in content
    assert "resolve_v2_v4_canonical_shard_bindings" in content
    assert "artifact_rows_cache = {}" in content
    assert "if run_id in artifact_rows_cache:" in content
    assert "selected_recovery_shards_resolvable" in content
    assert 'if venue == "v1_v3"' in content
    assert 'f"readiness selected {venue_label} shard "' in content
    assert "return selected_recovery_shards_resolvable(" in content
    assert '"pons-v1-v3-full.jsonl"' in content
    assert '"pons-v2-v4-full.jsonl"' in content
    assert "expected_filter_semantics = (" in content
    assert "global V3 Initialize/Swap topic scan followed by " in content
    assert "PoolManager Initialize/Swap global topic scan followed " in content
    assert 'provenance.get("filter_semantics")' in content
    assert 'records = int(manifest.get("records", -1))' in content
    assert 'digest = str(manifest.get("sha256") or "")' in content
    assert 'manifest.get("path") != expected_data_name' in content
    assert 'if records < 0:' in content
    assert 'len(digest) != 64' in content
    assert 'char not in "0123456789abcdef"' in content
    assert "zipfile.BadZipFile" in content
    assert "json.JSONDecodeError" in content
    assert "UnicodeDecodeError" in content
    assert content.count(
        'if not isinstance(manifest.get("provenance"), dict):'
    ) == 2
    assert "except (TypeError, ValueError):" in content
    assert "recovery_lineage_valid" in content
    assert "validate_gap_plan_jobs" in content
    assert content.count("validate_gap_plan_jobs(") == 3
    assert "phase1-pons-v1-v3-gap-plan" in content
    assert "v1-v3-gap-plan.json" in content
    assert "phase1-pons-v2-v4-gap-plan" in content
    assert "v4-gap-plan.json" in content
    assert "pons-v1-v3-summary.json" in content
    assert "pons-v2-v4-summary.json" in content
    assert "embedded_plan != current_plan" in content
    assert 'summary.get("snapshot_head_block", -1)' in content
    assert 'summary.get("records", -1)' in content
    assert 'summary.get("tape_sha256") or ""' in content
    assert 'summary.get(membership_field, -1)' in content
    assert 'summary.get(matched_field, -1)' in content
    assert 'summary.get(missing_field, -1)' in content
    assert 'summary.get("source_files", 0)' in content
    assert 'provenance.get("shards")' in content
    assert 'summary.get("candidate_source_files", -1)' in content
    assert '"dropped_overlapping_source_files"' in content
    assert "source_files != len(shards)" in content
    assert "candidate_source_files < source_files" in content
    assert "candidate_source_files - source_files" in content
    assert '"registered_pools"' in content
    assert '"registered_pool_ids"' in content
    assert "268_688" in content
    assert "3_638" in content
    assert 'current_plan.get("prior_gap_run_id") or 0' in content
    assert '"partial_run_id" not in current_plan' in content
    assert '"prior_gap_run_id" not in current_plan' in content
    assert "if prior_gap_id == 0:" in content
    assert content.index("current_plan = artifact_json(") < content.index(
        "if prior_gap_id == 0:"
    )
    assert '"partial_run_id" not in prior_plan' in content
    assert '"prior_gap_run_id" not in prior_plan' in content
    assert "if cursor in seen:" in content
    assert "if depth > 20:" in content
    assert "pons-v1-v3-full.jsonl.manifest.json" in content
    assert "pons-v2-v4-full.jsonl.manifest.json" in content
    assert "manifest_gap_aware_v1_v3_recovery" in content
    assert "manifest_gap_aware_v4_recovery" in content
    assert '"partial_run_id", 0' in content
    assert "33_982_556_591" in content
    assert "33_911_022_718" in content
    assert "33_912_452_330" in content
    assert content.count("fetch_github_actions_artifact_zip(") == 1
    assert '"recovery_manifest_valid"] = True' in content
    assert '"recovery_lineage_valid"] = True' in content
    assert "RECOVERY_VENUE_ARTIFACTS" in content
    assert "RECOVERY_VENUE_WORKFLOW_PATHS" in content
    assert "recovery_runs=recovery_runs" in content
    assert "active_recovery_run_ids = {" in content
    assert "active_recovery_run_ids=active_recovery_run_ids" in content
    assert "Recovery run IDs:" in content
    assert "successful_job_artifact_missing" in content
    assert "artifact_without_successful_job" in content
    assert "unexpected_gap_artifacts" in content
    assert "malformed_gap_artifact_names" in content
    assert "duplicate_repair_job_ids" in content
    assert "artifacts_without_successful_jobs" in content
    assert "artifacts_with_active_jobs" in content
    assert "active_job_states" in content
    assert '"queued"' in content
    assert '"in_progress"' in content
    assert "successful_job_ids - observed_artifact_ids" in content
    assert "(observed_artifact_ids & expected_gap_ids)" in content
    assert "artifact_candidate_ids - active_job_ids" in content
    assert "artifact_candidate_ids & active_job_ids" in content
    assert "in-flight=" in content
    assert "artifact-without-success=" in content
    assert "invalid_finalizers" in content
    assert "finalizer_head_sha" in content
    assert "launch_readiness_source_run_id" in content
    assert "launch_ledger_generation" in content
    assert "VIABILITY_ROUTE_WORKFLOW_PATHS" in content
    assert "VIABILITY_ROUTE_WORKFLOWS" not in content
    assert "job_counts(run_id)" in content
    assert "33982556591" in content
    assert '"&per_page=100&page=1"' in content
    assert "finalizer run pagination exceeded" not in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "RpcClient" not in content
    assert "time.sleep(" not in content

    launcher = _workflow("phase1-pons-readiness-audit-one-shot.yml")
    assert "launch Phase 1 readiness audit" in launcher
    assert 'source_eligibility_run_id: "33982556591"' in launcher
    assert "phase1-pons-readiness-audit.yml" in launcher
    assert "workflow_dispatch:" not in launcher


def test_phase1_pass_closeout_is_guarded_artifact_only_and_pr_pinned():
    content = _workflow("phase1-pons-pass-closeout-one-shot.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "push:" in trigger_block
    assert "workflow_dispatch:" not in trigger_block
    assert ".github/phase1-pons-pass-closeout.json" in content
    assert "launch Phase 1 PASS closeout" in content
    assert "phase1-pons-acceptance-gate" in content
    assert "phase1-acceptance-report.json" in content
    assert "Read frozen PASS run and exact acceptance artifact" in content
    assert "Phase 1 closeout acceptance retry artifacts " in content
    assert "are not equivalent" in content
    assert "acceptance_artifact_id" in content
    assert (
        "artifact-ids: ${{ steps.config.outputs.acceptance_artifact_id }}"
        in content
    )
    assert 'report.get("phase1_acceptance_status") != "pass"' in content
    assert "hlp-v1-phase1-data-viability" in content
    assert "331_011_903" in content
    assert "phase1-pons-viability-ledger-finalize-one-shot.yml" in content
    assert '["git", "merge-base", "--is-ancestor"' in content
    assert ".github/phase1-pons-pass-closeout.json" in content
    assert "docs/project-state.md" in content
    assert "code changed after Phase 1 PASS evidence" in content
    assert "## Phase 1 remaining gates" in content
    assert '"- [ ]" in gate_section' in content
    assert "Phase 1 PASS run is not recorded in project-state" in content
    assert 'get(f"/repos/{repo}/pulls/3")' in content
    assert 'pr.get("state") != "open"' in content
    assert 'pr.get("draft") is not True' in content
    assert '!= "phase1/data-acquisition-spike"' in content
    assert '!= "main"' in content
    assert "PR 3 head moved while Phase 1 closeout was running" in content
    assert "safe_to_mark_pr_ready" in content
    assert "safe_to_merge_after_required_checks" in content
    assert "phase1-pons-pass-closeout" in content
    assert "id: upload_closeout" in content
    assert "id: retry_upload_closeout" in content
    assert "Retry Phase 1 closeout artifact upload" in content
    assert "Final Phase 1 closeout artifact upload retry" in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "RpcClient" not in content
    assert "time.sleep(" not in content


def test_recovered_completion_chain_is_terminal_gated_and_resumable():
    content = _workflow("phase1-pons-recovered-completion-chain.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "33982556591" in content
    assert "recovered completion cannot start before source is terminal" in content
    assert "recovered completion is unnecessary after complete " in content
    assert "missing_source_artifacts" in content
    assert "required_source_artifacts" in content
    assert "phase1-pons-full-eligibility-acquisition-one-shot.yml" in content
    assert "phase1-pons-live-venue-rescue-one-shot.yml" in content
    assert "phase1-pons-v1-v3-recover-gaps.yml" in content
    assert "phase1-pons-v2-v4-recover-gaps.yml" in content
    assert "phase1-pons-v1-v3-full" in content
    assert "phase1-pons-v2-v4-full" in content
    assert "inputs.v2_v4_run_id == ''" in content
    assert "pricing_run_id:" in content
    assert "reused pricing requires an explicit V2/V4 run ID" in content
    assert "recovered completion support run IDs changed" in content
    assert "recovered completion support run is not successful" in content
    assert "recovered completion support workflow path changed" in content
    assert "recovered completion support branch changed" in content
    assert "recovered completion support artifact missing or" in content
    for run_id in (
        "33_974_681_334",
        "33_920_762_592",
        "33_911_022_718",
        "33_936_232_604",
        "33_912_452_330",
        "33_923_299_711",
        "33_972_109_927",
    ):
        assert run_id in content
    assert "recovery source launch commit changed" in content
    assert "c53b3a63156976a5873752c332fa7578011249b0" in content
    assert "source already has complete V2/V4; set v2_v4_run_id" in content
    assert "source has reusable V2/V4 shards; recover source gaps" in content
    assert "source already has complete pricing; set pricing_run_id" in content
    assert "source_v2_shards" in content
    assert "recovery_manifest" in content
    assert "select_equivalent_artifact_retry" in content
    assert "resolve_v1_v3_canonical_shard_bindings" in content
    assert "resolve_v2_v4_canonical_shard_bindings" in content
    assert "artifact_rows_cache = {}" in content
    assert "if run_id in artifact_rows_cache:" in content
    assert 'venue_label = (' in content
    assert 'if venue_label == "V1/V3"' in content
    assert "shard_resolver = (" in content
    assert 'f"recovery {venue_label} canonical shard geometry "' in content
    assert '"recovered completion selected "' in content
    assert 'f"recovery {venue_label} selected shard artifact "' in content
    assert "is unavailable or ambiguous" in content
    assert "recovery venue retry artifacts are not equivalent" in content
    assert content.count("fetch_github_actions_artifact_zip(") == 1
    assert content.count("fetch_github_actions_json(") == 2
    assert "urllib.request.urlopen" not in content
    assert "decode_json=False" not in content
    assert content.count("id: download_reused_eligible") == 1
    assert content.count("id: retry_download_reused_eligible") == 1
    for source in ("eligible", "representative"):
        assert content.count(f"id: download_evidence_{source}") == 1, source
        assert content.count(
            f"id: retry_download_evidence_{source}"
        ) == 1, source
        assert content.count(
            f"steps.download_evidence_{source}.outcome == 'failure'"
        ) == 2, source
        assert content.count(
            f"steps.retry_download_evidence_{source}.outcome == 'failure'"
        ) == 2, source
    assert "actions/checkout@v4" in content
    assert "python -m pip install -e ." in content
    assert "pons-v1-v3-full.jsonl.manifest.json" in content
    assert "pons-v2-v4-full.jsonl.manifest.json" in content
    assert "manifest_gap_aware_v1_v3_recovery" in content
    assert "manifest_gap_aware_v4_recovery" in content
    assert "expected_filter_semantics" in content
    assert "global V3 Initialize/Swap topic scan followed by " in content
    assert "PoolManager Initialize/Swap global topic scan followed " in content
    assert "recovery venue manifest filter semantics changed" in content
    assert "recovery venue manifest path changed" in content
    assert "recovery venue manifest record count is invalid" in content
    assert "recovery venue manifest SHA-256 is invalid" in content
    assert 'manifest_name.removesuffix(' in content
    assert 'len(manifest_digest) != 64' in content
    assert 'char not in "0123456789abcdef"' in content
    assert "recovery venue partial run does not match frozen" in content
    assert "recovery lineage plan" in content
    assert "identity is ambiguous: " in content
    assert "recovery venue plan lacks bound lineage metadata" in content
    assert "recovery venue plan metadata is invalid" in content
    assert "recovery venue plan snapshot changed" in content
    assert "recovery venue plan start block changed" in content
    assert "validate_gap_plan_jobs" in content
    assert content.count("validate_gap_plan_jobs(") == 2
    assert "recovery venue plan structure changed: " in content
    assert "recovery_artifact_json" in content
    assert "recovery venue embedded plan" in content
    assert "recovery venue summary" in content
    assert "recovery venue embedded plan does not match lineage " in content
    assert "recovery venue summary snapshot changed" in content
    assert "recovery venue summary records changed" in content
    assert "recovery venue summary tape SHA changed" in content
    assert "recovery venue summary membership changed" in content
    assert "recovery venue summary matched membership changed" in content
    assert "recovery venue summary missing initialize changed" in content
    assert "recovery venue summary shard provenance changed" in content
    assert "recovery venue summary source file count changed" in content
    assert "recovery venue summary candidate file count " in content
    assert "recovery venue summary overlap accounting changed" in content
    assert 'summary.get("candidate_source_files", -1)' in content
    assert '"dropped_overlapping_source_files"' in content
    assert "source_files != len(shards)" in content
    assert "candidate_source_files - source_files" in content
    assert "recovery venue summary metadata is invalid" in content
    assert "pons-v1-v3-summary.json" in content
    assert "pons-v2-v4-summary.json" in content
    assert "268_688" in content
    assert "3_638" in content
    assert "recovery venue prior plan structure changed: " in content
    assert "recovery venue prior lineage is invalid" in content
    assert "if prior_gap_id == 0:" in content
    assert content.index("current_plan = recovery_plan(") < content.index(
        "if prior_gap_id == 0:"
    )
    assert "recovery venue manifest/plan prior lineage" in content
    assert "recovery venue prior lineage contains a cycle" in content
    assert "recovery venue prior lineage exceeds" in content
    assert "recovery venue prior plan lacks bound" in content
    assert "recovery venue prior partial run mismatch" in content
    assert "source_registry_run_id" in content
    assert "transition_run_id" in content
    assert "reused pricing run is missing lifecycle/fallback" in content
    assert "inputs.pricing_run_id == ''" in content
    assert "phase1-pons-pricing-eligibility-chain.yml" in content
    assert "phase1-pons-eligible-universe-promote.yml" in content
    assert "promote_reused_universe" in content
    assert "verify_reused_pricing" in content
    assert "reused pricing V1/V3 provenance mismatch" in content
    assert "reused pricing V2/V4 provenance mismatch" in content
    assert "reused pricing eligible universe remains incomplete" in content
    assert '"validated_v1_v3_run_id"' in content
    assert '"validated_v2_v4_run_id"' in content
    assert (
        "needs.verify_reused_pricing.result == 'success'"
        in content
    )
    assert (
        "inputs.pricing_run_id != '' && inputs.pricing_run_id || "
        "format('{0}', github.run_id)"
    ) in content
    assert "phase1-pons-representative-evidence-chain.yml" in content
    assert "v1_v3_run_id: ${{ inputs.v1_v3_run_id }}" in content
    assert (
        "inputs.v2_v4_run_id != '' && inputs.v2_v4_run_id || "
        "format('{0}', github.run_id)"
    ) in content
    assert "phase1-pons-eligible-universe" in content
    assert "phase1-pons-representative-validation" in content
    assert "phase1-pons-post-eligibility-evidence-ready" in content
    assert '"recovery_mode": True' in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content


def test_recovered_completion_launcher_is_config_guarded_and_unarmed():
    content = _workflow("phase1-pons-recovered-completion-one-shot.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "push:" in trigger_block
    assert "workflow_dispatch:" not in trigger_block
    assert ".github/phase1-pons-recovered-completion.json" in content
    assert "startsWith(github.event.head_commit.message" in content
    assert "contains(github.event.head_commit.message" not in content
    assert "launch recovered Phase 1 completion generation " in content
    assert 'r"launch recovered Phase 1 completion generation (\\d+)"' in content
    assert "raw_launch_message != launch_message" in content
    assert "launch message must be exactly one line" in content
    assert "launch requires an exact generation" in content
    assert "requested_generation != generation" in content
    assert "launch/config generation mismatch" in content
    assert "generation != previous_generation + 1" in content
    assert "generation must increment " in content
    assert "by exactly one" in content
    assert 're.fullmatch(r"[0-9a-f]{40}", before_sha)' in content
    assert 're.fullmatch(r"[0-9a-f]{40}", current_sha)' in content
    assert 'f"/repos/{repo}/commits/{current_sha}"' in content
    assert "launch must be a direct " in content
    assert "single-parent commit" in content
    assert "launch must modify exactly " in content
    assert "the guarded config file" in content
    assert "expected_keys = {" in content
    assert "set(config) != expected_keys" in content
    assert "set(previous_config) != expected_keys" in content
    assert "previous config schema changed" in content
    assert "validation_generation != 7" in content
    assert "previous_validation_generation != 7" in content
    assert "validation generation changed" in content
    assert "recovered completion config is not armed" in content
    assert "source_id != 33_982_556_591" in content
    assert "v1_id <= 0" in content
    assert "pricing_run_id" in content
    assert "reused pricing requires an explicit V2/V4 run ID" in content
    assert "phase1-pons-recovered-completion-chain.yml" in content
    assert "import urllib.error" in content
    assert "transient_http_codes = {" in content
    assert "for attempt in range(3):" in content
    assert "recovered completion metadata retry loop exhausted" in content
    assert "time.sleep(" not in content


def test_viability_accepts_only_approved_evidence_workflow_paths():
    guard = _workflow("phase1-pons-viability-guarded-route.yml")
    finalizer = _workflow(
        "phase1-pons-viability-ledger-finalize-one-shot.yml"
    )
    for content in (guard, finalizer):
        assert (
            "phase1-pons-post-eligibility-evidence-one-shot.yml"
            in content
        )
        assert "phase1-pons-recovered-completion-one-shot.yml" in content
        assert "phase1/data-acquisition-spike" in content
    assert "evidence handoff workflow path is not allowed" in guard
    assert "viability ledger evidence workflow path is not allowed" in finalizer


def test_readiness_state_change_watcher_is_artifact_only_and_scoped():
    content = _workflow("phase1-pons-readiness-on-state-change.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "push:" in trigger_block
    assert "workflow_dispatch:" not in trigger_block
    assert ".github/phase1-pons-viability-ready.json" in content
    assert ".github/phase1-pons-viability-runs.json" in content
    assert "phase1-pons-readiness-audit.yml" in content
    assert 'source_eligibility_run_id: "33982556591"' in content
    assert "cancel-in-progress: true" in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "RpcClient" not in content
    assert "time.sleep(" not in content


def test_post_eligibility_handoffs_validate_bundle_before_viability():
    normal = _workflow("phase1-pons-post-eligibility-evidence-chain.yml")
    recovered = _workflow("phase1-pons-recovered-completion-chain.yml")
    for content in (normal, recovered):
        assert "validate_post_eligibility_evidence_bundle" in content
        assert "pons-eligible-universe-summary.json" in content
        assert "pons-eligible-100k-universe.jsonl.manifest.json" in content
        assert "pons-representative-validation-summary.json" in content
        assert "pons-representative-validation.jsonl.manifest.json" in content
        assert '"eligible_universe_sha256"' not in content or "**validation" in content
        assert "phase1-pons-post-eligibility-evidence-ready" in content
        assert "id: upload_evidence_ready" in content
        assert "id: retry_upload_evidence_ready" in content
        assert "Retry evidence-ready artifact upload" in content
        assert "Final evidence-ready artifact upload retry" in content
        assert "Resolve exact eligible and representative artifacts" in content
        assert "select_equivalent_artifact_retry" in content
        assert "post-eligibility evidence input retry artifacts " in content
        assert "are not equivalent" in content
        assert "eligible_artifact_id" in content
        assert "representative_artifact_id" in content
        assert (
            "artifact-ids: ${{ steps.evidence_inputs.outputs."
            "eligible_artifact_id }}"
            in content
        )
        assert (
            "artifact-ids: ${{ steps.evidence_inputs.outputs."
            "representative_artifact_id }}"
            in content
        )
    assert "post-eligibility source run must match frozen parent" in normal
    assert "33_982_556_591" in normal
    assert "phase1-pons-full-eligibility-acquisition-one-shot.yml" in normal
    assert "post-eligibility source workflow path changed" in normal
    assert "post-eligibility source branch changed" in normal
    assert "c53b3a63156976a5873752c332fa7578011249b0" in normal
    assert "post-eligibility source launch commit changed" in normal
    assert "post-eligibility support run IDs changed" in normal
    assert "post-eligibility support run is not successful" in normal
    assert "post-eligibility support workflow path changed" in normal
    assert "post-eligibility support branch changed" in normal
    assert "post-eligibility support artifact missing or expired" in normal
    assert "post-eligibility quote audit artifact changed" in normal
    for run_id in (
        "33_974_681_334",
        "33_920_762_592",
        "33_911_022_718",
        "33_936_232_604",
        "33_912_452_330",
        "33_923_299_711",
        "33_972_109_927",
    ):
        assert run_id in normal
    for token in (
        "phase1-pons-stock-oracle-promote-v2-delta-one-shot.yml",
        "phase1-pons-stock-oracle-full",
        "phase1-pons-research-smoke.yml",
        "phase1-pons-research-smoke",
        "phase1-pons-v1-registry-recovery.yml",
        "phase1-pons-full-registry-recovered",
        "phase1-pons-v2-curve-gap-recovery-optimized-one-shot.yml",
        "phase1-pons-v2-curve-full",
        "phase1-pons-v2-transition-full.yml",
        "phase1-pons-v2-transition-full",
        "phase1-pons-quote-audit-one-shot.yml",
        "phase1-pons-full-quote-audit-current",
        "phase1-pons-anchor-promote-recovered-one-shot.yml",
        "phase1-pons-weth-usdg-anchor-full",
    ):
        assert token in normal
        assert token in recovered
    assert "expected_lifecycle_run_id=source_run_id" in normal
    assert "expected_v1_v3_run_id=source_run_id" in normal
    assert "expected_v2_v4_run_id=source_run_id" in normal
    assert "expected_lifecycle_run_id=pricing_run_id" in recovered
    assert "expected_v1_v3_run_id=v1_v3_run_id" in recovered
    assert "expected_v2_v4_run_id=v2_v4_run_id" in recovered
