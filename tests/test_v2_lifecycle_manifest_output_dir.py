from pathlib import Path


def test_v2_manifest_validation_output_dir_exists_after_checkout():
    assert Path("artifacts").is_dir()
