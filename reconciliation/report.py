"""Write a reconciliation result to a CSV report."""

import os
import tempfile
from decimal import Decimal
from pathlib import Path

import pandas as pd

DATE_FORMAT = "%Y-%m-%d"

# Internal amount columns (integer cents) and their names in the report (decimal amounts).
AMOUNT_COLUMNS = {
    "bank_amount_cents": "bank_amount",
    "accounting_amount_cents": "accounting_amount",
    "difference_cents": "difference",
}


def format_cents(cents: int) -> str:
    """Format integer cents as a decimal amount, e.g. -35000 -> "-350.00".

    scaleb(-2) divides by 100 exactly and always keeps two decimal places,
    so no float is involved.
    """
    return str(Decimal(int(cents)).scaleb(-2))


def build_report(result: pd.DataFrame) -> pd.DataFrame:
    """Convert a reconciliation result into report columns.

    Dates become YYYY-MM-DD text, amounts become decimal text and the _cents
    suffix is dropped from column names. Missing values stay missing. The
    input is not modified.
    """
    report = result.assign(date=result["date"].dt.strftime(DATE_FORMAT))
    for column in AMOUNT_COLUMNS:
        report[column] = report[column].map(format_cents, na_action="ignore")
    return report.rename(columns=AMOUNT_COLUMNS)


def export_report(result: pd.DataFrame, path: str | Path) -> None:
    """Write the report as CSV, creating parent directories if needed.

    The CSV is first written to a temporary file in the same directory and
    only then moved over the final path, so an existing report is kept intact
    if writing fails. Missing values are written as empty fields.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(result)

    # Same directory as the final file: os.replace is only atomic within one file system.
    file_descriptor, temp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="") as file:
            report.to_csv(file, index=False, lineterminator="\n")
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise
