from hlp.data.flap_registry import (
    build_flap_launch_registry,
    build_flap_launch_registry_ordered,
)
from hlp.data.types import FlapEvent


TOKEN = "0x" + "11" * 20
ZERO = "0x" + "00" * 20


def event(
    kind,
    *,
    logi,
    actor=None,
    value=None,
    value2=None,
    amount=None,
    quote_amount=None,
    pool=None,
):
    return FlapEvent(
        event_type=kind,
        token=TOKEN,
        actor=actor,
        amount_raw=amount,
        quote_amount_raw=quote_amount,
        fee_raw=None,
        post_price_raw=None,
        value_raw=value,
        value2_raw=value2,
        pool=pool,
        name="Cat" if kind == "token_created" else None,
        symbol="CAT" if kind == "token_created" else None,
        meta="ipfs://cat" if kind == "token_created" else None,
        block_number=10,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=1,
        log_index=logi,
    )


def test_build_flap_registry_from_creation_config_events():
    rows = build_flap_launch_registry(
        [
            event("token_created", logi=0, actor="0x" + "22" * 20, value=7),
            event("curve_set_v2", logi=1, value=1, value2=2, amount=3),
            event("dex_supply_thresh_set", logi=2, value=800),
            event("quote_set", logi=3, actor=ZERO),
            event("migrator_set", logi=4, value=1),
            event("token_version_set", logi=5, value=7),
            event("dex_preference_set", logi=6, value=2, value2=1),
            event(
                "launched_to_dex",
                logi=7,
                amount=700,
                quote_amount=300,
                pool="0x" + "44" * 20,
            ),
            event("dex_preference_set", logi=8, value=9, value2=7),
        ]
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["token"] == TOKEN
    assert row["quote_token"] == ZERO
    assert row["quote_set_block"] == 10
    assert row["quote_set_transaction_index"] == 1
    assert row["quote_set_log_index"] == 3
    assert row["r"] == 1 and row["h"] == 2 and row["k"] == 3
    assert row["dex_supply_thresh_raw"] == 800
    assert row["migrator_type"] == 1
    assert row["dex_id"] == 9
    assert row["lp_fee_profile"] == 7
    assert row["graduation_pool"] == "0x" + "44" * 20
    assert row["graduation_block"] == 10
    assert row["graduation_log_index"] == 7
    assert row["graduation_token_amount_raw"] == 700
    assert row["graduation_quote_amount_raw"] == 300
    assert row["graduation_quote_token"] == ZERO
    assert row["graduation_dex_id"] == 2
    assert row["graduation_lp_fee_profile"] == 1
    assert row["graduation_migrator_type"] == 1
    assert row["graduation_token_version"] == 7
    assert row["supply_raw"] == 1_000_000_000 * 10**18


def test_flap_registry_rejects_duplicate_graduation():
    import pytest

    pool = "0x" + "44" * 20
    rows = [
        event("token_created", logi=0, actor="0x" + "22" * 20),
        event("quote_set", logi=1, actor=ZERO),
        event("launched_to_dex", logi=2, pool=pool),
        event("launched_to_dex", logi=3, pool=pool),
    ]
    with pytest.raises(ValueError, match="duplicate Flap LaunchedToDEX"):
        build_flap_launch_registry(rows)


def test_ordered_flap_registry_rejects_chronology_drift():
    import pytest

    rows = [
        event("token_created", logi=2, actor="0x" + "22" * 20),
        event("quote_set", logi=1, actor=ZERO),
    ]
    with pytest.raises(ValueError, match="not chronological"):
        build_flap_launch_registry_ordered(rows)


def test_ordered_flap_registry_matches_sorting_wrapper():
    rows = [
        event("quote_set", logi=2, actor=ZERO),
        event("token_created", logi=0, actor="0x" + "22" * 20),
        event("curve_set_v2", logi=1, value=1, value2=2, amount=3),
    ]
    ordered = sorted(
        rows,
        key=lambda row: (
            row.block_number,
            -1 if row.transaction_index is None else row.transaction_index,
            row.log_index,
        ),
    )
    assert build_flap_launch_registry_ordered(ordered) == (
        build_flap_launch_registry(rows)
    )


def test_flap_registry_preserves_quote_history():
    quote_a = "0x" + "33" * 20
    quote_b = "0x" + "44" * 20
    rows = build_flap_launch_registry([
        event("token_created", logi=0, actor="0x" + "22" * 20),
        event("quote_set", logi=1, actor=quote_a),
        event("quote_set", logi=3, actor=quote_b),
    ])

    row = rows[0]
    assert row["quote_token"] == quote_b
    assert row["quote_history"] == [
        {
            "quote_token": quote_a,
            "block_number": 10,
            "transaction_index": 1,
            "log_index": 1,
        },
        {
            "quote_token": quote_b,
            "block_number": 10,
            "transaction_index": 1,
            "log_index": 3,
        },
    ]

