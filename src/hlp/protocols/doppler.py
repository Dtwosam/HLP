"""Doppler/Whetstone Airlock launch adapter for Robinhood Chain."""

from __future__ import annotations

from hlp.config import DOPPLER_AIRLOCK, normalize_address
from hlp.data.types import DopplerLaunch, RawLog
from hlp.protocols.evm import data_words, event_topic, topic_address, word_address


CREATE_SIG = "Create(address,address,address,address)"
CREATE_TOPIC = event_topic(CREATE_SIG)


def decode_doppler_launch(log: RawLog) -> DopplerLaunch:
    if log.address != normalize_address(DOPPLER_AIRLOCK):
        raise ValueError("not the canonical Doppler Airlock")
    if not log.topics or log.topics[0] != CREATE_TOPIC:
        raise ValueError("not Doppler Airlock Create")
    if len(log.topics) != 2:
        raise ValueError("unexpected Doppler Create topic count")
    words=data_words(log.data)
    if len(words)!=3:
        raise ValueError("unexpected Doppler Create data length")
    return DopplerLaunch(
        asset=word_address(words[0]),
        numeraire=topic_address(log.topics[1]),
        initializer=word_address(words[1]),
        pool_or_hook=word_address(words[2]),
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
    )
