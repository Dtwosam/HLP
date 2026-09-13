import re
from pathlib import Path


def test_run_artifact_listing_paginates_past_first_100(monkeypatch):
    from hlp.github_artifacts import list_run_artifacts

    calls = []
    pages = {
        1: [{"id": index, "name": f"artifact-{index}"} for index in range(100)],
        2: [{"id": index, "name": f"artifact-{index}"} for index in range(100, 172)],
    }

    def fake_get_json(url, token):
        match = re.search(r"[?&]page=(\d+)", url)
        assert match, url
        page = int(match.group(1))
        calls.append(page)
        return {"artifacts": pages.get(page, [])}

    artifacts = list_run_artifacts(
        repository="Dtwosam/HLP",
        run_id=34593238603,
        token="test-token",
        get_json=fake_get_json,
    )

    assert [artifact["id"] for artifact in artifacts] == list(range(172))
    assert calls == [1, 2]


def test_exact_v4_artifact_patterns_do_not_mix_shards_and_gaps():
    from hlp.github_artifacts import matching_artifacts

    artifacts = [
        {"id": 1, "name": "phase1-pons-v4-quote-fallback-0"},
        {"id": 2, "name": "phase1-pons-v4-quote-fallback-127"},
        {"id": 3, "name": "phase1-pons-v4-quote-fallback-gap-000"},
        {"id": 4, "name": "phase1-pons-v4-quote-fallback-gap-plan"},
        {"id": 5, "name": "phase1-pons-v4-quote-fallback-full"},
        {"id": 6, "name": "phase1-pons-v4-quote-routes-selected"},
    ]

    shards = matching_artifacts(
        artifacts,
        r"^phase1-pons-v4-quote-fallback-[0-9]+$",
    )
    gaps = matching_artifacts(
        artifacts,
        r"^phase1-pons-v4-quote-fallback-gap-[0-9]{3}$",
    )

    assert [artifact["id"] for artifact in shards] == [1, 2]
    assert [artifact["id"] for artifact in gaps] == [3]


def test_v4_gap_recovery_uses_paginated_exact_artifact_downloads():
    workflow = (
        Path(__file__).parents[1]
        / ".github"
        / "workflows"
        / "phase1-pons-v4-quote-fallback-recover-gaps.yml"
    ).read_text()

    assert workflow.count("python -m hlp.github_artifacts download-run") >= 4
    assert "^phase1-pons-v4-quote-fallback-[0-9]+$" in workflow
    assert "^phase1-pons-v4-quote-fallback-gap-[0-9]{3}$" in workflow
    assert 'Path("partial-gaps").glob(' in workflow
    assert 'Path("partial-gaps").glob("v4-quote-events-gap-*.jsonl")' in workflow
