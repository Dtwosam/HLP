from pathlib import Path


path = Path(".github/scripts/apply_repaired_pricing_promotion.py")
text = path.read_text()
old = '''        text,
        """          PRICING_RUN_ID: ${{ inputs.pricing_run_id }}\n""",
        """          PRICING_RUN_ID: ${{ inputs.pricing_run_id != '' && inputs.pricing_run_id || format('{0}', github.run_id) }}\n""",
        "chain verified pricing source run",
    )
'''
new = '''        text,
        """          V1_V3_RUN_ID: ${{ inputs.v1_v3_run_id }}\n          V2_V4_RUN_ID: ${{ inputs.v2_v4_run_id }}\n          PRICING_RUN_ID: ${{ inputs.pricing_run_id }}\n""",
        """          V1_V3_RUN_ID: ${{ inputs.v1_v3_run_id }}\n          V2_V4_RUN_ID: ${{ inputs.v2_v4_run_id }}\n          PRICING_RUN_ID: ${{ inputs.pricing_run_id != '' && inputs.pricing_run_id || format('{0}', github.run_id) }}\n""",
        "chain verified pricing source run",
    )
'''
count = text.count(old)
if count != 1:
    raise SystemExit(f"temporary helper scope target changed: {count}")
path.write_text(text.replace(old, new, 1))
