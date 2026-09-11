"""Small EVM ABI/event helpers used by protocol adapters."""

from __future__ import annotations

from eth_utils import keccak

from hlp.config import normalize_address


def event_topic(signature: str) -> str:
    return "0x" + keccak(text=signature).hex()


def function_selector(signature: str) -> str:
    return "0x" + keccak(text=signature)[:4].hex()


def topic_address(topic: str) -> str:
    value = topic.removeprefix("0x")
    if len(value) != 64:
        raise ValueError("indexed address topic must be 32 bytes")
    return normalize_address("0x" + value[-40:])


def data_words(data: str) -> tuple[int, ...]:
    value = data.removeprefix("0x")
    if len(value) % 64:
        raise ValueError("ABI data is not aligned to 32-byte words")
    return tuple(int(value[i : i + 64], 16) for i in range(0, len(value), 64))


def signed_word(value: int, bits: int = 256) -> int:
    """Interpret an ABI word as a signed two's-complement integer."""
    if bits <= 0 or bits > 256:
        raise ValueError("bits must be between 1 and 256")
    mask = (1 << bits) - 1
    narrowed = value & mask
    sign = 1 << (bits - 1)
    return narrowed - (1 << bits) if narrowed & sign else narrowed


def topic_bytes32(topic: str) -> str:
    value = topic.lower()
    if not value.startswith("0x") or len(value) != 66:
        raise ValueError("bytes32 topic must be 32 bytes")
    int(value[2:], 16)
    return value


def word_address(value: int) -> str:
    if value < 0 or value >= 1 << 160:
        # ABI address values may be zero-padded but cannot carry high bits.
        if value >> 160:
            raise ValueError("ABI word contains non-address high bits")
    return normalize_address("0x" + f"{value & ((1 << 160) - 1):040x}")



def abi_dynamic_bytes_at(data: str, head_word_index: int) -> bytes:
    """Decode one ABI dynamic bytes/string argument from event/call data."""
    value = data.removeprefix("0x")
    if len(value) % 64:
        raise ValueError("ABI data is not aligned to 32-byte words")
    head = head_word_index * 64
    if head < 0 or head + 64 > len(value):
        raise ValueError("ABI head word index out of bounds")
    offset_bytes = int(value[head : head + 64], 16)
    if offset_bytes % 32:
        raise ValueError("ABI dynamic offset is not word aligned")
    start = offset_bytes * 2
    if start + 64 > len(value):
        raise ValueError("ABI dynamic offset out of bounds")
    length = int(value[start : start + 64], 16)
    body_start = start + 64
    body_end = body_start + length * 2
    if body_end > len(value):
        raise ValueError("ABI dynamic body out of bounds")
    return bytes.fromhex(value[body_start:body_end])


def abi_string_at(data: str, head_word_index: int) -> str:
    return abi_dynamic_bytes_at(data, head_word_index).decode("utf-8")
