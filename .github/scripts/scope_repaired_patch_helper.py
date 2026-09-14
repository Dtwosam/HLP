from pathlib import Path


path = Path(".github/scripts/apply_repaired_pricing_promotion.py")
text = path.read_text()
marker = '        "chain verified pricing source run",\n'
if text.count(marker) != 1:
    raise SystemExit(
        f"temporary helper scope label changed: {text.count(marker)}"
    )
marker_index = text.index(marker)
start = text.rfind("    text = replace_once(\n", 0, marker_index)
end = text.find("    )\n", marker_index)
if start < 0 or end < 0:
    raise SystemExit("temporary helper replacement boundaries not found")
end += len("    )\n")
replacement = '''    text = replace_once(
        text,
        """          V1_V3_RUN_ID: ${{ inputs.v1_v3_run_id }}\n          V2_V4_RUN_ID: ${{ inputs.v2_v4_run_id }}\n          PRICING_RUN_ID: ${{ inputs.pricing_run_id }}\n""",
        """          V1_V3_RUN_ID: ${{ inputs.v1_v3_run_id }}\n          V2_V4_RUN_ID: ${{ inputs.v2_v4_run_id }}\n          PRICING_RUN_ID: ${{ inputs.pricing_run_id != '' && inputs.pricing_run_id || format('{0}', github.run_id) }}\n""",
        "chain verified pricing source run",
    )
'''
path.write_text(text[:start] + replacement + text[end:])
