from pathlib import Path


PATH = Path(".github/workflows/phase1-pons-representative-evidence-chain.yml")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)


text = PATH.read_text()
text = replace_once(
    text,
    """          V2_V4_RUN_ID: ${{ inputs.v2_v4_run_id }}
        run: |
""",
    """          V2_V4_RUN_ID: ${{ inputs.v2_v4_run_id }}
          CURRENT_RUN_ID: ${{ github.run_id }}
          CURRENT_HEAD_SHA: ${{ github.sha }}
        run: |
""",
    "representative preflight current-run env",
)
text = replace_once(
    text,
    """          eligibility_run = get(
              f\"/repos/{repo}/actions/runs/{eligibility_run_id}\"
          )
          if (
              eligibility_run.get(\"status\") != \"completed\"
              or eligibility_run.get(\"conclusion\") != \"success\"
          ):
              raise SystemExit(
                  \"representative eligibility run is not successful\"
              )
          if eligibility_run.get(\"head_branch\") != (
              \"phase1/data-acquisition-spike\"
          ):
              raise SystemExit(
                  \"representative eligibility branch changed\"
              )
""",
    """          current_run_id = int(os.environ[\"CURRENT_RUN_ID\"])
          current_head_sha = os.environ[\"CURRENT_HEAD_SHA\"].strip()
          eligibility_run = get(
              f\"/repos/{repo}/actions/runs/{eligibility_run_id}\"
          )
          eligibility_path = str(
              eligibility_run.get(\"path\") or \"\"
          ).split(\"@\", 1)[0]
          if eligibility_run_id == current_run_id:
              if eligibility_path != (
                  \".github/workflows/\"
                  \"phase1-pons-recovered-completion-one-shot.yml\"
              ):
                  raise SystemExit(
                      \"representative current eligibility workflow changed\"
                  )
              if str(eligibility_run.get(\"status\") or \"\") not in {
                  \"queued\",
                  \"in_progress\",
                  \"waiting\",
                  \"requested\",
                  \"pending\",
              }:
                  raise SystemExit(
                      \"representative current eligibility run is not active\"
                  )
              if eligibility_run.get(\"head_sha\") != current_head_sha:
                  raise SystemExit(
                      \"representative current eligibility head changed\"
                  )
          elif (
              eligibility_run.get(\"status\") != \"completed\"
              or eligibility_run.get(\"conclusion\") != \"success\"
          ):
              raise SystemExit(
                  \"representative eligibility run is not successful\"
              )
          if eligibility_run.get(\"head_branch\") != (
              \"phase1/data-acquisition-spike\"
          ):
              raise SystemExit(
                  \"representative eligibility branch changed\"
              )
""",
    "representative eligibility run status gate",
)
PATH.write_text(text)
