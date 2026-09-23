from hlp.protocols.erc20 import SYMBOL_SELECTOR, read_erc20_symbol


TOKEN = "0x" + "11" * 20


def abi_string(value: str) -> str:
    raw = value.encode().hex()
    padded = raw.ljust(((len(raw) + 63) // 64) * 64, "0")
    return (
        "0x"
        + f"{32:064x}"
        + f"{len(value.encode()):064x}"
        + padded
    )


class StringRpc:
    def eth_call(self, token, selector, block):
        assert token == TOKEN
        assert selector == SYMBOL_SELECTOR
        assert block == 99
        return abi_string("cbBTC")


class Bytes32Rpc:
    def eth_call(self, token, selector, block):
        assert token == TOKEN
        assert selector == SYMBOL_SELECTOR
        return "0x" + "CBBTC".encode().hex().ljust(64, "0")


def test_read_erc20_symbol_standard_string():
    assert read_erc20_symbol(StringRpc(), TOKEN, block=99) == "cbBTC"


def test_read_erc20_symbol_legacy_bytes32():
    assert read_erc20_symbol(Bytes32Rpc(), TOKEN, block=99) == "CBBTC"
