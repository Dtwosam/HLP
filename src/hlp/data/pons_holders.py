"""ERC-20 transfer acquisition and holder-state replay for Pons samples."""

from __future__ import annotations

from dataclasses import asdict
from typing import Iterable, Iterator

from hlp.config import normalize_address
from hlp.data.reconstruct import event_order
from hlp.data.rpc import RpcClient
from hlp.protocols.erc20 import TRANSFER_TOPIC, decode_erc20_transfer


ZERO_ADDRESS = "0x" + "00" * 20


def fetch_pons_transfer_rows(
    rpc: RpcClient,
    tokens: Iterable[str],
    *,
    from_block: int,
    to_block: int,
    chunk_size: int = 2_000,
    min_chunk_size: int = 25,
) -> Iterator[dict]:
    """Fetch ERC-20 Transfer logs for a bounded representative token set."""
    token_set = {
        normalize_address(token)
        for token in tokens
    }
    if not token_set:
        raise ValueError("at least one Pons token is required")
    if len(token_set) > 50:
        raise ValueError(
            "representative transfer tape is capped at 50 tokens per request"
        )
    if from_block < 0 or to_block < from_block:
        raise ValueError("invalid representative transfer range")

    logs = rpc.iter_logs_chunked(
        from_block,
        to_block,
        address=sorted(token_set),
        topics=[TRANSFER_TOPIC],
        chunk_size=chunk_size,
        min_chunk_size=min_chunk_size,
    )
    previous = None
    for raw in logs:
        row = asdict(decode_erc20_transfer(raw))
        token = normalize_address(row["token"])
        if token not in token_set:
            raise ValueError(
                f"transfer filter returned unexpected token {token}"
            )
        row["token"] = token
        row["from_address"] = normalize_address(row["from_address"])
        row["to_address"] = normalize_address(row["to_address"])
        order = event_order(row)
        if previous is not None and order <= previous:
            raise ValueError(
                "representative transfer tape is not strictly chronological"
            )
        previous = order
        yield row


def reconstruct_pons_holder_states(
    transfer_rows: Iterable[dict],
) -> list[dict]:
    """Replay exact ERC-20 balances and holder count after every transfer.

    The input must begin early enough to include the token's initial mint.
    Any debit that would make a balance negative is treated as evidence that
    the transfer history is incomplete and fails closed.
    """
    rows = [dict(row) for row in transfer_rows]
    rows.sort(key=lambda row: (event_order(row), row["token"].lower()))

    balances: dict[str, dict[str, int]] = {}
    holder_counts: dict[str, int] = {}
    supplies: dict[str, int] = {}
    previous_by_token: dict[str, tuple[int, int, int]] = {}
    output: list[dict] = []

    for source in rows:
        token = normalize_address(source["token"])
        from_address = normalize_address(source["from_address"])
        to_address = normalize_address(source["to_address"])
        value = int(source["value_raw"])
        if value < 0:
            raise ValueError("ERC-20 transfer value cannot be negative")

        order = event_order(source)
        prior_order = previous_by_token.get(token)
        if prior_order is not None and order <= prior_order:
            raise ValueError(
                f"transfer history is not strictly chronological for {token}"
            )
        previous_by_token[token] = order

        token_balances = balances.setdefault(token, {})
        holder_count = holder_counts.setdefault(token, 0)
        supply = supplies.setdefault(token, 0)

        if from_address == to_address:
            if from_address != ZERO_ADDRESS:
                current = token_balances.get(from_address, 0)
                if current < value:
                    raise ValueError(
                        "incomplete transfer history: self-transfer exceeds "
                        f"known balance for {token} {from_address}"
                    )
            from_after = (
                None
                if from_address == ZERO_ADDRESS
                else token_balances.get(from_address, 0)
            )
            to_after = (
                None
                if to_address == ZERO_ADDRESS
                else token_balances.get(to_address, 0)
            )
        else:
            if from_address != ZERO_ADDRESS:
                current = token_balances.get(from_address, 0)
                if current < value:
                    raise ValueError(
                        "incomplete transfer history: debit exceeds known "
                        f"balance for {token} {from_address}"
                    )
                next_balance = current - value
                token_balances[from_address] = next_balance
                if current > 0 and next_balance == 0:
                    holder_count -= 1
                from_after = next_balance
            else:
                supply += value
                from_after = None

            if to_address != ZERO_ADDRESS:
                current = token_balances.get(to_address, 0)
                next_balance = current + value
                token_balances[to_address] = next_balance
                if current == 0 and next_balance > 0:
                    holder_count += 1
                to_after = next_balance
            else:
                if supply < value:
                    raise ValueError(
                        "incomplete transfer history: burn exceeds accounted "
                        f"supply for {token}"
                    )
                supply -= value
                to_after = None

        holder_counts[token] = holder_count
        supplies[token] = supply

        if holder_count < 0:
            raise ValueError(f"negative holder count for {token}")
        if supply < 0:
            raise ValueError(f"negative accounted supply for {token}")

        out = dict(source)
        out.update(
            {
                "token": token,
                "from_address": from_address,
                "to_address": to_address,
                "is_mint": from_address == ZERO_ADDRESS,
                "is_burn": to_address == ZERO_ADDRESS,
                "from_balance_after_raw": from_after,
                "to_balance_after_raw": to_after,
                "holder_count_after": holder_count,
                "accounted_supply_after_raw": supply,
            }
        )
        output.append(out)

    for token, token_balances in balances.items():
        positive_supply = sum(
            balance
            for address, balance in token_balances.items()
            if address != ZERO_ADDRESS and balance > 0
        )
        if positive_supply != supplies[token]:
            raise ValueError(
                "holder replay supply mismatch for "
                f"{token}: balances={positive_supply} "
                f"accounted={supplies[token]}"
            )
        observed_holders = sum(
            balance > 0
            for address, balance in token_balances.items()
            if address != ZERO_ADDRESS
        )
        if observed_holders != holder_counts[token]:
            raise ValueError(
                "holder replay count mismatch for "
                f"{token}: balances={observed_holders} "
                f"tracked={holder_counts[token]}"
            )

    return output


def summarize_pons_holder_states(
    holder_rows: Iterable[dict],
) -> list[dict]:
    """Return the final accounted holder state for every sampled token."""
    latest: dict[str, dict] = {}
    transfer_counts: dict[str, int] = {}
    mint_counts: dict[str, int] = {}
    burn_counts: dict[str, int] = {}

    for source in holder_rows:
        row = dict(source)
        token = normalize_address(row["token"])
        prior = latest.get(token)
        if prior is not None and event_order(row) <= event_order(prior):
            raise ValueError(
                f"holder state rows are not chronological for {token}"
            )
        latest[token] = row
        transfer_counts[token] = transfer_counts.get(token, 0) + 1
        mint_counts[token] = mint_counts.get(token, 0) + int(
            bool(row.get("is_mint"))
        )
        burn_counts[token] = burn_counts.get(token, 0) + int(
            bool(row.get("is_burn"))
        )

    output = []
    for token, row in latest.items():
        output.append(
            {
                "token": token,
                "last_block_number": int(row["block_number"]),
                "last_transaction_index": row.get("transaction_index"),
                "last_log_index": int(row["log_index"]),
                "transfers": transfer_counts[token],
                "mints": mint_counts[token],
                "burns": burn_counts[token],
                "holder_count": int(row["holder_count_after"]),
                "accounted_supply_raw": int(
                    row["accounted_supply_after_raw"]
                ),
            }
        )
    output.sort(key=lambda row: row["token"])
    return output
