from pathlib import Path


WORKFLOW = Path(".github/workflows/phase2-archive-rpc-preflight.yml")


def test_phase2_archive_preflight_is_manual_and_read_only():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "git push" not in text


def test_phase2_archive_preflight_requires_authenticated_route():
    text = WORKFLOW.read_text()

    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" in text
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY is not configured" in text
    assert "SOLIDRPC_AUTH_RPC_URL" in text
    assert '"X-API-Key": key' in text
    assert "solidrpc_authenticated_free" in text


def test_phase2_archive_preflight_proves_wide_historical_access():
    text = WORKFLOW.read_text()

    assert "HISTORICAL_CODE_BLOCK: '8600612'" in text
    assert "WIDE_LOG_FROM: '8621500'" in text
    assert "WIDE_LOG_TO: '8622499'" in text
    assert "SOLIDRPC_PUBLIC_FILTERED_LOG_BLOCK_CAP" in text
    assert "wide_log_probe_exceeds_public_cap" in text
    assert "authenticated_archive_ready" in text
    assert "phase2-archive-rpc-preflight.json" in text
