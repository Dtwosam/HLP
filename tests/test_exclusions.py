import pytest

from hlp.config import ROBINHOOD_USDG, ROBINHOOD_WETH
from hlp.data.exclusions import (
    build_phase2_exclusion_registry,
    classify_excluded_asset,
    exclusion_map,
)


AAPL = "0x" + "11" * 20
IMPOSTOR = "0x" + "22" * 20
SYSTEM = "0x" + "33" * 20


def stock_row(address=AAPL):
    return {
        "asset_id": "apple",
        "token_symbol": "AAPL",
        "token_name": "Apple Robinhood Token",
        "contract_address": address,
        "chain_id": 4663,
        "token_decimals": 18,
        "status": "ASSET_STATUS_ACTIVE",
    }


def test_registry_contains_fixed_and_official_address_exclusions():
    rows = build_phase2_exclusion_registry([stock_row()])
    mapping = exclusion_map(rows)

    assert mapping[ROBINHOOD_WETH.lower()]["category"] == "wrapped_native"
    assert mapping[ROBINHOOD_USDG.lower()]["category"] == "stablecoin"
    assert mapping[AAPL]["category"] == "robinhood_canonical_asset"
    assert mapping[AAPL]["metadata"]["token_symbol"] == "AAPL"


def test_symbol_impersonator_is_not_excluded_without_address_identity():
    rows = build_phase2_exclusion_registry([stock_row()])
    assert classify_excluded_asset(AAPL, rows) is not None
    assert classify_excluded_asset(IMPOSTOR, rows) is None


def test_verified_system_asset_requires_explicit_provenance():
    rows = build_phase2_exclusion_registry(
        [],
        extra_verified_assets=[
            {
                "address": SYSTEM,
                "category": "protocol_system_token",
                "source": "verified_contract_registry",
                "reason": "protocol accounting token",
                "metadata": {"contract": "ExampleSystem"},
            }
        ],
    )
    row = classify_excluded_asset(SYSTEM, rows)
    assert row["source"] == "verified_contract_registry"
    assert row["reason"] == "protocol accounting token"


def test_wrong_chain_official_asset_fails_closed():
    with pytest.raises(ValueError, match="wrong chain"):
        build_phase2_exclusion_registry([{**stock_row(), "chain_id": 1}])


def test_unknown_extra_category_fails_closed():
    with pytest.raises(ValueError, match="unsupported category"):
        build_phase2_exclusion_registry(
            [],
            extra_verified_assets=[
                {
                    "address": SYSTEM,
                    "category": "looks_like_a_stock",
                    "source": "guess",
                    "reason": "ticker heuristic",
                }
            ],
        )


def test_duplicate_address_classification_fails_closed():
    with pytest.raises(ValueError, match="duplicate deterministic exclusion"):
        build_phase2_exclusion_registry(
            [stock_row(ROBINHOOD_WETH)],
        )
