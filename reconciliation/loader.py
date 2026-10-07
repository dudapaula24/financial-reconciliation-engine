"""Load transaction CSV files into a validated, standardized DataFrame."""

import logging
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ["id", "date", "description", "amount"]
DATE_FORMAT = "%Y-%m-%d"

# Line 1 of the file is the header, so DataFrame index 0 is line 2.
FIRST_DATA_LINE = 2


class InvalidDataError(Exception):
    """Raised when the content of an input file does not follow the expected format."""


def load_records(path: str | Path) -> pd.DataFrame:
    """Load a CSV file and return it validated and standardized.

    The returned DataFrame has the columns id, date, description and
    amount_cents, in the same row order as the file. Extra columns are dropped.

    Raises FileNotFoundError if the file does not exist and InvalidDataError
    if its content is invalid.
    """
    # Everything is read as text so pandas never guesses types (e.g. floats for amounts).
    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError as exc:
        raise InvalidDataError(f"File is empty: {path}") from exc

    _check_columns(df)

    df = df[REQUIRED_COLUMNS].copy()
    for column in REQUIRED_COLUMNS:
        df[column] = df[column].str.strip()

    _check_empty_values(df)
    _check_unique_ids(df)
    df["date"] = _parse_dates(df)
    df["amount_cents"] = _parse_amounts(df)
    df = df.drop(columns="amount")

    if df.empty:
        logger.warning("No records found in %s", path)
    else:
        logger.info("Loaded %d records from %s", len(df), path)

    return df


def to_cents(text: str) -> int:
    """Convert a decimal amount such as "-350.00" into integer cents (-35000).

    Raises InvalidDataError if the text is not a finite number or cannot be
    represented as a whole number of cents (e.g. "10.005").
    """
    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise InvalidDataError(f"Invalid amount: {text!r}") from exc

    if not amount.is_finite():
        raise InvalidDataError(f"Invalid amount: {text!r}")

    cents = amount * 100
    if cents != cents.to_integral_value():
        raise InvalidDataError(f"Amount has more than 2 decimal places: {text!r}")

    return int(cents)


def _check_columns(df: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise InvalidDataError(f"Missing required column(s): {', '.join(missing)}")


def _check_empty_values(df: pd.DataFrame) -> None:
    for column in REQUIRED_COLUMNS:
        empty = df[column] == ""
        if empty.any():
            raise InvalidDataError(
                f"Empty '{column}' value on line(s): {_format_lines(df.index[empty])}"
            )


def _check_unique_ids(df: pd.DataFrame) -> None:
    """Raise InvalidDataError if any id appears more than once.

    Expected message format, listing every line involved:
        Duplicate 'id' value on line(s): 2, 4
    """
    duplicated = df["id"].duplicated(keep=False)
    if duplicated.any():
        raise InvalidDataError(
            f"Duplicate 'id' value on line(s): {_format_lines(df.index[duplicated])}"
        )


def _parse_dates(df: pd.DataFrame) -> pd.Series:
    # errors="coerce" turns every invalid date into NaT instead of stopping at the first one.
    dates = pd.to_datetime(df["date"], format=DATE_FORMAT, errors="coerce")
    invalid = dates.isna()
    if invalid.any():
        raise InvalidDataError(
            f"Invalid date (expected YYYY-MM-DD) on line(s): {_format_lines(df.index[invalid])}"
        )
    return dates


def _parse_amounts(df: pd.DataFrame) -> pd.Series:
    amounts = []
    invalid_indexes = []
    for index, text in df["amount"].items():
        try:
            amounts.append(to_cents(text))
        except InvalidDataError:
            invalid_indexes.append(index)

    if invalid_indexes:
        raise InvalidDataError(f"Invalid amount on line(s): {_format_lines(invalid_indexes)}")

    return pd.Series(amounts, index=df.index, dtype="int64")


def _format_lines(indexes) -> str:
    """Convert DataFrame indexes into the matching CSV line numbers, e.g. "2, 4"."""
    return ", ".join(str(index + FIRST_DATA_LINE) for index in indexes)
