from pathlib import Path


PATH = Path(".github/workflows/phase1-pons-repaired-pricing-promote.yml")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)


text = PATH.read_text()
text = replace_once(
    text,
    '''              34_480_161_440: {
                  "path": (
                      ".github/workflows/"
                      "phase1-pons-recovered-completion-one-shot.yml"
                  ),
                  "branch": "phase1/data-acquisition-spike",
                  "head_sha": "db374769984c621d4f2f22aad27e0686f218164a",
                  "conclusion": "success",
              },
''',
    '''              34_480_161_440: {
                  "path": (
                      ".github/workflows/"
                      "phase1-pons-recovered-completion-one-shot.yml"
                  ),
                  "branch": "phase1/data-acquisition-spike",
                  "head_sha": "db374769984c621d4f2f22aad27e0686f218164a",
                  "conclusion": "failure",
              },
''',
    "V3 parent conclusion",
)
text = replace_once(
    text,
    '''          artifact_contracts = {
''',
    '''          producer_job_contracts = {
              102_880_847_690: {
                  "run_id": 34_480_161_440,
                  "name": "recover / pricing / v1_eligibility / eligibility",
                  "conclusion": "success",
              },
              103_164_491_961: {
                  "run_id": 34_480_161_440,
                  "name": "recover / pricing / v3_fallback / merge",
                  "conclusion": "success",
              },
          }
          for job_id, contract in producer_job_contracts.items():
              job = get(f"/repos/{repo}/actions/jobs/{job_id}")
              if (
                  int(job.get("run_id", 0)) != contract["run_id"]
                  or str(job.get("name") or "") != contract["name"]
                  or job.get("status") != "completed"
                  or job.get("conclusion") != contract["conclusion"]
              ):
                  raise SystemExit(
                      "repaired pricing source producer job changed: "
                      f"job={job_id}"
                  )

          known_failure_job_id = 103_165_686_004
          known_failure_job = get(
              f"/repos/{repo}/actions/jobs/{known_failure_job_id}"
          )
          if (
              int(known_failure_job.get("run_id", 0)) != 34_480_161_440
              or str(known_failure_job.get("name") or "")
              != "recover / pricing / v4_fallback / plan"
              or known_failure_job.get("status") != "completed"
              or known_failure_job.get("conclusion") != "failure"
          ):
              raise SystemExit(
                  "repaired pricing known downstream failure changed: "
                  f"job={known_failure_job_id}"
              )

          artifact_contracts = {
''',
    "producer job validation insertion",
)
PATH.write_text(text)
