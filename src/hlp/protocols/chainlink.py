"""Chainlink AggregatorV3Interface point-in-time reads."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from hlp.config import normalize_address
from hlp.data.rpc import RpcClient
from hlp.data.types import RawLog
from hlp.protocols.evm import (
    data_words,
    event_topic,
    function_selector,
    signed_word,
    word_address,
)


DECIMALS_SELECTOR = function_selector("decimals()")
DESCRIPTION_SELECTOR = function_selector("description()")
LATEST_ROUND_DATA_SELECTOR = function_selector("latestRoundData()")
AGGREGATOR_SELECTOR = function_selector("aggregator()")
ANSWER_UPDATED_SIG = "AnswerUpdated(int256,uint256,uint256)"
ANSWER_UPDATED_TOPIC = event_topic(ANSWER_UPDATED_SIG)


@dataclass(frozen=True, slots=True)
class ChainlinkAnswerUpdate:
    aggregator: str
    answer_raw: int
    round_id: int
    updated_at: int
    block_number: int
    transaction_hash: str
    transaction_index: int | None
    log_index: int


@dataclass(frozen=True, slots=True)
class ChainlinkRound:
    feed: str
    round_id: int
    answer_raw: int
    started_at: int
    updated_at: int
    answered_in_round: int
    decimals: int
    description: str
    block_number: int

    @property
    def answer(self) -> Decimal:
        return Decimal(self.answer_raw) / (Decimal(10) ** self.decimals)


def _decode_uint(result: str) -> int:
    words = data_words(result)
    if len(words) != 1:
        raise ValueError("expected one ABI word")
    return words[0]


def _decode_dynamic_string(result: str) -> str:
    value = result.removeprefix("0x")
    if len(value) < 128:
        raise ValueError("ABI string result too short")
    offset = int(value[:64], 16)
    start = offset * 2
    if start + 64 > len(value):
        raise ValueError("ABI string offset out of bounds")
    length = int(value[start : start + 64], 16)
    data_start = start + 64
    data_end = data_start + length * 2
    if data_end > len(value):
        raise ValueError("ABI string data out of bounds")
    return bytes.fromhex(value[data_start:data_end]).decode("utf-8")


def read_chainlink_decimals(
    rpc: RpcClient,
    feed: str,
    *,
    block: int,
) -> int:
    value = _decode_uint(rpc.eth_call(normalize_address(feed), DECIMALS_SELECTOR, block))
    if value > 255:
        raise ValueError("Chainlink decimals exceeds uint8")
    return value


def read_chainlink_description(
    rpc: RpcClient,
    feed: str,
    *,
    block: int,
) -> str:
    return _decode_dynamic_string(
        rpc.eth_call(normalize_address(feed), DESCRIPTION_SELECTOR, block)
    )


def read_chainlink_latest_round(
    rpc: RpcClient,
    feed: str,
    *,
    block: int,
) -> ChainlinkRound:
    feed = normalize_address(feed)
    words = data_words(rpc.eth_call(feed, LATEST_ROUND_DATA_SELECTOR, block))
    if len(words) != 5:
        raise ValueError("unexpected latestRoundData result length")
    answer = signed_word(words[1])
    if answer <= 0:
        raise ValueError("Chainlink answer is not positive")
    decimals = read_chainlink_decimals(rpc, feed, block=block)
    description = read_chainlink_description(rpc, feed, block=block)
    return ChainlinkRound(
        feed=feed,
        round_id=words[0],
        answer_raw=answer,
        started_at=words[2],
        updated_at=words[3],
        answered_in_round=words[4],
        decimals=decimals,
        description=description,
        block_number=block,
    )



def read_chainlink_aggregator(
    rpc: RpcClient,
    feed: str,
    *,
    block: int,
) -> str:
    """Return the underlying aggregator selected by a Chainlink proxy."""
    words = data_words(
        rpc.eth_call(normalize_address(feed), AGGREGATOR_SELECTOR, block)
    )
    if len(words) != 1:
        raise ValueError("unexpected Chainlink aggregator() result length")
    return word_address(words[0])



def decode_chainlink_answer_updated(log: RawLog) -> ChainlinkAnswerUpdate:
    """Decode the standard Chainlink AnswerUpdated event.

    event AnswerUpdated(int256 indexed current, uint256 indexed roundId, uint256 updatedAt)
    """
    if not log.topics or log.topics[0] != ANSWER_UPDATED_TOPIC:
        raise ValueError("not a Chainlink AnswerUpdated event")
    if len(log.topics) != 3:
        raise ValueError("unexpected AnswerUpdated topic count")
    words = data_words(log.data)
    if len(words) != 1:
        raise ValueError("unexpected AnswerUpdated data length")
    answer = signed_word(int(log.topics[1], 16))
    if answer <= 0:
        raise ValueError("Chainlink AnswerUpdated answer is not positive")
    return ChainlinkAnswerUpdate(
        aggregator=log.address,
        answer_raw=answer,
        round_id=int(log.topics[2], 16),
        updated_at=words[0],
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
    )
