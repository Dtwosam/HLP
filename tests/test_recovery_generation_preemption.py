from pathlib import Path


def test_recovered_completion_preempts_older_generation():
    content = Path(
        ".github/workflows/phase1-pons-recovered-completion-chain.yml"
    ).read_text()

    assert (
        "group: phase1-pons-recovered-completion-${{ github.ref }}"
        in content
    )
    assert "cancel-in-progress: true" in content
