from hlp.data.pons_v2 import filter_v2_registry_to_graduated


TOKEN = "0x" + "11" * 20
OTHER = "0x" + "22" * 20


def test_filter_v2_registry_to_graduated_preserves_launch_economics():
    registry = [
        {"token": TOKEN, "curve": "0x" + "33" * 20, "supply_raw": 123},
        {"token": OTHER, "curve": "0x" + "44" * 20, "supply_raw": 456},
    ]
    graduations = [{
        "token": TOKEN,
        "block_number": 20,
        "transaction_hash": "0x" + "aa" * 32,
        "transaction_index": 2,
        "log_index": 3,
    }]
    rows = filter_v2_registry_to_graduated(registry, graduations)
    assert len(rows) == 1
    assert rows[0]["token"] == TOKEN
    assert rows[0]["supply_raw"] == 123
    assert rows[0]["graduation_block"] == 20
