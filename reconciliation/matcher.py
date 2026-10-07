"""Match bank transactions against accounting records."""

from collections import deque

import pandas as pd


def find_exact_matches(
    bank: pd.DataFrame, accounting: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Pair bank and accounting records that share the same date and amount.

    Matching is one-to-one: each record is used in at most one pair. When
    several records share a key, the k-th bank record pairs with the k-th
    accounting record, following the row order of each DataFrame.

    Returns (matches, unmatched_bank, unmatched_accounting). matches has the
    columns bank_id and accounting_id; the unmatched DataFrames keep the
    columns and row order of the inputs. The inputs are not modified.
    """
    candidates = _build_candidate_queues(accounting)

    pairs = []
    for record in bank.itertuples(index=False):
        queue = candidates.get(_exact_key(record))
        if queue:
            # popleft() removes the candidate, so it can never be paired again.
            pairs.append((record.id, queue.popleft()))

    matches = pd.DataFrame(pairs, columns=["bank_id", "accounting_id"])
    unmatched_bank = bank[~bank["id"].isin(matches["bank_id"])]
    unmatched_accounting = accounting[~accounting["id"].isin(matches["accounting_id"])]
    return matches, unmatched_bank, unmatched_accounting


def _build_candidate_queues(accounting: pd.DataFrame) -> dict[tuple, deque]:
    """Group accounting ids by exact key, keeping row order inside each queue."""
    queues = {}
    for record in accounting.itertuples(index=False):
        queues.setdefault(_exact_key(record), deque()).append(record.id)
    return queues


def _exact_key(record) -> tuple:
    return (record.date, record.amount_cents)
