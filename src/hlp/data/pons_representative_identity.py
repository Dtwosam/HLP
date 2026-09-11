"""Canonical identity contract for the frozen Phase 1 representative cohort."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

_TOKEN = re.compile(r"0x[0-9a-f]{40}")


def representative_sample_identity(path: Path) -> dict[str, Any]:
    """Return a strict identity for the exact 5-runner/5-failure sample file."""
    raw = path.read_bytes()
    rows = [
        json.loads(line)
        for line in raw.decode("utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) != 10:
        raise ValueError(
            "representative sample identity requires exactly 10 rows: "
            f"got={len(rows)}"
        )

    tokens: list[str] = []
    groups: Counter[str] = Counter()
    versions: Counter[str] = Counter()
    for row in rows:
        token = str(row.get("token") or "").lower()
        if _TOKEN.fullmatch(token) is None:
            raise ValueError(
                f"representative sample token is invalid: {token!r}"
            )
        tokens.append(token)
        groups[str(row.get("sample_group") or "")] += 1
        versions[str(row.get("pons_version") or "")] += 1

    if len(set(tokens)) != 10:
        raise ValueError("representative sample contains duplicate tokens")
    if groups != {"runner": 5, "failure": 5}:
        raise ValueError(
            "representative sample groups changed: "
            f"{dict(groups)}"
        )
    if set(versions) != {"v1", "v2"}:
        raise ValueError(
            "representative sample must contain both Pons generations"
        )

    token_set_sha256 = hashlib.sha256(
        ("\n".join(sorted(tokens)) + "\n").encode()
    ).hexdigest()
    return {
        "records": 10,
        "sample_sha256": hashlib.sha256(raw).hexdigest(),
        "token_set_sha256": token_set_sha256,
        "tokens": sorted(tokens),
        "groups": dict(sorted(groups.items())),
        "versions": dict(sorted(versions.items())),
    }


def require_representative_sample_identity(
    path: Path,
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify a sample file against the identity frozen in its summary."""
    identity = representative_sample_identity(path)
    for field in ("sample_sha256", "token_set_sha256"):
        if str(summary.get(field) or "") != identity[field]:
            raise ValueError(
                f"representative sample {field} mismatch"
            )
    if int(summary.get("tokens", -1)) != identity["records"]:
        raise ValueError("representative sample record count mismatch")
    return identity
