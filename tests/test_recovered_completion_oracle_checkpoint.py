from pathlib import Path


PROMOTED_ORACLE_RUN_ID = "34765335793"
OLD_ORACLE_RUN_ID = "33974681334"


def test_recovered_completion_uses_promoted_cbbtc_oracle_checkpoint() -> None:
    one_shot = Path(
        ".github/workflows/phase1-pons-recovered-completion-one-shot.yml"
    ).read_text()
    chain = Path(
        ".github/workflows/phase1-pons-recovered-completion-chain.yml"
    ).read_text()

    assert f'oracle_run_id: "{PROMOTED_ORACLE_RUN_ID}"' in one_shot
    assert chain.count(f'default: "{PROMOTED_ORACLE_RUN_ID}"') >= 2
    assert "\"run_id\": 34_765_335_793" in chain
    assert OLD_ORACLE_RUN_ID not in one_shot
    assert OLD_ORACLE_RUN_ID not in chain
