from __future__ import annotations

import gzip
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO


def _safe_component(value: str | None) -> str:
    if not value:
        return "_"
    return "".join(char if char.isalnum() or char in "-_." else "_" for char in value)


class RawEventWriter:
    """Append-only hourly gzip JSONL writer for immutable wire-event envelopes."""

    def __init__(self, data_dir: Path, network: str, flush_interval_seconds: float = 1.0):
        self.root = data_dir / "raw" / network
        self.flush_interval_seconds = flush_interval_seconds
        self._handles: dict[Path, TextIO] = {}
        self._last_flush = time.monotonic()

    def _path_for(self, event: dict[str, Any]) -> Path:
        received_ns = int(event["received_time_ns"])
        stamp = datetime.fromtimestamp(received_ns / 1_000_000_000, tz=UTC)
        channel = _safe_component(str(event.get("channel") or "_"))
        coin = _safe_component(event.get("coin"))
        directory = self.root / stamp.strftime("%Y-%m-%d") / stamp.strftime("%H")
        return directory / f"{channel}-{coin}.jsonl.gz"

    def write(self, event: dict[str, Any]) -> None:
        path = self._path_for(event)
        handle = self._handles.get(path)
        if handle is None:
            path.parent.mkdir(parents=True, exist_ok=True)
            handle = gzip.open(path, mode="at", encoding="utf-8", newline="\n")  # noqa: SIM115
            self._handles[path] = handle

        handle.write(json.dumps(event, separators=(",", ":"), ensure_ascii=False))
        handle.write("\n")

        now = time.monotonic()
        if now - self._last_flush >= self.flush_interval_seconds:
            self.flush()
            self._last_flush = now

        self._close_old_partitions(path.parent)

    def _close_old_partitions(self, active_directory: Path) -> None:
        stale = [path for path in self._handles if path.parent != active_directory]
        for path in stale:
            handle = self._handles.pop(path)
            handle.flush()
            handle.close()

    def flush(self) -> None:
        for handle in self._handles.values():
            handle.flush()

    def close(self) -> None:
        for handle in self._handles.values():
            handle.flush()
            handle.close()
        self._handles.clear()
