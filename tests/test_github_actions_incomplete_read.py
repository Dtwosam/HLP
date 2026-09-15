import http.client
import urllib.error

from hlp.data.github_actions import (
    fetch_github_actions_artifact_zip,
    fetch_github_actions_json,
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


def test_actions_metadata_retries_incomplete_read(monkeypatch):
    api_url = "https://api.github.com/repos/Dtwosam/HLP/actions/runs/127/jobs"
    seen = {"calls": 0}

    class IncompleteResponse(_Response):
        def read(self):
            raise http.client.IncompleteRead(b'{"total_count":', 100)

    class NoRedirectOpener:
        def open(self, request, timeout):
            seen["calls"] += 1
            if seen["calls"] == 1:
                return IncompleteResponse(b"")
            return _Response(b'{"total_count": 247, "jobs": []}')

    monkeypatch.setattr(
        "hlp.data.github_actions.urllib.request.build_opener",
        lambda *handlers: NoRedirectOpener(),
    )

    payload = fetch_github_actions_json(
        api_url,
        "secret-token",
        attempts=3,
    )

    assert payload == {"total_count": 247, "jobs": []}
    assert seen["calls"] == 2


def test_actions_artifact_retries_incomplete_redirected_blob(monkeypatch):
    api_url = (
        "https://api.github.com/repos/Dtwosam/HLP/"
        "actions/artifacts/903/zip"
    )
    blob_urls = [
        "https://results.blob.core.windows.net/actions/first.zip",
        "https://results.blob.core.windows.net/actions/second.zip",
    ]
    seen = {"api_calls": 0, "blob_calls": 0}

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

    class IncompleteResponse(_Response):
        def read(self):
            raise http.client.IncompleteRead(b"PK\x03\x04partial", 100)

    def flaky_blob(request, timeout):
        seen["blob_calls"] += 1
        if seen["blob_calls"] == 1:
            return IncompleteResponse(b"")
        return _Response(b"PK\x03\x04recovered")

    monkeypatch.setattr(
        "hlp.data.github_actions.urllib.request.build_opener",
        lambda *handlers: NoRedirectOpener(),
    )
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
