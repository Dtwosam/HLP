from __future__ import annotations

import argparse
import io
import json
import os
import re
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Iterable


_API_ROOT = "https://api.github.com"


def _request(url: str, token: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "hlp-phase1-artifact-recovery",
        },
    )


def _get_json(url: str, token: str) -> dict:
    with urllib.request.urlopen(_request(url, token), timeout=60) as response:
        return json.load(response)


def _get_bytes(url: str, token: str) -> bytes:
    with urllib.request.urlopen(_request(url, token), timeout=120) as response:
        return response.read()


def list_run_artifacts(
    *,
    repository: str,
    run_id: int,
    token: str,
    get_json: Callable[[str, str], dict] = _get_json,
) -> list[dict]:
    artifacts: list[dict] = []
    page = 1
    while True:
        url = (
            f"{_API_ROOT}/repos/{repository}/actions/runs/{run_id}/artifacts"
            f"?per_page=100&page={page}"
        )
        batch = list(get_json(url, token).get("artifacts", []))
        artifacts.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return artifacts


def matching_artifacts(artifacts: Iterable[dict], name_regex: str) -> list[dict]:
    pattern = re.compile(name_regex)
    return sorted(
        (artifact for artifact in artifacts if pattern.fullmatch(artifact["name"])),
        key=lambda artifact: artifact["name"],
    )


def _extract_zip_merge(payload: bytes, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    root = output.resolve()
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for member in archive.infolist():
            target = (output / member.filename).resolve()
            if target != root and root not in target.parents:
                raise ValueError(f"unsafe artifact member path: {member.filename}")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            data = archive.read(member)
            if target.exists() and target.read_bytes() != data:
                raise ValueError(f"artifact member collision: {member.filename}")
            target.write_bytes(data)


def download_run_artifacts(
    *,
    repository: str,
    run_id: int,
    token: str,
    name_regex: str,
    output: Path,
    allow_empty: bool = False,
) -> list[dict]:
    artifacts = matching_artifacts(
        list_run_artifacts(repository=repository, run_id=run_id, token=token),
        name_regex,
    )
    if not artifacts and not allow_empty:
        raise RuntimeError(
            f"no artifacts in run {run_id} matched {name_regex!r}"
        )
    for artifact in artifacts:
        if artifact.get("expired"):
            raise RuntimeError(f"artifact expired: {artifact['name']}")
        payload = _get_bytes(artifact["archive_download_url"], token)
        _extract_zip_merge(payload, output)
    return artifacts


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    download = subparsers.add_parser("download-run")
    download.add_argument("--repository", required=True)
    download.add_argument("--run-id", required=True, type=int)
    download.add_argument("--name-regex", required=True)
    download.add_argument("--out", required=True, type=Path)
    download.add_argument("--allow-empty", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")
    if args.command == "download-run":
        artifacts = download_run_artifacts(
            repository=args.repository,
            run_id=args.run_id,
            token=token,
            name_regex=args.name_regex,
            output=args.out,
            allow_empty=args.allow_empty,
        )
        print(
            json.dumps(
                {
                    "run_id": args.run_id,
                    "matched": len(artifacts),
                    "names": [artifact["name"] for artifact in artifacts],
                },
                sort_keys=True,
            )
        )
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
