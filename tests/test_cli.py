import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from reconciliation import cli
from reconciliation.cli import main

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_main(bank, accounting, output):
    return main(["--bank", str(bank), "--accounting", str(accounting), "--output", str(output)])


# --- Successful run ---


def test_main_writes_report_and_prints_summary(tmp_path, sample_files, capsys):
    bank_path, accounting_path = sample_files
    output = tmp_path / "out" / "report.csv"

    exit_code = run_main(bank_path, accounting_path, output)

    assert exit_code == 0
    report = pd.read_csv(output, dtype=str, keep_default_na=False)
    assert report["status"].tolist() == [
        "MATCHED", "MATCHED", "MATCHED", "AMOUNT_MISMATCH",
        "BANK_ONLY", "BANK_ONLY", "ACCOUNTING_ONLY",
    ]
    stdout = capsys.readouterr().out
    assert "AMOUNT_MISMATCH" in stdout
    assert "Total: 7 items, 6 bank records, 5 accounting records" in stdout
    assert f"Report written to {output}" in stdout


def test_main_uses_default_output_path(tmp_path, sample_files, monkeypatch):
    bank_path, accounting_path = sample_files
    monkeypatch.chdir(tmp_path)

    exit_code = main(["--bank", str(bank_path), "--accounting", str(accounting_path)])

    assert exit_code == 0
    assert (tmp_path / "output" / "reconciliation_result.csv").exists()


# --- Invalid arguments ---


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--bank", "bank.csv"],
        ["--accounting", "accounting.csv"],
        ["--bank", "bank.csv", "--accounting", "accounting.csv", "--unknown"],
    ],
    ids=["no_arguments", "missing_accounting", "missing_bank", "unknown_argument"],
)
def test_main_rejects_invalid_arguments_with_exit_code_2(argv, capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(argv)

    assert exc_info.value.code == 2
    assert "usage:" in capsys.readouterr().err


# --- Input and output errors ---


def test_main_returns_1_for_missing_input_file(tmp_path, sample_files, caplog):
    _, accounting_path = sample_files
    output = tmp_path / "report.csv"

    exit_code = run_main(tmp_path / "missing.csv", accounting_path, output)

    assert exit_code == 1
    assert "Input file not found" in caplog.text
    assert "missing.csv" in caplog.text
    assert not output.exists()


def test_main_returns_1_for_invalid_data_and_names_the_file(tmp_path, sample_files, caplog):
    _, accounting_path = sample_files
    invalid_bank = tmp_path / "invalid_bank.csv"
    invalid_bank.write_text("id,date,description,amount\nB001,2026-09-01,Alpha,abc\n", encoding="utf-8")
    output = tmp_path / "report.csv"

    exit_code = run_main(invalid_bank, accounting_path, output)

    assert exit_code == 1
    assert "Invalid input data" in caplog.text
    assert "invalid_bank.csv" in caplog.text
    assert "Invalid amount on line(s): 2" in caplog.text
    assert not output.exists()


def test_main_keeps_previous_report_when_input_is_invalid(tmp_path, sample_files):
    _, accounting_path = sample_files
    invalid_bank = tmp_path / "invalid_bank.csv"
    invalid_bank.write_text("id,date,amount\nB001,2026-09-01,-350.00\n", encoding="utf-8")
    output = tmp_path / "report.csv"
    output.write_text("previous report", encoding="utf-8")

    exit_code = run_main(invalid_bank, accounting_path, output)

    assert exit_code == 1
    assert output.read_text(encoding="utf-8") == "previous report"


def test_main_returns_1_when_report_cannot_be_written(tmp_path, sample_files, monkeypatch, caplog, capsys):
    bank_path, accounting_path = sample_files

    def failing_export(result, path):
        raise PermissionError("file is locked")

    monkeypatch.setattr(cli, "export_report", failing_export)

    exit_code = run_main(bank_path, accounting_path, tmp_path / "report.csv")

    assert exit_code == 1
    assert "Could not write report" in caplog.text
    assert capsys.readouterr().out == ""


# --- Running as a module ---


def run_module(*args):
    return subprocess.run(
        [sys.executable, "-m", "reconciliation", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )


def test_module_entry_point_prints_summary_to_stdout(tmp_path, sample_files):
    bank_path, accounting_path = sample_files

    completed = run_module(
        "--bank", str(bank_path),
        "--accounting", str(accounting_path),
        "--output", str(tmp_path / "report.csv"),
    )

    assert completed.returncode == 0
    assert "Reconciliation summary" in completed.stdout
    assert "ERROR" not in completed.stderr


def test_module_entry_point_prints_errors_to_stderr(tmp_path, sample_files):
    _, accounting_path = sample_files

    completed = run_module(
        "--bank", str(tmp_path / "missing.csv"),
        "--accounting", str(accounting_path),
        "--output", str(tmp_path / "report.csv"),
    )

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert "ERROR: Input file not found" in completed.stderr
