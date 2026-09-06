import io
import urllib.error

from hlp.data.github_actions import fetch_github_actions_job_log


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
