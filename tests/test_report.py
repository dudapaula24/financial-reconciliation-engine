import pandas as pd
import pytest

from reconciliation import report
from reconciliation.report import build_report, export_report, format_cents

EXPECTED_SAMPLE_REPORT = """\
status,bank_id,accounting_id,date,bank_description,accounting_description,bank_amount,accounting_amount,difference
MATCHED,B001,A001,2026-09-01,Alpha Office Supplies,Alpha Office Supplies,-350.00,-350.00,0.00
MATCHED,B002,A002,2026-09-02,BETA CONSULTING,Beta Consulting,1200.50,1200.50,0.00
MATCHED,B005,A005,2026-09-08,Epsilon Cleaning Services,Epsilon Cleaning Services,-200.00,-200.00,0.00
AMOUNT_MISMATCH,B004,A004,2026-09-05,DELTA LOGISTICS,Delta Logistics,1000.00,990.00,10.00
BANK_ONLY,B003,,2026-09-03,Monthly Bank Fee,,-15.00,,
BANK_ONLY,B006,,2026-09-08,Epsilon Cleaning Services,,-200.00,,
ACCOUNTING_ONLY,,A003,2026-09-04,,Gamma Software License,,-89.90,
"""


# --- Amount formatting ---


@pytest.mark.parametrize(
    ("cents", "expected"),
    [
        (-35000, "-350.00"),
        (120050, "1200.50"),
        (100, "1.00"),
        (5, "0.05"),
        (-5, "-0.05"),
        (-1, "-0.01"),
        (0, "0.00"),
        (123456789012, "1234567890.12"),
    ],
)
def test_format_cents(cents, expected):
    assert format_cents(cents) == expected


# --- Report table ---


def test_build_report_renames_amount_columns_and_formats_values(sample_result):
    table = build_report(sample_result)

    assert list(table.columns) == [
        "status", "bank_id", "accounting_id", "date",
        "bank_description", "accounting_description",
        "bank_amount", "accounting_amount", "difference",
    ]
    first = table.iloc[0]
    assert first["date"] == "2026-09-01"
    assert first["bank_amount"] == "-350.00"
    assert first["difference"] == "0.00"


def test_build_report_keeps_missing_values_missing(sample_result):
    table = build_report(sample_result)

    bank_only = table[table["status"] == "BANK_ONLY"].iloc[0]
    assert pd.isna(bank_only["accounting_id"])
    assert pd.isna(bank_only["accounting_amount"])
    assert pd.isna(bank_only["difference"])


def test_build_report_does_not_modify_result(sample_result):
    result_before = sample_result.copy()

    build_report(sample_result)

    pd.testing.assert_frame_equal(sample_result, result_before)


# --- Export ---


def test_export_report_writes_decimal_amounts_and_empty_missing_fields(tmp_path, sample_result):
    path = tmp_path / "report.csv"

    export_report(sample_result, path)

    assert path.read_text(encoding="utf-8") == EXPECTED_SAMPLE_REPORT


def test_export_report_creates_missing_directories(tmp_path, sample_result):
    path = tmp_path / "nested" / "folder" / "report.csv"

    export_report(sample_result, path)

    assert path.exists()


@pytest.fixture
def previous_report(tmp_path):
    """Create a report directory holding only an existing report file, and return its path."""
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    path = report_dir / "report.csv"
    path.write_text("previous report", encoding="utf-8")
    return path


def files_in(directory):
    return [p.name for p in directory.iterdir()]


def test_export_report_replaces_existing_report(previous_report, sample_result):
    export_report(sample_result, previous_report)

    assert previous_report.read_text(encoding="utf-8") == EXPECTED_SAMPLE_REPORT
    assert files_in(previous_report.parent) == ["report.csv"]


def test_export_report_keeps_previous_report_when_writing_fails(previous_report, sample_result, monkeypatch):

    def failing_to_csv(self, file, **kwargs):
        file.write("partial content")
        raise OSError("disk full")

    monkeypatch.setattr(pd.DataFrame, "to_csv", failing_to_csv)

    with pytest.raises(OSError, match="disk full"):
        export_report(sample_result, previous_report)

    assert previous_report.read_text(encoding="utf-8") == "previous report"
    assert files_in(previous_report.parent) == ["report.csv"]


def test_export_report_keeps_previous_report_when_replace_fails(previous_report, sample_result, monkeypatch):
    # e.g. on Windows, the final file is open in a spreadsheet program.
    def failing_replace(source, destination):
        raise PermissionError("file is locked")

    monkeypatch.setattr(report.os, "replace", failing_replace)

    with pytest.raises(PermissionError):
        export_report(sample_result, previous_report)

    assert previous_report.read_text(encoding="utf-8") == "previous report"
    assert files_in(previous_report.parent) == ["report.csv"]
