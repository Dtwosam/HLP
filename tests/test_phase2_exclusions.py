import pytest

from hlp.config import ROBINHOOD_USDG, ROBINHOOD_WETH
from hlp.data.phase2_exclusions import (
    PHASE2_EXCLUSION_REGISTRY_VERSION,
    apply_phase2_exclusion_registry,
    build_phase2_exclusion_registry,
)


STOCK = "0x" + "11" * 20
MEME = "0x" + "22" * 20


def asset(address=STOCK, asset_id="aapl"):
    return {
        "asset_id": asset_id,
        "token_symbol": "AAPL",
        "token_name": "Apple",
        "contract_address": address,
        "chain_id": 4663,
        "token_decimals": 18,
        "status": "active",
    }


def test_exclusion_registry_is_address_based_and_includes_static_assets():
    rows, summary = build_phase2_exclusion_registry([asset()])
    by_address = {row["address"]: row for row in rows}

    assert summary["version"] == PHASE2_EXCLUSION_REGISTRY_VERSION
    assert summary["matching_semantics"] == "exact_normalized_address_only"
    assert summary["symbol_or_name_matching_allowed"] is False
    assert ROBINHOOD_WETH.lower() in by_address
    assert ROBINHOOD_USDG.lower() in by_address
    assert STOCK in by_address
    assert by_address[STOCK]["exclusion_class"] == (
        "robinhood_canonical_asset"
    )


def test_exclusion_registry_does_not_use_symbol_for_matching():
    rows, _ = build_phase2_exclusion_registry([asset()])
    included, excluded = apply_phase2_exclusion_registry(
        [MEME, STOCK],
        rows,
    )

    assert included == [MEME]
    assert [row["address"] for row in excluded] == [STOCK]


def test_exclusion_registry_rejects_empty_official_asset_population():
    with pytest.raises(ValueError, match="returned no chain assets"):
        build_phase2_exclusion_registry([])


def test_exclusion_registry_rejects_duplicate_official_address():
    with pytest.raises(ValueError, match="repeats address"):
        build_phase2_exclusion_registry([
            asset(),
            asset(asset_id="duplicate"),
        ])


def test_exclusion_registry_static_identity_precedes_official_overlap():
    rows, summary = build_phase2_exclusion_registry([
        asset(address=ROBINHOOD_WETH, asset_id="wrapped"),
    ])
    weth = next(
        row for row in rows
        if row["address"] == ROBINHOOD_WETH.lower()
    )

    assert weth["exclusion_class"] == "canonical_weth"
    assert weth["robinhood_asset_id"] == "wrapped"
    assert summary["official_robinhood_addresses"] == 1
