from pathlib import Path


PATH = Path(".github/workflows/phase1-pons-representative-evidence-chain.yml")

text = PATH.read_text()
old = '                  "run_id": 33_974_681_334,\n'
new = '                  "run_id": 34_765_335_793,\n'
count = text.count(old)
if count != 1:
    raise SystemExit(
        f"representative oracle support run anchor changed: expected 1 got {count}"
    )
text = text.replace(old, new, 1)
PATH.write_text(text)
