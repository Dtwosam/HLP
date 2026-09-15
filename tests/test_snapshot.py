import hashlib
import json
from pathlib import Path

from hlp.data.snapshot import write_jsonl_snapshot


def test_write_jsonl_snapshot_is_deterministic_and_manifested(tmp_path: Path):
    output = tmp_path / "sample.jsonl"
    manifest = write_jsonl_snapshot(
        [{"b": 2, "a": 1}, {"a": 3}],
        output=output,
        provenance={"source": "unit"},
    )
    raw = output.read_bytes()
    assert manifest["records"] == 2
    assert manifest["sha256"] == hashlib.sha256(raw).hexdigest()
    assert raw == b'{"a":1,"b":2}\n{"a":3}\n'
    sidecar = json.loads(
        output.with_suffix(".jsonl.manifest.json").read_text()
    )
    assert sidecar["provenance"]["source"] == "unit"
