from pathlib import Path


WORKFLOWS = [
    ".github/workflows/phase1-pools-fun-mcap-smoke.yml",
    ".github/workflows/phase1-pools-fun-history-smoke.yml",
    ".github/workflows/phase1-noxa-history-smoke.yml",
    ".github/workflows/phase1-flap-curve-mcap-smoke.yml",
    ".github/workflows/phase1-flap-history-smoke.yml",
    ".github/workflows/phase1-trench-curve-mcap-smoke.yml",
    ".github/workflows/phase1-trench-history-smoke.yml",
]


def test_accepted_phase1_launchpad_smokes_are_manual_only():
    for path in WORKFLOWS:
        text = Path(path).read_text()
        assert "workflow_dispatch:" in text
        assert "\n  push:" not in text
        assert "\n  pull_request:" not in text
