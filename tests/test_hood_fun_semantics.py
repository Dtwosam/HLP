import pytest

from hlp.data.hood_fun_semantics import (
    HOOD_FUN_CURVE_SEMANTICS_VERSION,
    audit_hood_fun_curve_semantics,
)
from hlp.data.types import HoodFunEvent


TOKEN = "0x" + "11" * 20


def event(
    event_type,
    *,
    block,
    log,
    is_buy=None,
    quote=None,
    token_amount=None,
    fee=None,
    virtual_quote=None,
    virtual_token=None,
    inventory=None,
):
    return HoodFunEvent(
        event_type=event_type,
        token=TOKEN,
        actor="0x" + "22" * 20,
        is_buy=is_buy,
        quote_amount_raw=quote,
        token_amount_raw=token_amount,
        fee_raw=fee,
        virtual_quote_raw=virtual_quote,
        virtual_token_raw=virtual_token,
        curve_inventory_raw=inventory,
        name="x" if event_type == "token_created" else None,
        symbol="X" if event_type == "token_created" else None,
        metadata_uri=None,
        block_number=block,
        transaction_hash="0x" + f"{block:064x}",
        transaction_index=0,
        log_index=log,
    )


def registry():
    return [{
        "token": TOKEN,
        "launch_block": 10,
        "launch_transaction_index": 0,
        "launch_log_index": 1,
        "initial_virtual_quote_raw": 1000,
        "initial_virtual_token_raw": 5000,
    }]


def test_audit_hood_fun_curve_semantics_checks_sequential_reserves():
    rows = [
        event(
            "token_created",
            block=10,
            log=1,
            virtual_quote=1000,
            virtual_token=5000,
            inventory=4000,
        ),
        event(
            "trade",
            block=11,
            log=2,
            is_buy=True,
            quote=110,
            token_amount=100,
            fee=10,
            virtual_quote=1100,
            virtual_token=4900,
        ),
        event(
            "trade",
            block=12,
            log=3,
            is_buy=False,
            quote=50,
            token_amount=50,
            fee=5,
            virtual_quote=1055,
            virtual_token=4950,
        ),
    ]

    report = audit_hood_fun_curve_semantics(rows, registry())

    assert report["version"] == HOOD_FUN_CURVE_SEMANTICS_VERSION
    assert report["launches_checked"] == 1
    assert report["checked_sequential_trades"] == 2
    assert report["tokens_with_checked_trades"] == 1
    assert report["reserve_conservation_complete"] is True
    assert report["reserve_formula_counts"] == {
        "buy_plus_net": 1,
        "sell_minus_gross_plus_fee": 1,
    }


def test_audit_hood_fun_curve_semantics_rejects_token_reserve_drift():
    rows = [
        event(
            "token_created",
            block=10,
            log=1,
            virtual_quote=1000,
            virtual_token=5000,
            inventory=4000,
        ),
        event(
            "trade",
            block=11,
            log=2,
            is_buy=True,
            quote=110,
            token_amount=100,
            fee=10,
            virtual_quote=1100,
            virtual_token=4899,
        ),
    ]

    with pytest.raises(ValueError, match="token reserve conservation"):
        audit_hood_fun_curve_semantics(rows, registry())


def test_audit_hood_fun_curve_semantics_requires_linked_trade():
    rows = [
        event(
            "token_created",
            block=10,
            log=1,
            virtual_quote=1000,
            virtual_token=5000,
            inventory=4000,
        ),
    ]

    with pytest.raises(ValueError, match="no sequential"):
        audit_hood_fun_curve_semantics(rows, registry())
