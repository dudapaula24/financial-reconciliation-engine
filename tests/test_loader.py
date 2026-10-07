import logging

import pandas as pd
import pytest

from reconciliation.loader import InvalidDataError, load_records, to_cents

HEADER = "id,date,description,amount"


def write_csv(tmp_path, *lines):
    path = tmp_path / "records.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# --- Valid files ---


def test_load_records_returns_standardized_dataframe(tmp_path):
    path = write_csv(
        tmp_path,
        HEADER,
        "B001,2026-09-01,Alpha Office Supplies,-350.00",
        "B002,2026-09-02,BETA CONSULTING,1200.50",
    )

    df = load_records(path)

    assert list(df.columns) == ["id", "date", "description", "amount_cents"]
    assert df["id"].tolist() == ["B001", "B002"]
    assert df["date"].tolist() == [pd.Timestamp("2026-09-01"), pd.Timestamp("2026-09-02")]
    assert df["description"].tolist() == ["Alpha Office Supplies", "BETA CONSULTING"]
    assert df["amount_cents"].tolist() == [-35000, 120050]
    assert df["amount_cents"].dtype == "int64"


def test_load_records_strips_surrounding_whitespace(tmp_path):
    path = write_csv(tmp_path, HEADER, "  B001 , 2026-09-01 ,  Alpha Office Supplies  , -350.00 ")

    df = load_records(path)

    assert df.loc[0, "id"] == "B001"
    assert df.loc[0, "description"] == "Alpha Office Supplies"
    assert df.loc[0, "amount_cents"] == -35000


def test_load_records_drops_extra_columns(tmp_path):
    path = write_csv(
        tmp_path,
        "id,date,description,amount,notes",
        "B001,2026-09-01,Alpha Office Supplies,-350.00,paid by transfer",
    )

    df = load_records(path)

    assert list(df.columns) == ["id", "date", "description", "amount_cents"]


def test_load_records_accepts_header_only_file_with_warning(tmp_path, caplog):
    path = write_csv(tmp_path, HEADER)

    with caplog.at_level(logging.WARNING, logger="reconciliation.loader"):
        df = load_records(path)

    assert df.empty
    assert list(df.columns) == ["id", "date", "description", "amount_cents"]
    assert "No records found" in caplog.text


# --- Invalid files ---


def test_load_records_raises_file_not_found_for_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_records(tmp_path / "does_not_exist.csv")


def test_load_records_rejects_completely_empty_file(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")

    with pytest.raises(InvalidDataError, match="File is empty"):
        load_records(path)


def test_load_records_rejects_missing_columns(tmp_path):
    path = write_csv(tmp_path, "id,date,amount", "B001,2026-09-01,-350.00")

    with pytest.raises(InvalidDataError, match="Missing required column\\(s\\): description"):
        load_records(path)


@pytest.mark.parametrize(
    ("row", "expected_message"),
    [
        (",2026-09-01,Alpha Office Supplies,-350.00", "Empty 'id' value on line\\(s\\): 3"),
        ("B002,,Alpha Office Supplies,-350.00", "Empty 'date' value on line\\(s\\): 3"),
        ("B002,2026-09-01,   ,-350.00", "Empty 'description' value on line\\(s\\): 3"),
        ("B002,2026-09-01,Alpha Office Supplies,", "Empty 'amount' value on line\\(s\\): 3"),
    ],
)
def test_load_records_rejects_empty_values(tmp_path, row, expected_message):
    path = write_csv(tmp_path, HEADER, "B001,2026-09-01,Beta Consulting,100.00", row)

    with pytest.raises(InvalidDataError, match=expected_message):
        load_records(path)


def test_load_records_rejects_duplicate_ids(tmp_path):
    path = write_csv(
        tmp_path,
        HEADER,
        "B001,2026-09-01,Alpha Office Supplies,-350.00",
        "B002,2026-09-02,Beta Consulting,1200.50",
        "B001,2026-09-03,Monthly Bank Fee,-15.00",
    )

    with pytest.raises(InvalidDataError, match="Duplicate 'id' value on line\\(s\\): 2, 4"):
        load_records(path)


@pytest.mark.parametrize("invalid_date", ["2026-02-30", "01/09/2026", "not-a-date"])
def test_load_records_rejects_invalid_dates(tmp_path, invalid_date):
    path = write_csv(
        tmp_path,
        HEADER,
        "B001,2026-09-01,Alpha Office Supplies,-350.00",
        f"B002,{invalid_date},Beta Consulting,1200.50",
    )

    with pytest.raises(InvalidDataError, match="Invalid date .* on line\\(s\\): 3"):
        load_records(path)


def test_load_records_reports_every_invalid_amount_line(tmp_path):
    path = write_csv(
        tmp_path,
        HEADER,
        "B001,2026-09-01,Alpha Office Supplies,abc",
        "B002,2026-09-02,Beta Consulting,1200.50",
        "B003,2026-09-03,Monthly Bank Fee,10.005",
    )

    with pytest.raises(InvalidDataError, match="Invalid amount on line\\(s\\): 2, 4"):
        load_records(path)


# --- Amount conversion ---


@pytest.mark.parametrize(
    ("text", "expected_cents"),
    [
        ("-350.00", -35000),
        ("1200.50", 120050),
        ("0.29", 29),
        ("-0.29", -29),
        ("10", 1000),
        ("10.5", 1050),
        ("10.500", 1050),
    ],
)
def test_to_cents_converts_valid_amounts(text, expected_cents):
    assert to_cents(text) == expected_cents


@pytest.mark.parametrize(
    "text",
    ["", "abc", "1,200.50", "R$ 10", "10.005", "NaN", "Infinity"],
)
def test_to_cents_rejects_invalid_amounts(text):
    with pytest.raises(InvalidDataError):
        to_cents(text)
