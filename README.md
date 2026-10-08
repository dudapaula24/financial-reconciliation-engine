# Financial Reconciliation Engine

**English** | [Português (Brasil)](README.pt-BR.md)

A Python command-line tool that reconciles bank transactions against accounting records, classifies every record by reconciliation status and writes a CSV report.

> All data in this repository is fictional. Company names such as "Alpha Office Supplies" or "Delta Logistics" are invented examples.

## Overview

Reconciliation means checking that every movement in a bank statement has a matching entry in the accounting records, and vice versa. Done by hand, it is repetitive and error-prone, especially when amounts repeat or descriptions are written differently on each side.

This project automates the first pass of that work. It reads two CSV files, validates them, pairs records with simple and explainable rules, and reports what was reconciled, what differs in amount and what still needs manual review.

## Quick Start

```bash
git clone https://github.com/dudapaula24/financial-reconciliation-engine.git
cd financial-reconciliation-engine
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows (PowerShell)
# source .venv/bin/activate       # Linux / macOS
pip install -r requirements.txt

python -m reconciliation --bank data/bank_transactions.csv --accounting data/accounting_records.csv
```

## Features

- **Input validation** with line-level error messages: required columns, empty fields, duplicate IDs, dates and amounts.
- **Exact amounts**: values are stored as integer cents, never as floats.
- **One-to-one exact matching** by date and amount, deterministic when amounts repeat.
- **Amount mismatch detection** by date and normalized description, with a conservative rule for ambiguous cases.
- **Four statuses**: `MATCHED`, `AMOUNT_MISMATCH`, `BANK_ONLY`, `ACCOUNTING_ONLY`.
- **Summary** of items and records per status, printed to the terminal.
- **CSV report** written safely: a previous report is kept intact if writing fails.
- **Command-line interface** with clear exit codes.

## Tech Stack

| Tool | Use |
|---|---|
| Python 3.11+ | Language (`StrEnum` and pandas 3 require 3.11) |
| pandas | Reading CSV files and handling tabular data |
| pytest | Automated tests |
| Python standard library | `argparse`, `logging`, `decimal`, `enum`, `collections`, `tempfile`, `pathlib` |

## How It Works

```
bank CSV ─────────┐
                  ├─► load & validate ─► exact matching ─► amount mismatch ─► result ─┬─► summary (terminal)
accounting CSV ───┘                       (date + amount)    (leftovers only)          └─► CSV report
```

### Reconciliation rules

Rules run in this order. Each step only sees the records left over by the previous one, so a record is never used twice.

1. **Exact match:** same `date` and same `amount`. The description is ignored. Matching is one-to-one: when several records share the same date and amount, the first bank record pairs with the first accounting record, the second with the second, following file order.
2. **Amount mismatch:** among the leftovers, same `date` and same normalized description, but different amounts. Descriptions are normalized by trimming spaces, collapsing repeated spaces and ignoring letter case. A pair is formed only when the date and description appear **exactly once on each side**; ambiguous records are left for manual review.
3. **Leftovers:** records without a pair become `BANK_ONLY` or `ACCOUNTING_ONLY`.

### Statuses

| Status | Meaning | `difference` |
|---|---|---|
| `MATCHED` | Same date and amount on both sides | `0.00` |
| `AMOUNT_MISMATCH` | Same date and description, different amounts | bank amount − accounting amount |
| `BANK_ONLY` | Bank record not reconciled automatically | empty |
| `ACCOUNTING_ONLY` | Accounting record not reconciled automatically | empty |

`BANK_ONLY` and `ACCOUNTING_ONLY` mean the record **could not be reconciled automatically**, not necessarily that the transaction is missing on the other side.

### Design decisions

- **Integer cents instead of floats.** Floats cannot represent many decimal values exactly (`0.29 * 100` is `28.999999999999996`). Amounts are parsed from text with `Decimal` and stored as integers, so comparisons are exact.
- **Queues instead of a plain `merge`.** Merging on date and amount pairs every record with every other record that shares the key, so one accounting record could match two bank records. Each key instead gets a first-in, first-out queue, and a candidate is removed once it is used.
- **Conservative description rule.** Matching by description is a heuristic, so when it is ambiguous the engine prefers leaving records for review over guessing.
- **Nullable integers in the result.** Missing values would turn a regular integer column into floats in pandas; the `Int64` type keeps amounts as integers.
- **Safe report writing.** The report is written to a temporary file in the same folder and then moved over the final file with `os.replace`, so a failure never leaves a half-written report.

## Input Format

Both files use the same format:

```csv
id,date,description,amount
B001,2026-09-01,Alpha Office Supplies,-350.00
```

| Column | Rule |
|---|---|
| `id` | Required, unique within the file |
| `date` | Required, `YYYY-MM-DD` |
| `description` | Required |
| `amount` | Required, dot as decimal separator, at most two decimal places, no currency symbol or thousands separator. Incoming amounts are positive, outgoing amounts negative, using the same convention in both files |

Extra columns are allowed and ignored. Files are read as UTF-8.

## CLI Usage

```bash
python -m reconciliation --bank BANK_CSV --accounting ACCOUNTING_CSV [--output REPORT_CSV]
```

| Argument | Required | Description |
|---|---|---|
| `--bank` | yes | Bank transactions CSV file |
| `--accounting` | yes | Accounting records CSV file |
| `--output` | no | Report file to write (default: `output/reconciliation_result.csv`) |

| Exit code | Meaning |
|---|---|
| `0` | Success |
| `1` | Input file not found, invalid input data, or report could not be written |
| `2` | Invalid command-line arguments |

The summary is printed to standard output; log messages and errors go to standard error.

## Example Output

Running the Quick Start command with the sample files in `data/`:

```text
INFO: Loaded 6 records from data/bank_transactions.csv
INFO: Loaded 5 records from data/accounting_records.csv
Reconciliation summary
         status  items  bank_records  accounting_records
        MATCHED      3             3                   3
AMOUNT_MISMATCH      1             1                   1
      BANK_ONLY      2             2                   0
ACCOUNTING_ONLY      1             0                   1
Total: 7 items, 6 bank records, 5 accounting records
Report written to output/reconciliation_result.csv
```

`items` counts result rows (a pair is one item); `bank_records` and `accounting_records` count input records, so the totals match the size of each input file.

Generated report:

```csv
status,bank_id,accounting_id,date,bank_description,accounting_description,bank_amount,accounting_amount,difference
MATCHED,B001,A001,2026-09-01,Alpha Office Supplies,Alpha Office Supplies,-350.00,-350.00,0.00
MATCHED,B002,A002,2026-09-02,BETA CONSULTING,Beta Consulting,1200.50,1200.50,0.00
MATCHED,B005,A005,2026-09-08,Epsilon Cleaning Services,Epsilon Cleaning Services,-200.00,-200.00,0.00
AMOUNT_MISMATCH,B004,A004,2026-09-05,DELTA LOGISTICS,Delta Logistics,1000.00,990.00,10.00
BANK_ONLY,B003,,2026-09-03,Monthly Bank Fee,,-15.00,,
BANK_ONLY,B006,,2026-09-08,Epsilon Cleaning Services,,-200.00,,
ACCOUNTING_ONLY,,A003,2026-09-04,,Gamma Software License,,-89.90,
```

Notice `B006`: it has the same date, description and amount as `B005`, but the only matching accounting record (`A005`) was already used, so `B006` stays unreconciled.

Invalid input is reported with the file and line. For example, a file `bank_with_errors.csv` whose third line has `abc` as the amount:

```text
ERROR: Invalid input data: bank_with_errors.csv: Invalid amount on line(s): 3
```

## Running Tests

```bash
pytest          # run all tests
pytest -v       # one line per test
```

The tests cover:

- **Loader:** valid files, every validation rule, amount conversion edge cases (`"0.29"`, `"NaN"`, `"10.005"`).
- **Matching:** one-to-one pairing, duplicates, file-order determinism, description normalization, ambiguous cases and the full sample dataset.
- **Result and summary:** column types, every record appearing exactly once, totals without double counting.
- **Report:** decimal formatting (including negative values such as `-0.05`), empty fields, and keeping a previous report when writing fails.
- **CLI:** full runs, exit codes, error messages and running as `python -m reconciliation`.

## Project Structure

```text
financial-reconciliation-engine/
├── data/                    # fictional sample input files
├── reconciliation/
│   ├── __main__.py          # entry point for python -m reconciliation
│   ├── cli.py               # argument parsing, logging, exit codes
│   ├── loader.py            # CSV reading, validation, conversion to cents
│   ├── matcher.py           # exact matching and amount mismatch rules
│   ├── reconciler.py        # statuses and consolidated result
│   ├── summary.py           # counts per status
│   └── report.py            # amount formatting and CSV export
├── tests/                   # pytest test suite
├── pytest.ini
└── requirements.txt
```

## Limitations

- Exact matching requires identical dates and amounts; there is no date or amount tolerance.
- Matching by description is a heuristic. It can produce false positives (two different payments to the same supplier on the same day) and false negatives (accents, punctuation, abbreviations and bank prefixes are not normalized).
- When several records share the same date and description, no amount mismatch pair is formed and they are left for manual review.
- Exact matching runs first and ignores descriptions, so it may use a record that would have been a more plausible amount mismatch.
- There is no threshold for differences: a difference of 0.01 and one of 1,000,000.00 receive the same status.
- Only one-to-one matches are supported; one payment covering several entries is not recognized.
- A single currency and a fixed CSV format are assumed.
- The report is UTF-8 without a byte order mark, so some spreadsheet programs may display accented characters incorrectly.
- All data is processed in memory. Performance has not been measured.

## Future Improvements

- Configurable date and amount tolerances.
- Choosing the closest amount when there are several candidates.
- Configurable description normalization.
- Other report formats.
- Docker image.
- A user interface.

## Author

Developed by [dudapaula24](https://github.com/dudapaula24).
