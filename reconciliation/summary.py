"""Summarize a reconciliation result by status."""

import pandas as pd

from reconciliation.reconciler import Status

SUMMARY_COLUMNS = ["status", "items", "bank_records", "accounting_records"]


def summarize(result: pd.DataFrame) -> pd.DataFrame:
    """Count items and records for each status of a reconciliation result.

    items is the number of result rows, so a matched pair counts as one item.
    bank_records and accounting_records count the filled ids on each side, so
    a pair counts once on each side and never twice on the same side.

    All four statuses are always listed, in Status order, including those
    with zero rows. No total row is added. The input is not modified.
    """
    rows = []
    for status in Status:
        group = result[result["status"] == status]
        rows.append(
            {
                "status": status.value,
                "items": len(group),
                "bank_records": int(group["bank_id"].notna().sum()),
                "accounting_records": int(group["accounting_id"].notna().sum()),
            }
        )
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)
