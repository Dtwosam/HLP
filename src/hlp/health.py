from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class HealthState:
    started_ns: int = field(default_factory=time.time_ns)
    message_counts: Counter[str] = field(default_factory=Counter)
    last_message_ns: dict[str, int] = field(default_factory=dict)
    reconnect_count: int = 0
    connection_count: int = 0
    write_errors: int = 0

    def mark_message(self, channel: str, coin: str | None, received_ns: int) -> None:
        key = f"{channel}:{coin or '_'}"
        self.message_counts[key] += 1
        self.last_message_ns[key] = received_ns

    def snapshot(self, *, queue_depth: int) -> dict[str, Any]:
        now_ns = time.time_ns()
        ages = {
            key: round((now_ns - timestamp_ns) / 1_000_000_000, 3)
            for key, timestamp_ns in self.last_message_ns.items()
        }
        return {
            "uptime_seconds": round((now_ns - self.started_ns) / 1_000_000_000, 1),
            "connections": self.connection_count,
            "reconnects": self.reconnect_count,
            "write_errors": self.write_errors,
            "queue_depth": queue_depth,
            "message_counts": dict(self.message_counts),
            "last_message_age_seconds": ages,
        }
