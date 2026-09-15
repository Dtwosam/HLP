from hlp.config import POOLS_FUN_FACTORY
from hlp.data.types import RawLog
from hlp.protocols.evm import event_topic
from hlp.protocols.pools_fun import (
    TOKEN_LAUNCHED_SIG,
    TOKEN_LAUNCHED_TOPIC,
    decode_pools_fun_launch,
)


TOKEN="0x"+"11"*20
POOL="0x"+"22"*20
CREATOR="0x"+"33"*20
PAIR="0x"+"44"*20
DEPLOYER="0x"+"55"*20
RECIPIENT="0x"+"66"*20


def word(v:int)->str:
    return f"{v & ((1<<256)-1):064x}"


def addr_word(a:str)->str:
    return a.removeprefix("0x").rjust(64,"0")


def topic_addr(a:str)->str:
    return "0x"+addr_word(a)


def test_decode_pools_fun_launch():
    uri=b"ipfs://abc"
    padded=uri+b"\x00"*((32-len(uri)%32)%32)
    # 6-word non-indexed head, metadata offset at head[4].
    data=(
        "0x"
        +addr_word(PAIR)
        +addr_word(DEPLOYER)
        +addr_word(RECIPIENT)
        +word((1<<256)-200)
        +word(6*32)
        +word(123)
        +word(len(uri))
        +padded.hex()
    )
    log=RawLog(
        chain_id=4663,block_number=10,block_hash=None,
        transaction_hash="0x"+"aa"*32,transaction_index=1,log_index=2,
        address=POOLS_FUN_FACTORY.lower(),
        topics=(
            TOKEN_LAUNCHED_TOPIC,
            topic_addr(TOKEN),
            topic_addr(POOL),
            topic_addr(CREATOR),
        ),
        data=data,removed=False,
    )
    row=decode_pools_fun_launch(log)
    assert TOKEN_LAUNCHED_TOPIC==event_topic(TOKEN_LAUNCHED_SIG)
    assert row.token==TOKEN
    assert row.pool==POOL
    assert row.paired_asset==PAIR
    assert row.creator==CREATOR
    assert row.deployer==DEPLOYER
    assert row.fee_recipient==RECIPIENT
    assert row.start_tick==-200
    assert row.metadata_uri=="ipfs://abc"
    assert row.dev_buy_amount_out==123
