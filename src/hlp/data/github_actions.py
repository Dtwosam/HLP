"""Safe GitHub Actions metadata helpers used by Phase 1 accounting."""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request


_REDIRECT_CODES = {301, 302, 303, 307, 308}
_TRANSIENT_ARTIFACT_HTTP_CODES = {
    403,
    408,
    409,
    425,
    429,
    500,
    502,
    503,
    504,
}


class GitHubActionsJobLogUnavailable(RuntimeError):
    """Raised when GitHub metadata exists but the historical log blob is gone."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req,
        fp,
        code,
        msg,
        headers,
        newurl,
    ):
        return None


def fetch_github_actions_job_log(
    api_url: str,
    token: str,
    *,
    timeout: float = 60,
) -> str:
    """Download one Actions job log without leaking auth across redirects."""
    parsed_api = urllib.parse.urlparse(api_url)
    if (
        parsed_api.scheme != "https"
        or parsed_api.netloc.lower() != "api.github.com"
    ):
        raise ValueError("Actions job log API URL must use api.github.com HTTPS")
    if not token:
        raise ValueError("GitHub token is required for Actions job logs")
    if timeout <= 0:
        raise ValueError("Actions job log timeout must be positive")

    request = urllib.request.Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "hlp-phase1-accounting",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    opener = urllib.request.build_opener(_NoRedirect())
    redirect_url = None
    try:
        with opener.open(request, timeout=timeout) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code not in _REDIRECT_CODES:
            body = exc.read().decode(errors="replace")
            raise RuntimeError(
                f"GitHub Actions log request failed: HTTP {exc.code}: "
                f"{body[:500]}"
            ) from exc
        redirect_url = exc.headers.get("Location")
        if not redirect_url:
            raise RuntimeError(
                "GitHub Actions log redirect is missing Location"
            ) from exc
    else:
        return payload.decode(errors="replace")

    parsed_redirect = urllib.parse.urlparse(redirect_url)
    if (
        parsed_redirect.scheme != "https"
        or not parsed_redirect.netloc
        or parsed_redirect.username is not None
        or parsed_redirect.password is not None
    ):
        raise RuntimeError("GitHub Actions log redirect is not safe HTTPS")

    blob_request = urllib.request.Request(
        redirect_url,
        headers={"User-Agent": "hlp-phase1-accounting"},
    )
    try:
        with urllib.request.urlopen(
            blob_request,
            timeout=timeout,
        ) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code in {404, 410}:
            raise GitHubActionsJobLogUnavailable(
                "GitHub Actions redirected log blob is unavailable: "
                f"HTTP {exc.code}"
            ) from exc
        raise RuntimeError(
            f"GitHub Actions redirected log download failed: {exc}"
        ) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(
            f"GitHub Actions redirected log download failed: {exc}"
        ) from exc
    return payload.decode(errors="replace")



def fetch_github_actions_artifact_zip(
    api_url: str,
    token: str,
    *,
    timeout: float = 60,
    attempts: int = 3,
) -> bytes:
    """Download one Actions artifact ZIP without forwarding auth to blob storage."""
    parsed_api = urllib.parse.urlparse(api_url)
    if (
        parsed_api.scheme != "https"
        or parsed_api.netloc.lower() != "api.github.com"
    ):
        raise ValueError(
            "Actions artifact API URL must use api.github.com HTTPS"
        )
    if not token:
        raise ValueError("GitHub token is required for Actions artifacts")
    if timeout <= 0:
        raise ValueError("Actions artifact timeout must be positive")
    attempt_count = int(attempts)
    if attempt_count <= 0:
        raise ValueError("Actions artifact attempts must be positive")

    opener = urllib.request.build_opener(_NoRedirect())
    for attempt in range(attempt_count):
        request = urllib.request.Request(
            api_url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "hlp-phase1-artifacts",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        redirect_url = None
        try:
            with opener.open(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in _REDIRECT_CODES:
                redirect_url = exc.headers.get("Location")
                if not redirect_url:
                    raise RuntimeError(
                        "GitHub Actions artifact redirect is missing Location"
                    ) from exc
            elif (
                exc.code in _TRANSIENT_ARTIFACT_HTTP_CODES
                and attempt + 1 < attempt_count
            ):
                continue
            else:
                body = exc.read().decode(errors="replace")
                raise RuntimeError(
                    f"GitHub Actions artifact request failed: HTTP {exc.code}: "
                    f"{body[:500]}"
                ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt + 1 < attempt_count:
                continue
            raise RuntimeError(
                f"GitHub Actions artifact request failed: {exc}"
            ) from exc

        parsed_redirect = urllib.parse.urlparse(redirect_url)
        if (
            parsed_redirect.scheme != "https"
            or not parsed_redirect.netloc
            or parsed_redirect.username is not None
            or parsed_redirect.password is not None
        ):
            raise RuntimeError(
                "GitHub Actions artifact redirect is not safe HTTPS"
            )

        blob_request = urllib.request.Request(
            redirect_url,
            headers={"User-Agent": "hlp-phase1-artifacts"},
        )
        try:
            with urllib.request.urlopen(
                blob_request,
                timeout=timeout,
            ) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if (
                exc.code in _TRANSIENT_ARTIFACT_HTTP_CODES
                and attempt + 1 < attempt_count
            ):
                continue
            raise RuntimeError(
                "GitHub Actions redirected artifact download failed: "
                f"HTTP {exc.code}: {exc.reason}"
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt + 1 < attempt_count:
                continue
            raise RuntimeError(
                f"GitHub Actions redirected artifact download failed: {exc}"
            ) from exc

    raise RuntimeError("GitHub Actions artifact download retry loop exhausted")



def select_equivalent_artifact_retry(
    rows,
    *,
    label: str,
):
    """Collapse duplicate retry artifacts only when GitHub proves equivalence."""
    candidates = [dict(row) for row in rows]
    if not candidates:
        raise ValueError(f"{label} has no artifact candidates")
    if len(candidates) == 1:
        return candidates[0]

    names = {str(row.get("name") or "") for row in candidates}
    if len(names) != 1 or "" in names:
        raise ValueError(f"{label} duplicate artifact names disagree")

    digests = {str(row.get("digest") or "").lower() for row in candidates}
    if len(digests) != 1:
        raise ValueError(f"{label} duplicate artifact digests disagree")
    digest = next(iter(digests))
    if not digest.startswith("sha256:") or len(digest) != 71:
        raise ValueError(f"{label} duplicate artifact digest is invalid")
    try:
        int(digest.removeprefix("sha256:"), 16)
    except ValueError as exc:
        raise ValueError(
            f"{label} duplicate artifact digest is invalid"
        ) from exc

    sizes = {int(row.get("size_in_bytes", -1)) for row in candidates}
    if len(sizes) != 1 or next(iter(sizes)) < 0:
        raise ValueError(f"{label} duplicate artifact sizes disagree")

    workflow_bindings = set()
    for row in candidates:
        workflow_run = row.get("workflow_run")
        if not isinstance(workflow_run, dict):
            raise ValueError(
                f"{label} duplicate artifact workflow binding is missing"
            )
        workflow_bindings.add((
            int(workflow_run.get("id", 0)),
            str(workflow_run.get("head_sha") or ""),
            str(workflow_run.get("head_branch") or ""),
        ))
    if len(workflow_bindings) != 1:
        raise ValueError(
            f"{label} duplicate artifact workflow bindings disagree"
        )

    ids = []
    for row in candidates:
        artifact_id = int(row.get("id", 0))
        if artifact_id <= 0:
            raise ValueError(
                f"{label} duplicate artifact ID is invalid"
            )
        ids.append(artifact_id)
    if len(ids) != len(set(ids)):
        raise ValueError(f"{label} duplicate artifact IDs repeat")

    return max(candidates, key=lambda row: int(row["id"]))



_RESCUE_TERMINAL_BINDING_KEYS = (
    "run_id",
    "status",
    "conclusion",
    "head_sha",
    "display_title",
    "run_attempt",
    "reusable_gap_ids",
    "missing_success_artifacts",
    "non_success_gap_artifacts",
    "plan_artifact_present",
    "canonical_artifact_present",
)


def build_rescue_terminal_binding(
    *,
    run_id,
    status,
    conclusion,
    head_sha,
    display_title,
    run_attempt,
    reusable_gap_ids,
    missing_success_artifacts,
    non_success_gap_artifacts,
    plan_artifact_present,
    canonical_artifact_present,
):
    """Build the canonical launcher/child rescue terminal-state binding."""
    observed_run_id = int(run_id)
    if observed_run_id <= 0:
        raise ValueError("rescue terminal binding run ID must be positive")

    def gap_ids(values, *, label):
        normalized = [str(value) for value in values]
        if any(not value.isdigit() for value in normalized):
            raise ValueError(
                f"rescue terminal binding {label} contains invalid gap ID"
            )
        if len(normalized) != len(set(normalized)):
            raise ValueError(
                f"rescue terminal binding {label} contains duplicate gap ID"
            )
        return sorted(normalized, key=int)

    binding = {
        "run_id": observed_run_id,
        "status": status,
        "conclusion": conclusion,
        "head_sha": head_sha,
        "display_title": display_title,
        "run_attempt": run_attempt,
        "reusable_gap_ids": gap_ids(
            reusable_gap_ids,
            label="reusable gaps",
        ),
        "missing_success_artifacts": gap_ids(
            missing_success_artifacts,
            label="missing success artifacts",
        ),
        "non_success_gap_artifacts": gap_ids(
            non_success_gap_artifacts,
            label="non-success gap artifacts",
        ),
        "plan_artifact_present": bool(plan_artifact_present),
        "canonical_artifact_present": bool(canonical_artifact_present),
    }
    if tuple(binding) != _RESCUE_TERMINAL_BINDING_KEYS:
        raise AssertionError("rescue terminal binding schema changed")
    return binding


def rescue_terminal_binding_sha256(binding) -> str:
    """Hash a canonical rescue terminal binding exactly as the launcher does."""
    if not isinstance(binding, dict):
        raise ValueError("rescue terminal binding must be a dictionary")
    if tuple(binding) != _RESCUE_TERMINAL_BINDING_KEYS:
        raise ValueError("rescue terminal binding keys changed")
    return hashlib.sha256(
        json.dumps(
            binding,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
