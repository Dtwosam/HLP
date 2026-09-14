from types import SimpleNamespace

from hlp.cli import _v4_quote_tape_rpc
from hlp.config import DEFAULT_RPC_URL


def _args():
    return SimpleNamespace(timeout=1.0, attempts=1, min_interval=0.0)


def test_v4_quote_tape_defaults_to_official_rpc_without_archive_config(monkeypatch):
    monkeypatch.delenv("ROBINHOOD_ARCHIVE_RPC_URL", raising=False)
    monkeypatch.delenv("ROBINHOOD_ARCHIVE_RPC_API_KEY", raising=False)

    rpc = _v4_quote_tape_rpc(_args())

    assert rpc.url == DEFAULT_RPC_URL
    assert rpc.extra_headers is None
    assert rpc.route_label == "robinhood_public"


def test_v4_quote_tape_respects_explicit_archive_override(monkeypatch):
    monkeypatch.setenv("ROBINHOOD_ARCHIVE_RPC_URL", "https://example.invalid/rpc")
    monkeypatch.setenv("ROBINHOOD_ARCHIVE_RPC_API_KEY", "test-key")

    rpc = _v4_quote_tape_rpc(_args())

    assert rpc.url == "https://example.invalid/rpc"
    assert rpc.extra_headers == {"X-API-Key": "test-key"}
