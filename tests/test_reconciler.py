from collections import Counter

import pandas as pd
import pytest

from reconciliation.reconciler import RESULT_COLUMNS, Status, reconcile

COLUMNS = ["id", "date", "description", "amount_cents"]

SAMPLE_BANK = [
    ("B001", "2026-09-01", "Alpha Office Supplies", -35000),
    ("B002", "2026-09-02", "BETA CONSULTING", 120050),
    ("B003", "2026-09-03", "Monthly Bank Fee", -1500),
    ("B004", "2026-09-05", "DELTA LOGISTICS", 100000),
    ("B005", "2026-09-08", "Epsilon Cleaning Services", -20000),
    ("B006", "2026-09-08", "Epsilon Cleaning Services", -20000),
]
SAMPLE_ACCOUNTING = [
    ("A001", "2026-09-01", "Alpha Office Supplies", -35000),
    ("A002", "2026-09-02", "Beta Consulting", 120050),
    ("A003", "2026-09-04", "Gamma Software License", -8990),
    ("A004", "2026-09-05", "Delta Logistics", 99000),
    ("A005", "2026-09-08", "Epsilon Cleaning Services", -20000),
]


def make_records(*rows):
    """Build a DataFrame shaped like the loader output from (id, date, description, amount_cents) tuples."""
    df = pd.DataFrame(list(rows), columns=COLUMNS)
    df["date"] = pd.to_datetime(df["date"])
    df["amount_cents"] = df["amount_cents"].astype("int64")
    return df


def result_rows(result):
    """Return the result as plain tuples, with dates as text and missing values as None."""
    table = result.assign(date=result["date"].dt.strftime("%Y-%m-%d"))
    return [
        tuple(None if pd.isna(value) else value for value in row)
        for row in table.itertuples(index=False)
    ]


def statuses_by_id(result):
    """Map every bank and accounting id in the result to its status."""
    mapping = {}
    for row in result.itertuples(index=False):
        for record_id in (row.bank_id, row.accounting_id):
            if not pd.isna(record_id):
                mapping[record_id] = row.status
    return mapping


# --- Full dataset ---


def test_reconcile_sample_dataset():
    result = reconcile(make_records(*SAMPLE_BANK), make_records(*SAMPLE_ACCOUNTING))

    assert list(result.columns) == RESULT_COLUMNS
    assert result_rows(result) == [
        ("MATCHED", "B001", "A001", "2026-09-01",
         "Alpha Office Supplies", "Alpha Office Supplies", -35000, -35000, 0),
        ("MATCHED", "B002", "A002", "2026-09-02",
         "BETA CONSULTING", "Beta Consulting", 120050, 120050, 0),
        ("MATCHED", "B005", "A005", "2026-09-08",
         "Epsilon Cleaning Services", "Epsilon Cleaning Services", -20000, -20000, 0),
        ("AMOUNT_MISMATCH", "B004", "A004", "2026-09-05",
         "DELTA LOGISTICS", "Delta Logistics", 100000, 99000, 1000),
        ("BANK_ONLY", "B003", None, "2026-09-03",
         "Monthly Bank Fee", None, -1500, None, None),
        ("BANK_ONLY", "B006", None, "2026-09-08",
         "Epsilon Cleaning Services", None, -20000, None, None),
        ("ACCOUNTING_ONLY", None, "A003", "2026-09-04",
         None, "Gamma Software License", None, -8990, None),
    ]


# --- Types ---


def test_reconcile_keeps_amounts_as_nullable_integers():
    result = reconcile(make_records(*SAMPLE_BANK), make_records(*SAMPLE_ACCOUNTING))

    for column in ["bank_amount_cents", "accounting_amount_cents", "difference_cents"]:
        assert result[column].dtype == "Int64", column


def test_reconcile_keeps_missing_fields_missing_instead_of_nan_text():
    result = reconcile(make_records(*SAMPLE_BANK), make_records(*SAMPLE_ACCOUNTING))

    text_columns = ["status", "bank_id", "accounting_id", "bank_description", "accounting_description"]
    for column in text_columns:
        assert result[column].dtype == "string", column

    bank_only = result[result["status"] == "BANK_ONLY"]
    for column in ["accounting_id", "accounting_description", "accounting_amount_cents", "difference_cents"]:
        assert bank_only[column].isna().all(), column

    accounting_only = result[result["status"] == "ACCOUNTING_ONLY"]
    for column in ["bank_id", "bank_description", "bank_amount_cents", "difference_cents"]:
        assert accounting_only[column].isna().all(), column

    assert not result[text_columns].isin(["nan", "NaN", "None", "<NA>", ""]).any().any()


def test_reconcile_status_values_are_status_members():
    result = reconcile(make_records(*SAMPLE_BANK), make_records(*SAMPLE_ACCOUNTING))

    assert set(result["status"]) <= set(Status)


# --- Edge cases ---


@pytest.mark.parametrize(
    ("bank_rows", "accounting_rows", "expected_statuses"),
    [
        ([], [], []),
        ([], [("A001", "2026-09-01", "Alpha Office Supplies", -35000)], ["ACCOUNTING_ONLY"]),
        ([("B001", "2026-09-01", "Alpha Office Supplies", -35000)], [], ["BANK_ONLY"]),
    ],
    ids=["both_empty", "empty_bank", "empty_accounting"],
)
def test_reconcile_handles_empty_inputs(bank_rows, accounting_rows, expected_statuses):
    result = reconcile(make_records(*bank_rows), make_records(*accounting_rows))

    assert list(result.columns) == RESULT_COLUMNS
    assert result["status"].tolist() == expected_statuses
    assert result["bank_amount_cents"].dtype == "Int64"
    assert result["difference_cents"].dtype == "Int64"


@pytest.mark.parametrize(
    ("bank_rows", "accounting_rows"),
    [
        (
            [
                ("B1", "2026-09-05", "Delta Logistics", 100000),
                ("B2", "2026-09-05", "Delta Logistics", 50000),
            ],
            [("A1", "2026-09-05", "Delta Logistics", 99000)],
        ),
        (
            [("B1", "2026-09-05", "Delta Logistics", 100000)],
            [
                ("A1", "2026-09-05", "Delta Logistics", 99000),
                ("A2", "2026-09-05", "Delta Logistics", 51000),
            ],
        ),
        (
            [
                ("B1", "2026-09-05", "Delta Logistics", 100000),
                ("B2", "2026-09-05", "Delta Logistics", 50000),
            ],
            [
                ("A1", "2026-09-05", "Delta Logistics", 99000),
                ("A2", "2026-09-05", "Delta Logistics", 51000),
            ],
        ),
    ],
    ids=["2_bank_vs_1_accounting", "1_bank_vs_2_accounting", "2_bank_vs_2_accounting"],
)
def test_reconcile_leaves_ambiguous_records_unreconciled(bank_rows, accounting_rows):
    bank = make_records(*bank_rows)
    accounting = make_records(*accounting_rows)

    result = reconcile(bank, accounting)

    statuses = statuses_by_id(result)
    assert all(statuses[record_id] == "BANK_ONLY" for record_id in bank["id"])
    assert all(statuses[record_id] == "ACCOUNTING_ONLY" for record_id in accounting["id"])
    assert result["difference_cents"].isna().all()


# --- Determinism ---


def test_reconcile_groups_by_status_and_keeps_input_order_within_groups():
    bank = make_records(
        ("B3", "2026-09-03", "Monthly Bank Fee", -1500),
        ("B2", "2026-09-02", "Beta Consulting", 120050),
        ("B9", "2026-09-09", "Theta Insurance", -5000),
        ("B1", "2026-09-01", "Alpha Office Supplies", -35000),
    )
    accounting = make_records(
        ("A1", "2026-09-01", "Alpha Office Supplies", -35000),
        ("A2", "2026-09-02", "Beta Consulting", 120050),
    )

    result = reconcile(bank, accounting)

    assert result["status"].tolist() == ["MATCHED", "MATCHED", "BANK_ONLY", "BANK_ONLY"]
    assert result["bank_id"].tolist() == ["B2", "B1", "B3", "B9"]


def test_reconcile_is_deterministic():
    bank = make_records(*SAMPLE_BANK)
    accounting = make_records(*SAMPLE_ACCOUNTING)

    pd.testing.assert_frame_equal(reconcile(bank, accounting), reconcile(bank, accounting))


# --- Control totals ---


@pytest.mark.parametrize(
    ("bank_rows", "accounting_rows"),
    [
        (SAMPLE_BANK, SAMPLE_ACCOUNTING),
        (
            [
                ("B1", "2026-09-05", "Delta Logistics", 100000),
                ("B2", "2026-09-05", "Delta Logistics", 50000),
                ("B3", "2026-09-05", "Delta Logistics", 100000),
            ],
            [
                ("A1", "2026-09-05", "Delta Logistics", 100000),
                ("A2", "2026-09-05", "Delta Logistics", 51000),
            ],
        ),
        ([], []),
    ],
    ids=["sample_dataset", "duplicates_and_ambiguity", "empty"],
)
def test_reconcile_includes_every_record_exactly_once(bank_rows, accounting_rows):
    bank = make_records(*bank_rows)
    accounting = make_records(*accounting_rows)

    result = reconcile(bank, accounting)

    assert Counter(result["bank_id"].dropna()) == Counter(bank["id"])
    assert Counter(result["accounting_id"].dropna()) == Counter(accounting["id"])


def test_reconcile_does_not_modify_inputs():
    bank = make_records(*SAMPLE_BANK)
    accounting = make_records(*SAMPLE_ACCOUNTING)
    bank_before = bank.copy()
    accounting_before = accounting.copy()

    reconcile(bank, accounting)

    pd.testing.assert_frame_equal(bank, bank_before)
    pd.testing.assert_frame_equal(accounting, accounting_before)
