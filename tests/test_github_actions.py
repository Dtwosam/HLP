import io
import urllib.error

import pytest

from hlp.data.github_actions import (
    GitHubActionsJobLogUnavailable,
    fetch_github_actions_artifact_zip,
    fetch_github_actions_job_log,
)


class _Response:
    def __init__(self, payload: bytes):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._payload


def test_actions_log_redirect_does_not_forward_github_token(monkeypatch):
    api_url = "https://api.github.com/repos/Dtwosam/HLP/actions/jobs/123/logs"
    blob_url = "https://results.blob.core.windows.net/actions/job-log.txt"
    seen = {}

    class NoRedirectOpener:
        def open(self, request, timeout):
            seen["api_headers"] = dict(request.header_items())
            raise urllib.error.HTTPError(
                api_url,
                302,
                "Found",
                {"Location": blob_url},
                None,
            )

    def fake_build_opener(*handlers):
        seen["handlers"] = handlers
        return NoRedirectOpener()

    def fake_urlopen(request, timeout):
        seen["blob_url"] = request.full_url
        seen["blob_headers"] = dict(request.header_items())
        return _Response(b'{"requests_made": 7}\n')

    monkeypatch.setattr(
        "hlp.data.github_actions.urllib.request.build_opener",
        fake_build_opener,
    )
    monkeypatch.setattr(
        "hlp.data.github_actions.urllib.request.urlopen",
        fake_urlopen,
    )

    log = fetch_github_actions_job_log(
        api_url,
        "secret-token",
        timeout=60,
    )

    assert log == '{"requests_made": 7}\n'
    assert seen["blob_url"] == blob_url
    assert seen["api_headers"]["Authorization"] == "Bearer secret-token"
    assert "Authorization" not in seen["blob_headers"]


def test_actions_log_missing_redirect_blob_is_classified(monkeypatch):
    api_url = "https://api.github.com/repos/Dtwosam/HLP/actions/jobs/456/logs"
    blob_url = "https://results.blob.core.windows.net/actions/missing-log.txt"

    class NoRedirectOpener:
        def open(self, request, timeout):
            raise urllib.error.HTTPError(
                api_url,
                302,
                "Found",
                {"Location": blob_url},
                None,
            )

    monkeypatch.setattr(
        "hlp.data.github_actions.urllib.request.build_opener",
        lambda *handlers: NoRedirectOpener(),
    )

    def missing_blob(request, timeout):
        raise urllib.error.HTTPError(
            blob_url,
            404,
            "Not Found",
            {},
            io.BytesIO(b"gone"),
        )

    monkeypatch.setattr(
        "hlp.data.github_actions.urllib.request.urlopen",
        missing_blob,
    )

    with pytest.raises(
        GitHubActionsJobLogUnavailable,
        match="log blob is unavailable",
    ):
        fetch_github_actions_job_log(api_url, "secret-token")



def test_actions_artifact_redirect_does_not_forward_github_token(monkeypatch):
    api_url = (
        "https://api.github.com/repos/Dtwosam/HLP/"
        "actions/artifacts/789/zip"
    )
    blob_url = (
        "https://results.blob.core.windows.net/actions/artifact.zip"
    )
    seen = {}

    class NoRedirectOpener:
        def open(self, request, timeout):
            seen["api_headers"] = dict(request.header_items())
            raise urllib.error.HTTPError(
                api_url,
                302,
                "Found",
                {"Location": blob_url},
                None,
            )

    monkeypatch.setattr(
        "hlp.data.github_actions.urllib.request.build_opener",
        lambda *handlers: NoRedirectOpener(),
    )

    def fake_urlopen(request, timeout):
        seen["blob_url"] = request.full_url
        seen["blob_headers"] = dict(request.header_items())
        return _Response(b"PK\x03\x04zip")

    monkeypatch.setattr(
        "hlp.data.github_actions.urllib.request.urlopen",
        fake_urlopen,
    )

    payload = fetch_github_actions_artifact_zip(
        api_url,
        "secret-token",
        timeout=60,
    )

    assert payload == b"PK\x03\x04zip"
    assert seen["blob_url"] == blob_url
    assert seen["api_headers"]["Authorization"] == "Bearer secret-token"
    assert "Authorization" not in seen["blob_headers"]

def test_actions_artifact_retries_transient_blob_failure_with_fresh_redirect(
    monkeypatch,
):
    api_url = (
        "https://api.github.com/repos/Dtwosam/HLP/"
        "actions/artifacts/900/zip"
    )
    blob_urls = [
        "https://results.blob.core.windows.net/actions/first.zip",
        "https://results.blob.core.windows.net/actions/second.zip",
    ]
    seen = {
        "api_calls": 0,
        "blob_calls": 0,
        "blob_headers": [],
    }

    class NoRedirectOpener:
        def open(self, request, timeout):
            index = seen["api_calls"]
            seen["api_calls"] += 1
            raise urllib.error.HTTPError(
                api_url,
                302,
                "Found",
                {"Location": blob_urls[index]},
                None,
            )

    monkeypatch.setattr(
        "hlp.data.github_actions.urllib.request.build_opener",
        lambda *handlers: NoRedirectOpener(),
    )

    def flaky_blob(request, timeout):
        seen["blob_calls"] += 1
        seen["blob_headers"].append(dict(request.header_items()))
        if seen["blob_calls"] == 1:
            raise urllib.error.HTTPError(
                request.full_url,
                503,
                "Service Unavailable",
                {},
                io.BytesIO(b"retry"),
            )
        return _Response(b"PK\x03\x04recovered")

    monkeypatch.setattr(
        "hlp.data.github_actions.urllib.request.urlopen",
        flaky_blob,
    )

    payload = fetch_github_actions_artifact_zip(
        api_url,
        "secret-token",
        attempts=3,
    )

    assert payload == b"PK\x03\x04recovered"
    assert seen["api_calls"] == 2
    assert seen["blob_calls"] == 2
    assert all(
        "Authorization" not in headers
        for headers in seen["blob_headers"]
    )


def test_actions_artifact_retries_transient_api_failure(monkeypatch):
    api_url = (
        "https://api.github.com/repos/Dtwosam/HLP/"
        "actions/artifacts/901/zip"
    )
    blob_url = (
        "https://results.blob.core.windows.net/actions/retry.zip"
    )
    seen = {"api_calls": 0}

    class NoRedirectOpener:
        def open(self, request, timeout):
            seen["api_calls"] += 1
            if seen["api_calls"] == 1:
                raise urllib.error.HTTPError(
                    api_url,
                    503,
                    "Service Unavailable",
                    {},
                    io.BytesIO(b"retry"),
                )
            raise urllib.error.HTTPError(
                api_url,
                302,
                "Found",
                {"Location": blob_url},
                None,
            )

    monkeypatch.setattr(
        "hlp.data.github_actions.urllib.request.build_opener",
        lambda *handlers: NoRedirectOpener(),
    )
    monkeypatch.setattr(
        "hlp.data.github_actions.urllib.request.urlopen",
        lambda request, timeout: _Response(b"PK\x03\x04api-recovered"),
    )

    payload = fetch_github_actions_artifact_zip(
        api_url,
        "secret-token",
        attempts=3,
    )

    assert payload == b"PK\x03\x04api-recovered"
    assert seen["api_calls"] == 2


def test_actions_artifact_attempts_must_be_positive():
    with pytest.raises(
        ValueError,
        match="artifact attempts must be positive",
    ):
        fetch_github_actions_artifact_zip(
            "https://api.github.com/repos/Dtwosam/HLP/"
            "actions/artifacts/902/zip",
            "secret-token",
            attempts=0,
        )

