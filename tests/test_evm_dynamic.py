from hlp.protocols.evm import abi_string_at


def word(value: int) -> str:
    return f"{value:064x}"


def test_abi_string_at_decodes_dynamic_head_offset():
    # (uint256,string): head[1] points to byte 64.
    raw = b"hello"
    padded = raw + b"\x00" * 27
    data = "0x" + word(7) + word(64) + word(len(raw)) + padded.hex()
    assert abi_string_at(data, 1) == "hello"
