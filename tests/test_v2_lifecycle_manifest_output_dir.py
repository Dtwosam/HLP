from pathlib import Path


def test_v2_manifest_validation_creates_artifact_output_dir():
    content = Path(
        ".github/workflows/phase1-pons-v2-lifecycle-eligibility.yml"
    ).read_text()

    expected = (
        "- name: Validate frozen V2 lifecycle input manifests\n"
        "        run: |\n"
        "          mkdir -p artifacts\n"
        "          python - <<'PY'"
    )
    assert expected in content
