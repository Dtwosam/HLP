"""Safe GitHub Actions metadata helpers used by Phase 1 accounting."""

from __future__ import annotations

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
