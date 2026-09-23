import hashlib
import json
from pathlib import Path

from hlp.data.snapshot import iter_jsonl_snapshot, write_jsonl_snapshot


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



def test_iter_jsonl_snapshot_streams_and_publishes_only_when_exhausted(
    tmp_path: Path,
):
    output = tmp_path / "stream.jsonl"
    rows = iter_jsonl_snapshot(
        [{"b": 2, "a": 1}, {"a": 3}],
        output=output,
        provenance={"source": "stream-unit"},
    )

    assert next(rows) == {"b": 2, "a": 1}
    assert not output.exists()
    assert not output.with_suffix(".jsonl.manifest.json").exists()

    assert list(rows) == [{"a": 3}]
    assert output.read_bytes() == b'{"a":1,"b":2}\n{"a":3}\n'
    manifest = json.loads(
        output.with_suffix(".jsonl.manifest.json").read_text()
    )
    assert manifest["records"] == 2
    assert manifest["provenance"]["source"] == "stream-unit"


def test_iter_jsonl_snapshot_cleans_partial_tape_when_consumer_stops(
    tmp_path: Path,
):
    output = tmp_path / "partial.jsonl"
    rows = iter_jsonl_snapshot(
        [{"a": 1}, {"a": 2}],
        output=output,
        provenance={"source": "partial-unit"},
    )

    assert next(rows) == {"a": 1}
    rows.close()

    assert not output.exists()
    assert not output.with_suffix(".jsonl.tmp").exists()
    assert not output.with_suffix(".jsonl.manifest.json").exists()
