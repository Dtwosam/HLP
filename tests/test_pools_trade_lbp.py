from hlp.config import normalize_address
from hlp.data.types import RawLog
from hlp.protocols.pools_trade_lbp import (
    CCA_BID_EXITED_TOPIC,
    CCA_BID_SUBMITTED_TOPIC,
    CCA_CHECKPOINT_TOPIC,
    CCA_CLEARING_PRICE_TOPIC,
    INITIALIZER_CREATED_TOPIC,
    POOLS_TRADE_LBP_STRATEGY,
    decode_pools_trade_cca_bid_exited,
    decode_pools_trade_cca_bid_submitted,
    decode_pools_trade_cca_price_event,
    decode_pools_trade_lbp_initializer_created,
)


TOKEN = "0x" + "11" * 20
INITIALIZER = "0x" + "22" * 20
RECIPIENT = "0x" + "33" * 20
POSITION = "0x" + "44" * 20
ZERO = "0x" + "00" * 20


def word(value: int) -> str:
    return f"{value & ((1 << 256) - 1):064x}"


def addr_word(address: str) -> str:
    return address.removeprefix("0x").rjust(64, "0")


def topic_addr(address: str) -> str:
    return "0x" + addr_word(address)


def test_initializer_created_topic_matches_robinhood_lbp():
    assert INITIALIZER_CREATED_TOPIC == (
        "0x6d759545eb439f07e70f45431d6339af7a4f1ffef06d43e8ddf47fdb0799708c"
    )


def test_decode_lbp_initializer_created_static_head():
    words = [
        word(32),
        addr_word(TOKEN),
        addr_word(ZERO),
        word(30_100_000),
        word(200_000_000 * 10**18),
        addr_word(RECIPIENT),
        addr_word(POSITION),
        word(2500),
        word(50),
        addr_word(ZERO),
        word(352),
        word(576),
    ]
    # Dynamic tails are irrelevant to the fields HLP uses here.
    words += [word(0)] * 10
    log = RawLog(
        chain_id=4663,
        block_number=30_000_001,
        block_hash=None,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=1,
        log_index=2,
        address=normalize_address(POOLS_TRADE_LBP_STRATEGY),
        topics=(INITIALIZER_CREATED_TOPIC, topic_addr(INITIALIZER)),
        data="0x" + "".join(words),
        removed=False,
    )
    row = decode_pools_trade_lbp_initializer_created(log)
    assert row.initializer == INITIALIZER
    assert row.token == TOKEN
    assert row.currency == ZERO
    assert row.migration_block == 30_100_000
    assert row.reserved_token_amount_for_lp == 200_000_000 * 10**18
    assert row.pool_fee == 2500
    assert row.pool_tick_spacing == 50



def cca_raw(*, topic, words, block, log_index):
    return RawLog(
        chain_id=4663,
        block_number=block,
        block_hash=None,
        transaction_hash="0x" + "bb" * 32,
        transaction_index=2,
        log_index=log_index,
        address="0xc5137968f7e6802736ba40e59acd164071ba73cf",
        topics=(topic,),
        data="0x" + "".join(word(value) for value in words),
        removed=False,
    )


def test_observed_cca_price_topics_are_frozen():
    assert CCA_CLEARING_PRICE_TOPIC == (
        "0x30adbe996d7a69a21fdebcc1f8a46270"
        "bf6c22d505a7d872c1ab4767aa707609"
    )
    assert CCA_CHECKPOINT_TOPIC == (
        "0xf1e4b6d7d0d7c5deb6393a39862d66a2"
        "f2ecb034f3283a8a597f9bf0c36f76fa"
    )


def test_decode_observed_cca_clearing_price_event():
    row = decode_pools_trade_cca_price_event(
        cca_raw(
            topic=CCA_CLEARING_PRICE_TOPIC,
            words=[30_001_798, 41_616_825_089_465_157_800],
            block=30_001_798,
            log_index=4,
        )
    )
    assert row.event_type == "clearing_price"
    assert row.auction == (
        "0xc5137968f7e6802736ba40e59acd164071ba73cf"
    )
    assert row.checkpoint_block == 30_001_798
    assert row.clearing_price_x96 == 41_616_825_089_465_157_800
    assert row.cumulative_mps is None


def test_decode_observed_cca_checkpoint_event():
    row = decode_pools_trade_cca_price_event(
        cca_raw(
            topic=CCA_CHECKPOINT_TOPIC,
            words=[
                30_001_805,
                41_616_825_089_465_157_800,
                3_264,
            ],
            block=30_001_805,
            log_index=8,
        )
    )
    assert row.event_type == "checkpoint"
    assert row.checkpoint_block == 30_001_805
    assert row.clearing_price_x96 == 41_616_825_089_465_157_800
    assert row.cumulative_mps == 3_264



def test_decode_cca_bid_submitted_uses_event_owner_not_tx_sender():
    owner = "0x" + "55" * 20
    log = RawLog(
        chain_id=4663,
        block_number=30_493_314,
        block_hash=None,
        transaction_hash="0x" + "cc" * 32,
        transaction_index=8,
        log_index=46,
        address=INITIALIZER,
        topics=(
            CCA_BID_SUBMITTED_TOPIC,
            "0x" + word(7),
            topic_addr(owner),
        ),
        data="0x" + word(79_228_162_514_264_337_593_543_000) + word(100_500_000_000_000),
        removed=False,
    )
    row = decode_pools_trade_cca_bid_submitted(log)
    assert row.auction == INITIALIZER
    assert row.bid_id == 7
    assert row.owner == owner
    assert row.price_q96 == 79_228_162_514_264_337_593_543_000
    assert row.amount_raw == 100_500_000_000_000


def test_decode_cca_bid_exited_has_exact_fill_and_refund():
    owner = "0x" + "55" * 20
    log = RawLog(
        chain_id=4663,
        block_number=30_494_000,
        block_hash=None,
        transaction_hash="0x" + "dd" * 32,
        transaction_index=1,
        log_index=9,
        address=INITIALIZER,
        topics=(
            CCA_BID_EXITED_TOPIC,
            "0x" + word(7),
            topic_addr(owner),
        ),
        data="0x" + word(25 * 10**18) + word(500_000),
        removed=False,
    )
    row = decode_pools_trade_cca_bid_exited(log)
    assert row.bid_id == 7
    assert row.owner == owner
    assert row.tokens_filled_raw == 25 * 10**18
    assert row.currency_refunded_raw == 500_000
