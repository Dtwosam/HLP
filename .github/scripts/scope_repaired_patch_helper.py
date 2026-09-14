from pathlib import Path


path = Path(".github/scripts/apply_repaired_pricing_promotion.py")
text = path.read_text()

# The existing launcher guard already exact-checks the config schema. Keep its
# validation generation stable while adding the repaired source keys.
config_bump = '    config["validation_generation"] = 8\n'
if text.count(config_bump) != 1:
    raise SystemExit(
        f"temporary helper validation config target changed: {text.count(config_bump)}"
    )
text = text.replace(config_bump, "", 1)

validation_marker = '        "one-shot validation generation",\n'
if text.count(validation_marker) != 1:
    raise SystemExit(
        "temporary helper validation label changed: "
        f"{text.count(validation_marker)}"
    )
validation_index = text.index(validation_marker)
validation_start = text.rfind("    text = replace_once(\n", 0, validation_index)
validation_end = text.find("    )\n", validation_index)
if validation_start < 0 or validation_end < 0:
    raise SystemExit("temporary helper validation boundaries not found")
validation_end += len("    )\n")
text = text[:validation_start] + text[validation_end:]

# Narrow the one ambiguous env replacement to the unique provenance step.
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
        """      - name: Verify reused pricing venue provenance before representative RPC\n        env:\n          V1_V3_RUN_ID: ${{ inputs.v1_v3_run_id }}\n          V2_V4_RUN_ID: ${{ inputs.v2_v4_run_id }}\n          PRICING_RUN_ID: ${{ inputs.pricing_run_id }}\n""",
        """      - name: Verify reused pricing venue provenance before representative RPC\n        env:\n          V1_V3_RUN_ID: ${{ inputs.v1_v3_run_id }}\n          V2_V4_RUN_ID: ${{ inputs.v2_v4_run_id }}\n          PRICING_RUN_ID: ${{ inputs.pricing_run_id != '' && inputs.pricing_run_id || format('{0}', github.run_id) }}\n""",
        "chain verified pricing source run",
    )
'''
path.write_text(text[:start] + replacement + text[end:])
