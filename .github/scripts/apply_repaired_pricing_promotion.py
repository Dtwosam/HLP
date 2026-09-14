from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parents[2]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def patch_config() -> None:
    path = ROOT / ".github" / "phase1-pons-recovered-completion.json"
    config = json.loads(path.read_text())
    expected = {
        "generation",
        "source_eligibility_run_id",
        "v1_v3_run_id",
        "v2_v4_run_id",
        "prior_transfer_run_id",
        "validation_generation",
        "pricing_run_id",
        "v3_fallback_run_id",
    }
    if set(config) != expected:
        raise SystemExit(f"config schema changed before patch: {sorted(config)}")
    config["validation_generation"] = 8
    config["repaired_v2_lifecycle_run_id"] = 0
    config["repaired_v4_fallback_run_id"] = 0
    ordered = {
        "generation": config["generation"],
        "source_eligibility_run_id": config["source_eligibility_run_id"],
        "v1_v3_run_id": config["v1_v3_run_id"],
        "v2_v4_run_id": config["v2_v4_run_id"],
        "prior_transfer_run_id": config["prior_transfer_run_id"],
        "validation_generation": config["validation_generation"],
        "pricing_run_id": config["pricing_run_id"],
        "v3_fallback_run_id": config["v3_fallback_run_id"],
        "repaired_v2_lifecycle_run_id": config["repaired_v2_lifecycle_run_id"],
        "repaired_v4_fallback_run_id": config["repaired_v4_fallback_run_id"],
    }
    path.write_text(json.dumps(ordered, indent=2) + "\n")


def patch_one_shot() -> None:
    path = ROOT / ".github" / "workflows" / "phase1-pons-recovered-completion-one-shot.yml"
    text = path.read_text()

    text = replace_once(
        text,
        """      pricing_run_id: ${{ steps.read.outputs.pricing_run_id }}\n      v3_fallback_run_id: ${{ steps.read.outputs.v3_fallback_run_id }}\n""",
        """      pricing_run_id: ${{ steps.read.outputs.pricing_run_id }}\n      v3_fallback_run_id: ${{ steps.read.outputs.v3_fallback_run_id }}\n      repaired_v2_lifecycle_run_id: ${{ steps.read.outputs.repaired_v2_lifecycle_run_id }}\n      repaired_v4_fallback_run_id: ${{ steps.read.outputs.repaired_v4_fallback_run_id }}\n""",
        "one-shot outputs",
    )
    text = replace_once(
        text,
        """              \"pricing_run_id\",\n              \"v3_fallback_run_id\",\n          }\n""",
        """              \"pricing_run_id\",\n              \"v3_fallback_run_id\",\n              \"repaired_v2_lifecycle_run_id\",\n              \"repaired_v4_fallback_run_id\",\n          }\n""",
        "one-shot expected keys",
    )
    text = replace_once(
        text,
        """          pricing_id = int(config.get(\"pricing_run_id\", 0))\n          v3_fallback_id = int(config.get(\"v3_fallback_run_id\", 0))\n          previous_generation = int(previous_config.get(\"generation\", -1))\n""",
        """          pricing_id = int(config.get(\"pricing_run_id\", 0))\n          v3_fallback_id = int(config.get(\"v3_fallback_run_id\", 0))\n          repaired_v2_id = int(\n              config.get(\"repaired_v2_lifecycle_run_id\", 0)\n          )\n          repaired_v4_id = int(\n              config.get(\"repaired_v4_fallback_run_id\", 0)\n          )\n          previous_generation = int(previous_config.get(\"generation\", -1))\n""",
        "one-shot parse repaired IDs",
    )
    text = replace_once(
        text,
        """              validation_generation != 7\n              or previous_validation_generation != 7\n""",
        """              validation_generation != 8\n              or previous_validation_generation != 8\n""",
        "one-shot validation generation",
    )
    text = replace_once(
        text,
        """          if (\n              v2_id < 0\n              or prior_id < 0\n              or pricing_id < 0\n              or v3_fallback_id < 0\n          ):\n              raise SystemExit(\"recovered completion optional run IDs are invalid\")\n          if pricing_id > 0 and v2_id <= 0:\n              raise SystemExit(\n                  \"reused pricing requires an explicit V2/V4 run ID\"\n              )\n""",
        """          if (\n              v2_id < 0\n              or prior_id < 0\n              or pricing_id < 0\n              or v3_fallback_id < 0\n              or repaired_v2_id < 0\n              or repaired_v4_id < 0\n          ):\n              raise SystemExit(\"recovered completion optional run IDs are invalid\")\n          if pricing_id > 0 and v2_id <= 0:\n              raise SystemExit(\n                  \"reused pricing requires an explicit V2/V4 run ID\"\n              )\n          if bool(repaired_v2_id) != bool(repaired_v4_id):\n              raise SystemExit(\n                  \"repaired pricing run IDs must be supplied together\"\n              )\n          if pricing_id > 0 and repaired_v2_id > 0:\n              raise SystemExit(\n                  \"repaired pricing cannot be combined with pricing_run_id\"\n              )\n          if repaired_v2_id > 0 and v2_id <= 0:\n              raise SystemExit(\n                  \"repaired pricing requires an explicit V2/V4 run ID\"\n              )\n          if repaired_v2_id > 0 and v3_fallback_id <= 0:\n              raise SystemExit(\n                  \"repaired pricing requires v3_fallback_run_id\"\n              )\n""",
        "one-shot repaired mode guards",
    )
    text = replace_once(
        text,
        """              output.write(f\"v3_fallback_run_id={v3_fallback_id}\\n\")\n""",
        """              output.write(f\"v3_fallback_run_id={v3_fallback_id}\\n\")\n              output.write(\n                  \"repaired_v2_lifecycle_run_id=\"\n                  + (str(repaired_v2_id) if repaired_v2_id else \"\")\n                  + \"\\n\"\n              )\n              output.write(\n                  \"repaired_v4_fallback_run_id=\"\n                  + (str(repaired_v4_id) if repaired_v4_id else \"\")\n                  + \"\\n\"\n              )\n""",
        "one-shot repaired outputs",
    )
    text = replace_once(
        text,
        """              \"pricing_run_id\": pricing_id,\n              \"v3_fallback_run_id\": v3_fallback_id,\n          }, sort_keys=True))\n""",
        """              \"pricing_run_id\": pricing_id,\n              \"v3_fallback_run_id\": v3_fallback_id,\n              \"repaired_v2_lifecycle_run_id\": repaired_v2_id,\n              \"repaired_v4_fallback_run_id\": repaired_v4_id,\n          }, sort_keys=True))\n""",
        "one-shot report",
    )
    text = replace_once(
        text,
        """      pricing_run_id: ${{ needs.config.outputs.pricing_run_id }}\n      v3_fallback_run_id: ${{ needs.config.outputs.v3_fallback_run_id }}\n      oracle_run_id: \"34765335793\"\n""",
        """      pricing_run_id: ${{ needs.config.outputs.pricing_run_id }}\n      v3_fallback_run_id: ${{ needs.config.outputs.v3_fallback_run_id }}\n      repaired_v2_lifecycle_run_id: ${{ needs.config.outputs.repaired_v2_lifecycle_run_id }}\n      repaired_v4_fallback_run_id: ${{ needs.config.outputs.repaired_v4_fallback_run_id }}\n      oracle_run_id: \"34765335793\"\n""",
        "one-shot recover inputs",
    )

    path.write_text(text)


def patch_chain() -> None:
    path = ROOT / ".github" / "workflows" / "phase1-pons-recovered-completion-chain.yml"
    text = path.read_text()

    text = replace_once(
        text,
        """      v3_fallback_run_id:\n        description: \"Optional prior run containing completed canonical V3 fallback artifacts\"\n        required: false\n        default: \"\"\n        type: string\n      oracle_run_id:\n""",
        """      v3_fallback_run_id:\n        description: \"Optional prior run containing completed canonical V3 fallback artifacts\"\n        required: false\n        default: \"\"\n        type: string\n      repaired_v2_lifecycle_run_id:\n        description: \"Exact repaired V2 lifecycle evidence run; must be paired with repaired V4 fallback evidence\"\n        required: false\n        default: \"\"\n        type: string\n      repaired_v4_fallback_run_id:\n        description: \"Exact repaired V4/generic fallback evidence run; must be paired with repaired V2 lifecycle evidence\"\n        required: false\n        default: \"\"\n        type: string\n      oracle_run_id:\n""",
        "chain dispatch repaired inputs",
    )
    text = replace_once(
        text,
        """      v3_fallback_run_id:\n        required: false\n        default: \"\"\n        type: string\n      oracle_run_id:\n""",
        """      v3_fallback_run_id:\n        required: false\n        default: \"\"\n        type: string\n      repaired_v2_lifecycle_run_id:\n        required: false\n        default: \"\"\n        type: string\n      repaired_v4_fallback_run_id:\n        required: false\n        default: \"\"\n        type: string\n      oracle_run_id:\n""",
        "chain call repaired inputs",
    )
    text = replace_once(
        text,
        """          PRICING_RUN_ID: ${{ inputs.pricing_run_id }}\n          V3_FALLBACK_RUN_ID: ${{ inputs.v3_fallback_run_id }}\n          ORACLE_RUN_ID: ${{ inputs.oracle_run_id }}\n""",
        """          PRICING_RUN_ID: ${{ inputs.pricing_run_id }}\n          V3_FALLBACK_RUN_ID: ${{ inputs.v3_fallback_run_id }}\n          REPAIRED_V2_LIFECYCLE_RUN_ID: ${{ inputs.repaired_v2_lifecycle_run_id }}\n          REPAIRED_V4_FALLBACK_RUN_ID: ${{ inputs.repaired_v4_fallback_run_id }}\n          ORACLE_RUN_ID: ${{ inputs.oracle_run_id }}\n""",
        "chain preflight env",
    )
    text = replace_once(
        text,
        """          v3_fallback_text = os.environ[\"V3_FALLBACK_RUN_ID\"].strip()\n          v3_fallback_id = int(v3_fallback_text) if v3_fallback_text else 0\n          if source_id != 33_982_556_591:\n""",
        """          v3_fallback_text = os.environ[\"V3_FALLBACK_RUN_ID\"].strip()\n          v3_fallback_id = int(v3_fallback_text) if v3_fallback_text else 0\n          repaired_v2_text = os.environ[\n              \"REPAIRED_V2_LIFECYCLE_RUN_ID\"\n          ].strip()\n          repaired_v2_id = int(repaired_v2_text) if repaired_v2_text else 0\n          repaired_v4_text = os.environ[\n              \"REPAIRED_V4_FALLBACK_RUN_ID\"\n          ].strip()\n          repaired_v4_id = int(repaired_v4_text) if repaired_v4_text else 0\n          if source_id != 33_982_556_591:\n""",
        "chain parse repaired IDs",
    )
    text = replace_once(
        text,
        """          if (\n              v1_id <= 0\n              or v2_id < 0\n              or pricing_id < 0\n              or v3_fallback_id < 0\n          ):\n              raise SystemExit(\"recovery run IDs are invalid\")\n          if pricing_id > 0 and v2_id <= 0:\n              raise SystemExit(\n                  \"reused pricing requires an explicit V2/V4 run ID\"\n              )\n""",
        """          if (\n              v1_id <= 0\n              or v2_id < 0\n              or pricing_id < 0\n              or v3_fallback_id < 0\n              or repaired_v2_id < 0\n              or repaired_v4_id < 0\n          ):\n              raise SystemExit(\"recovery run IDs are invalid\")\n          if pricing_id > 0 and v2_id <= 0:\n              raise SystemExit(\n                  \"reused pricing requires an explicit V2/V4 run ID\"\n              )\n          if bool(repaired_v2_id) != bool(repaired_v4_id):\n              raise SystemExit(\n                  \"repaired pricing run IDs must be supplied together\"\n              )\n          if pricing_id > 0 and repaired_v2_id > 0:\n              raise SystemExit(\n                  \"repaired pricing cannot be combined with pricing_run_id\"\n              )\n          if repaired_v2_id > 0 and v2_id <= 0:\n              raise SystemExit(\n                  \"repaired pricing requires an explicit V2/V4 run ID\"\n              )\n          if repaired_v2_id > 0 and v3_fallback_id <= 0:\n              raise SystemExit(\n                  \"repaired pricing requires v3_fallback_run_id\"\n              )\n""",
        "chain repaired mode guards",
    )
    text = replace_once(
        text,
        """              \"pricing_run_id\": pricing_id,\n              \"v3_fallback_run_id\": v3_fallback_id,\n              \"support_run_ids\": observed_support_runs,\n""",
        """              \"pricing_run_id\": pricing_id,\n              \"v3_fallback_run_id\": v3_fallback_id,\n              \"repaired_v2_lifecycle_run_id\": repaired_v2_id,\n              \"repaired_v4_fallback_run_id\": repaired_v4_id,\n              \"support_run_ids\": observed_support_runs,\n""",
        "chain preflight report repaired IDs",
    )
    text = replace_once(
        text,
        """              \"resume_v2_v4\": v2_id == 0 and pricing_id == 0,\n              \"reuse_pricing\": pricing_id > 0,\n""",
        """              \"resume_v2_v4\": (\n                  v2_id == 0 and pricing_id == 0 and repaired_v2_id == 0\n              ),\n              \"reuse_pricing\": pricing_id > 0,\n              \"promote_repaired_pricing\": repaired_v2_id > 0,\n""",
        "chain preflight mode report",
    )
    text = replace_once(
        text,
        """    if: ${{ needs.preflight.result == 'success' && inputs.pricing_run_id == '' && inputs.v2_v4_run_id == '' }}\n""",
        """    if: ${{ needs.preflight.result == 'success' && inputs.pricing_run_id == '' && inputs.repaired_v2_lifecycle_run_id == '' && inputs.repaired_v4_fallback_run_id == '' && inputs.v2_v4_run_id == '' }}\n""",
        "chain skip V2/V4 acquisition",
    )
    text = replace_once(
        text,
        """    if: ${{ always() && inputs.pricing_run_id == '' && needs.preflight.result == 'success' && (inputs.v2_v4_run_id != '' || needs.v2_v4.result == 'success' || needs.v2_v4_recovery.result == 'success') }}\n""",
        """    if: ${{ always() && inputs.pricing_run_id == '' && inputs.repaired_v2_lifecycle_run_id == '' && inputs.repaired_v4_fallback_run_id == '' && needs.preflight.result == 'success' && (inputs.v2_v4_run_id != '' || needs.v2_v4.result == 'success' || needs.v2_v4_recovery.result == 'success') }}\n""",
        "chain skip heavy pricing",
    )

    promotion_jobs = """  promote_repaired_pricing:\n    needs: preflight\n    if: ${{ needs.preflight.result == 'success' && inputs.repaired_v2_lifecycle_run_id != '' && inputs.repaired_v4_fallback_run_id != '' }}\n    uses: ./.github/workflows/phase1-pons-repaired-pricing-promote.yml\n    with:\n      v1_v3_run_id: ${{ inputs.v1_v3_run_id }}\n      v2_v4_run_id: ${{ inputs.v2_v4_run_id }}\n      v3_fallback_run_id: ${{ inputs.v3_fallback_run_id }}\n      repaired_v2_lifecycle_run_id: ${{ inputs.repaired_v2_lifecycle_run_id }}\n      repaired_v4_fallback_run_id: ${{ inputs.repaired_v4_fallback_run_id }}\n\n  promote_repaired_universe:\n    needs: promote_repaired_pricing\n    if: ${{ needs.promote_repaired_pricing.result == 'success' }}\n    uses: ./.github/workflows/phase1-pons-eligible-universe-promote.yml\n    with:\n      source_eligibility_run_id: ${{ github.run_id }}\n    secrets: inherit\n\n"""
    text = replace_once(
        text,
        "  promote_reused_universe:\n",
        promotion_jobs + "  promote_reused_universe:\n",
        "chain insert repaired promotion jobs",
    )

    text = replace_once(
        text,
        """  verify_reused_pricing:\n    needs: promote_reused_universe\n    if: ${{ needs.promote_reused_universe.result == 'success' && inputs.pricing_run_id != '' }}\n""",
        """  verify_reused_pricing:\n    needs:\n      - promote_reused_universe\n      - promote_repaired_universe\n    if: ${{ always() && ((inputs.pricing_run_id != '' && needs.promote_reused_universe.result == 'success') || (inputs.repaired_v2_lifecycle_run_id != '' && needs.promote_repaired_universe.result == 'success')) }}\n""",
        "chain verify promoted pricing condition",
    )
    text = replace_once(
        text,
        """          PRICING_RUN_ID: ${{ inputs.pricing_run_id }}\n""",
        """          PRICING_RUN_ID: ${{ inputs.pricing_run_id != '' && inputs.pricing_run_id || format('{0}', github.run_id) }}\n""",
        "chain verified pricing source run",
    )

    old_representative = """  representative:\n    needs:\n      - preflight\n      - pricing\n      - promote_reused_universe\n      - verify_reused_pricing\n    if: ${{ always() && needs.preflight.result == 'success' && ((inputs.pricing_run_id == '' && needs.pricing.result == 'success') || (inputs.pricing_run_id != '' && needs.promote_reused_universe.result == 'success' && needs.verify_reused_pricing.result == 'success')) }}\n"""
    new_representative = """  representative:\n    needs:\n      - preflight\n      - pricing\n      - promote_repaired_pricing\n      - promote_reused_universe\n      - promote_repaired_universe\n      - verify_reused_pricing\n    if: ${{ always() && needs.preflight.result == 'success' && ((inputs.pricing_run_id == '' && inputs.repaired_v2_lifecycle_run_id == '' && needs.pricing.result == 'success') || (inputs.pricing_run_id != '' && needs.promote_reused_universe.result == 'success' && needs.verify_reused_pricing.result == 'success') || (inputs.repaired_v2_lifecycle_run_id != '' && needs.promote_repaired_pricing.result == 'success' && needs.promote_repaired_universe.result == 'success' && needs.verify_reused_pricing.result == 'success')) }}\n"""
    text = replace_once(
        text,
        old_representative,
        new_representative,
        "chain representative modes",
    )

    old_ready = """  ready:\n    needs:\n      - pricing\n      - promote_reused_universe\n      - verify_reused_pricing\n      - representative\n    if: ${{ always() && needs.representative.result == 'success' && ((inputs.pricing_run_id == '' && needs.pricing.result == 'success') || (inputs.pricing_run_id != '' && needs.promote_reused_universe.result == 'success' && needs.verify_reused_pricing.result == 'success')) }}\n"""
    new_ready = """  ready:\n    needs:\n      - pricing\n      - promote_repaired_pricing\n      - promote_reused_universe\n      - promote_repaired_universe\n      - verify_reused_pricing\n      - representative\n    if: ${{ always() && needs.representative.result == 'success' && ((inputs.pricing_run_id == '' && inputs.repaired_v2_lifecycle_run_id == '' && needs.pricing.result == 'success') || (inputs.pricing_run_id != '' && needs.promote_reused_universe.result == 'success' && needs.verify_reused_pricing.result == 'success') || (inputs.repaired_v2_lifecycle_run_id != '' && needs.promote_repaired_pricing.result == 'success' && needs.promote_repaired_universe.result == 'success' && needs.verify_reused_pricing.result == 'success')) }}\n"""
    text = replace_once(text, old_ready, new_ready, "chain ready modes")

    path.write_text(text)


if __name__ == "__main__":
    patch_config()
    patch_one_shot()
    patch_chain()
    print("patched recovered completion for exact repaired pricing promotion")
