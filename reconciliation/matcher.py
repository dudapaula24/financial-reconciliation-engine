"""Match bank transactions against accounting records."""

from collections import Counter, deque
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


def find_amount_mismatches(
    unmatched_bank: pd.DataFrame, unmatched_accounting: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Pair leftover records that share date and description but differ in amount.

    Expects the unmatched DataFrames returned by find_exact_matches. Matching
    by description is a simple heuristic and may produce false positives
    (e.g. two different payments to the same supplier on the same day).

    The rule is conservative: a pair is formed only when its key
    (date, normalized description) appears exactly once on each side. Records
    whose key is ambiguous stay in the unmatched DataFrames for manual review.

    Returns (mismatches, unmatched_bank, unmatched_accounting). mismatches has
    the columns bank_id, accounting_id and difference_cents, where
    difference_cents = bank amount_cents - accounting amount_cents. The
    unmatched DataFrames keep the columns and row order of the inputs. The
    inputs are not modified.

    Raises ValueError if a pair has equal amounts, which means the inputs were
    not the leftovers of find_exact_matches.
    """
    pairs = _pair_by_key(
        _with_unique_keys(unmatched_bank, _description_key),
        _with_unique_keys(unmatched_accounting, _description_key),
        _description_key,
    )

    bank_amounts = unmatched_bank.set_index("id")["amount_cents"]
    accounting_amounts = unmatched_accounting.set_index("id")["amount_cents"]
    differences = pairs["bank_id"].map(bank_amounts) - pairs["accounting_id"].map(accounting_amounts)

    equal_amounts = pairs[differences == 0]
    if not equal_amounts.empty:
        listed = ", ".join(
            f"{bank_id}/{accounting_id}"
            for bank_id, accounting_id in zip(equal_amounts["bank_id"], equal_amounts["accounting_id"])
        )
        raise ValueError(
            f"Records with equal amounts are not amount mismatches: {listed}. "
            "Pass the unmatched records returned by find_exact_matches."
        )

    mismatches = pairs.assign(difference_cents=differences.astype("int64"))
    remaining_bank = _without_ids(unmatched_bank, mismatches["bank_id"])
    remaining_accounting = _without_ids(unmatched_accounting, mismatches["accounting_id"])
    return mismatches, remaining_bank, remaining_accounting


def normalize_description(text: str) -> str:
    """Normalize a description so that it can be compared with another one.

    Strips surrounding whitespace, collapses repeated inner whitespace into a
    single space and ignores letter case with casefold(). Accents, punctuation
    and abbreviations are intentionally left unchanged.

    Example: "  DELTA   Logistics " -> "delta logistics"
    """
    return " ".join(text.split()).casefold()


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


def _with_unique_keys(records: pd.DataFrame, key: KeyFunction) -> pd.DataFrame:
    """Keep only the records whose key appears exactly once in records."""
    keys = [key(record) for record in records.itertuples(index=False)]
    counts = Counter(keys)
    return records.loc[[counts[k] == 1 for k in keys]]


def _without_ids(records: pd.DataFrame, ids: pd.Series) -> pd.DataFrame:
    return records[~records["id"].isin(ids)]


def _exact_key(record) -> tuple:
    return (record.date, record.amount_cents)


def _description_key(record) -> tuple:
    return (record.date, normalize_description(record.description))
