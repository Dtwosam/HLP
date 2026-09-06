"""Safe GitHub Actions metadata helpers used by Phase 1 accounting."""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request


_REDIRECT_CODES = {301, 302, 303, 307, 308}


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
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(
            f"GitHub Actions redirected log download failed: {exc}"
        ) from exc
    return payload.decode(errors="replace")
