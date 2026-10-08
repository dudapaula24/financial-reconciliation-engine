"""Run the matching rules and consolidate their output into a single result."""

from enum import StrEnum

import pandas as pd

from reconciliation.matcher import find_amount_mismatches, find_exact_matches


class Status(StrEnum):
    """Reconciliation outcome of a pair of records or of a single record.

    BANK_ONLY and ACCOUNTING_ONLY mean the record could not be reconciled
    automatically, not necessarily that the transaction is missing on the
    other side.
    """

    MATCHED = "MATCHED"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    BANK_ONLY = "BANK_ONLY"
    ACCOUNTING_ONLY = "ACCOUNTING_ONLY"


# Text columns use the pandas string dtype and amounts use the nullable Int64
# dtype, so a missing value never turns an amount column into float.
RESULT_DTYPES = {
    "status": "str",
    "bank_id": "str",
    "accounting_id": "str",
    "date": "datetime64[us]",
    "bank_description": "str",
    "accounting_description": "str",
    "bank_amount_cents": "Int64",
    "accounting_amount_cents": "Int64",
    "difference_cents": "Int64",
}
RESULT_COLUMNS = list(RESULT_DTYPES)


def reconcile(bank: pd.DataFrame, accounting: pd.DataFrame) -> pd.DataFrame:
    """Reconcile bank records against accounting records.

    Exact matches are found first; the amount mismatch heuristic only runs on
    what is left. Each input record appears in exactly one row of the result.

    Rows are grouped by status (MATCHED, AMOUNT_MISMATCH, BANK_ONLY,
    ACCOUNTING_ONLY) and keep the input row order inside each group. Fields
    that do not apply to a status (e.g. accounting fields of a BANK_ONLY row)
    are missing. The inputs are not modified.
    """
    matches, unmatched_bank, unmatched_accounting = find_exact_matches(bank, accounting)
    mismatches, bank_only, accounting_only = find_amount_mismatches(
        unmatched_bank, unmatched_accounting
    )

    parts = [
        _paired_rows(matches.assign(difference_cents=0), bank, accounting, Status.MATCHED),
        _paired_rows(mismatches, bank, accounting, Status.AMOUNT_MISMATCH),
        _single_rows(_with_side_prefix(bank_only, "bank"), Status.BANK_ONLY),
        _single_rows(_with_side_prefix(accounting_only, "accounting"), Status.ACCOUNTING_ONLY),
    ]
    return pd.concat(parts, ignore_index=True)


def _paired_rows(
    pairs: pd.DataFrame, bank: pd.DataFrame, accounting: pd.DataFrame, status: Status
) -> pd.DataFrame:
    """Add the details of both records to each (bank_id, accounting_id) pair."""
    bank_details = _with_side_prefix(bank, "bank")
    # Both matching rules require the same date, so the bank date represents the pair.
    accounting_details = _with_side_prefix(accounting, "accounting").drop(columns="date")

    rows = pairs.merge(bank_details, on="bank_id", how="left", validate="one_to_one").merge(
        accounting_details, on="accounting_id", how="left", validate="one_to_one"
    )
    return _single_rows(rows, status)


def _single_rows(rows: pd.DataFrame, status: Status) -> pd.DataFrame:
    """Set the status and conform rows to the result columns and dtypes."""
    return rows.assign(status=status.value).reindex(columns=RESULT_COLUMNS).astype(RESULT_DTYPES)


def _with_side_prefix(records: pd.DataFrame, side: str) -> pd.DataFrame:
    """Rename loader columns to result columns, e.g. id -> bank_id."""
    return records.rename(
        columns={
            "id": f"{side}_id",
            "description": f"{side}_description",
            "amount_cents": f"{side}_amount_cents",
        }
    )
