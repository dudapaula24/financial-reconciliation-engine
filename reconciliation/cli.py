"""Command-line interface for the reconciliation engine."""

import argparse
import logging
from pathlib import Path

import pandas as pd

from reconciliation.loader import InvalidDataError, load_records
from reconciliation.reconciler import reconcile
from reconciliation.report import export_report
from reconciliation.summary import summarize

DEFAULT_OUTPUT = Path("output") / "reconciliation_result.csv"

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """Run a reconciliation from the command line and return the exit code.

    Exit codes: 0 on success, 1 when an input file cannot be read or is
    invalid, or the report cannot be written. Invalid arguments make argparse
    exit with code 2.
    """
    args = _parse_args(argv)
    # Diagnostics and errors go to stderr through logging; the summary goes to stdout.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    try:
        bank = _load(args.bank)
        accounting = _load(args.accounting)
    except FileNotFoundError as exc:
        logger.error("Input file not found: %s", exc)
        return 1
    except InvalidDataError as exc:
        logger.error("Invalid input data: %s", exc)
        return 1

    result = reconcile(bank, accounting)

    try:
        export_report(result, args.output)
    except OSError as exc:
        logger.error("Could not write report to %s: %s", args.output, exc)
        return 1

    print(_format_summary(summarize(result)))
    print(f"Report written to {args.output}")
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m reconciliation",
        description="Reconcile bank transactions against accounting records.",
    )
    parser.add_argument("--bank", required=True, type=Path, help="bank transactions CSV file")
    parser.add_argument(
        "--accounting", required=True, type=Path, help="accounting records CSV file"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"report CSV file to write (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args(argv)


def _load(path: Path) -> pd.DataFrame:
    """Load a file, adding its path to validation errors so the user knows which file failed."""
    try:
        return load_records(path)
    except InvalidDataError as exc:
        raise InvalidDataError(f"{path}: {exc}") from exc


def _format_summary(summary: pd.DataFrame) -> str:
    totals = (
        f"Total: {summary['items'].sum()} items, "
        f"{summary['bank_records'].sum()} bank records, "
        f"{summary['accounting_records'].sum()} accounting records"
    )
    return "\n".join(["Reconciliation summary", summary.to_string(index=False), totals])
