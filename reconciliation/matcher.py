"""Match bank transactions against accounting records."""

from collections import deque
from collections.abc import Callable

import pandas as pd

KeyFunction = Callable[[tuple], tuple]


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
    matches = _pair_by_key(bank, accounting, _exact_key)
    unmatched_bank = _without_ids(bank, matches["bank_id"])
    unmatched_accounting = _without_ids(accounting, matches["accounting_id"])
    return matches, unmatched_bank, unmatched_accounting


def _pair_by_key(bank: pd.DataFrame, accounting: pd.DataFrame, key: KeyFunction) -> pd.DataFrame:
    """Pair records one-to-one when key(record) is equal, in row order (FIFO).

    Returns a DataFrame with the columns bank_id and accounting_id.
    """
    candidates = _build_candidate_queues(accounting, key)

    pairs = []
    for record in bank.itertuples(index=False):
        queue = candidates.get(key(record))
        if queue:
            # popleft() removes the candidate, so it can never be paired again.
            pairs.append((record.id, queue.popleft()))

    return pd.DataFrame(pairs, columns=["bank_id", "accounting_id"])


def _build_candidate_queues(records: pd.DataFrame, key: KeyFunction) -> dict[tuple, deque]:
    """Group record ids by key(record), keeping row order inside each queue."""
    queues = {}
    for record in records.itertuples(index=False):
        queues.setdefault(key(record), deque()).append(record.id)
    return queues


def _without_ids(records: pd.DataFrame, ids: pd.Series) -> pd.DataFrame:
    return records[~records["id"].isin(ids)]


def _exact_key(record) -> tuple:
    return (record.date, record.amount_cents)
