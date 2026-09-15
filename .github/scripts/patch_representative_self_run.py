from pathlib import Path


PATH = Path(".github/workflows/phase1-pons-representative-evidence-chain.yml")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)


text = PATH.read_text()
step_marker = "      - name: Verify frozen representative support inputs\n"
if text.count(step_marker) != 1:
    raise SystemExit("representative preflight step marker changed")
step_start = text.index(step_marker)
run_marker = "        run: |\n"
run_start = text.index(run_marker, step_start)
step_prefix = text[step_start:run_start]
env_needle = "          V2_V4_RUN_ID: ${{ inputs.v2_v4_run_id }}\n"
if step_prefix.count(env_needle) != 1:
    raise SystemExit("representative preflight V2/V4 env anchor changed")
step_prefix = step_prefix.replace(
    env_needle,
    env_needle
    + "          CURRENT_RUN_ID: ${{ github.run_id }}\n"
    + "          CURRENT_HEAD_SHA: ${{ github.sha }}\n",
    1,
)
text = text[:step_start] + step_prefix + text[run_start:]
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
                  \".github/workflows/phase1-pons-recovered-completion-one-shot.yml\"
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
