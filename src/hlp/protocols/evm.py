"""Small EVM ABI/event helpers used by protocol adapters."""

from __future__ import annotations

from eth_utils import keccak

from hlp.config import normalize_address


def event_topic(signature: str) -> str:
    return "0x" + keccak(text=signature).hex()


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


def word_address(value: int) -> str:
    if value < 0 or value >= 1 << 160:
        # ABI address values may be zero-padded but cannot carry high bits.
        if value >> 160:
            raise ValueError("ABI word contains non-address high bits")
    return normalize_address("0x" + f"{value & ((1 << 160) - 1):040x}")
