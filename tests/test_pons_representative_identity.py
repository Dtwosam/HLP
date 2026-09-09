import json

import pytest

from hlp.data.pons_representative_identity import (
    representative_sample_identity,
    require_representative_sample_identity,
)


def _row(index, *, group, version):
    return {
        "token": "0x" + f"{index:040x}",
        "sample_group": group,
        "pons_version": version,
        "launch_block": index,
    }


def _write_sample(path):
    rows = [
        *[
            _row(i, group="runner", version="v1" if i < 5 else "v2")
            for i in range(1, 6)
        ],
        *[
            _row(i, group="failure", version="v1" if i < 10 else "v2")
            for i in range(6, 11)
        ],
    ]
    path.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        )
    )
    return rows


def test_representative_sample_identity_binds_file_and_token_set(tmp_path):
    path = tmp_path / "sample.jsonl"
    _write_sample(path)

    identity = representative_sample_identity(path)

    assert identity["records"] == 10
    assert identity["groups"] == {"failure": 5, "runner": 5}
    assert identity["versions"] == {"v1": 8, "v2": 2}
    assert len(identity["sample_sha256"]) == 64
    assert len(identity["token_set_sha256"]) == 64
    assert len(identity["tokens"]) == 10

    verified = require_representative_sample_identity(
        path,
        {
            "tokens": 10,
            "sample_sha256": identity["sample_sha256"],
            "token_set_sha256": identity["token_set_sha256"],
        },
    )
    assert verified == identity


def test_representative_sample_identity_rejects_duplicate_tokens(tmp_path):
    path = tmp_path / "sample.jsonl"
    rows = _write_sample(path)
    rows[-1]["token"] = rows[0]["token"]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))

    with pytest.raises(ValueError, match="duplicate tokens"):
        representative_sample_identity(path)


def test_representative_sample_identity_rejects_group_drift(tmp_path):
    path = tmp_path / "sample.jsonl"
    rows = _write_sample(path)
    rows[-1]["sample_group"] = "runner"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))

    with pytest.raises(ValueError, match="groups changed"):
        representative_sample_identity(path)


def test_representative_sample_identity_rejects_summary_digest_drift(tmp_path):
    path = tmp_path / "sample.jsonl"
    _write_sample(path)
    identity = representative_sample_identity(path)

    with pytest.raises(ValueError, match="sample_sha256 mismatch"):
        require_representative_sample_identity(
            path,
            {
                "tokens": 10,
                "sample_sha256": "0" * 64,
                "token_set_sha256": identity["token_set_sha256"],
            },
        )
