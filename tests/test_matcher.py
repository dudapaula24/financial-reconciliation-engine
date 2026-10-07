import pandas as pd
import pytest

from reconciliation.matcher import find_exact_matches

COLUMNS = ["id", "date", "description", "amount_cents"]


def make_records(*rows):
    """Build a DataFrame shaped like the loader output from (id, date, description, amount_cents) tuples."""
    df = pd.DataFrame(list(rows), columns=COLUMNS)
    df["date"] = pd.to_datetime(df["date"])
    df["amount_cents"] = df["amount_cents"].astype("int64")
    return df


def pairs(matches):
    return list(zip(matches["bank_id"], matches["accounting_id"]))


def ids(records):
    return records["id"].tolist()


# --- Basic rule: same date + same amount ---


def test_pairs_records_with_same_date_and_amount():
    bank = make_records(("B001", "2026-09-01", "Alpha Office Supplies", -35000))
    accounting = make_records(("A001", "2026-09-01", "Alpha Office Supplies", -35000))

    matches, unmatched_bank, unmatched_accounting = find_exact_matches(bank, accounting)

    assert list(matches.columns) == ["bank_id", "accounting_id"]
    assert pairs(matches) == [("B001", "A001")]
    assert unmatched_bank.empty
    assert unmatched_accounting.empty


def test_ignores_description():
    bank = make_records(("B002", "2026-09-02", "BETA CONSULTING", 120050))
    accounting = make_records(("A002", "2026-09-02", "Beta Consulting", 120050))

    matches, _, _ = find_exact_matches(bank, accounting)

    assert pairs(matches) == [("B002", "A002")]


def test_does_not_pair_same_amount_on_different_dates():
    bank = make_records(("B001", "2026-09-01", "Alpha Office Supplies", -35000))
    accounting = make_records(("A001", "2026-09-02", "Alpha Office Supplies", -35000))

    matches, unmatched_bank, unmatched_accounting = find_exact_matches(bank, accounting)

    assert matches.empty
    assert ids(unmatched_bank) == ["B001"]
    assert ids(unmatched_accounting) == ["A001"]


@pytest.mark.parametrize("accounting_amount", [-34999, 35000])
def test_does_not_pair_different_amounts_on_same_date(accounting_amount):
    bank = make_records(("B001", "2026-09-01", "Alpha Office Supplies", -35000))
    accounting = make_records(("A001", "2026-09-01", "Alpha Office Supplies", accounting_amount))

    matches, unmatched_bank, unmatched_accounting = find_exact_matches(bank, accounting)

    assert matches.empty
    assert ids(unmatched_bank) == ["B001"]
    assert ids(unmatched_accounting) == ["A001"]


# --- One-to-one and determinism ---


def test_accounting_record_is_not_reused_for_duplicate_bank_records():
    bank = make_records(
        ("B005", "2026-09-08", "Epsilon Cleaning Services", -20000),
        ("B006", "2026-09-08", "Epsilon Cleaning Services", -20000),
    )
    accounting = make_records(("A005", "2026-09-08", "Epsilon Cleaning Services", -20000))

    matches, unmatched_bank, unmatched_accounting = find_exact_matches(bank, accounting)

    assert pairs(matches) == [("B005", "A005")]
    assert ids(unmatched_bank) == ["B006"]
    assert unmatched_accounting.empty


def test_bank_record_is_not_reused_for_duplicate_accounting_records():
    bank = make_records(("B005", "2026-09-08", "Epsilon Cleaning Services", -20000))
    accounting = make_records(
        ("A005", "2026-09-08", "Epsilon Cleaning Services", -20000),
        ("A006", "2026-09-08", "Epsilon Cleaning Services", -20000),
    )

    matches, unmatched_bank, unmatched_accounting = find_exact_matches(bank, accounting)

    assert pairs(matches) == [("B005", "A005")]
    assert unmatched_bank.empty
    assert ids(unmatched_accounting) == ["A006"]


def test_two_bank_records_against_two_accounting_records_with_same_key():
    bank = make_records(
        ("B005", "2026-09-08", "Epsilon Cleaning Services", -20000),
        ("B006", "2026-09-08", "Epsilon Cleaning Services", -20000),
    )
    accounting = make_records(
        ("A005", "2026-09-08", "Epsilon Cleaning Services", -20000),
        ("A006", "2026-09-08", "Epsilon Cleaning Services", -20000),
    )

    matches, unmatched_bank, unmatched_accounting = find_exact_matches(bank, accounting)

    assert pairs(matches) == [("B005", "A005"), ("B006", "A006")]
    assert unmatched_bank.empty
    assert unmatched_accounting.empty


def test_pairs_follow_row_order_not_id():
    bank = make_records(
        ("B006", "2026-09-08", "Epsilon Cleaning Services", -20000),
        ("B005", "2026-09-08", "Epsilon Cleaning Services", -20000),
    )
    accounting = make_records(("A005", "2026-09-08", "Epsilon Cleaning Services", -20000))

    matches, unmatched_bank, _ = find_exact_matches(bank, accounting)

    assert pairs(matches) == [("B006", "A005")]
    assert ids(unmatched_bank) == ["B005"]


# --- Edge cases ---


@pytest.mark.parametrize(
    ("bank_rows", "accounting_rows"),
    [
        ([], [("A001", "2026-09-01", "Alpha Office Supplies", -35000)]),
        ([("B001", "2026-09-01", "Alpha Office Supplies", -35000)], []),
        ([], []),
    ],
    ids=["empty_bank", "empty_accounting", "both_empty"],
)
def test_handles_empty_inputs(bank_rows, accounting_rows):
    bank = make_records(*bank_rows)
    accounting = make_records(*accounting_rows)

    matches, unmatched_bank, unmatched_accounting = find_exact_matches(bank, accounting)

    assert matches.empty
    assert list(matches.columns) == ["bank_id", "accounting_id"]
    assert ids(unmatched_bank) == ids(bank)
    assert ids(unmatched_accounting) == ids(accounting)


def test_does_not_modify_inputs():
    bank = make_records(("B001", "2026-09-01", "Alpha Office Supplies", -35000))
    accounting = make_records(("A001", "2026-09-01", "Alpha Office Supplies", -35000))
    bank_before = bank.copy()
    accounting_before = accounting.copy()

    find_exact_matches(bank, accounting)

    pd.testing.assert_frame_equal(bank, bank_before)
    pd.testing.assert_frame_equal(accounting, accounting_before)


# --- Sample dataset ---


def test_sample_dataset():
    bank = make_records(
        ("B001", "2026-09-01", "Alpha Office Supplies", -35000),
        ("B002", "2026-09-02", "BETA CONSULTING", 120050),
        ("B003", "2026-09-03", "Monthly Bank Fee", -1500),
        ("B004", "2026-09-05", "DELTA LOGISTICS", 100000),
        ("B005", "2026-09-08", "Epsilon Cleaning Services", -20000),
        ("B006", "2026-09-08", "Epsilon Cleaning Services", -20000),
    )
    accounting = make_records(
        ("A001", "2026-09-01", "Alpha Office Supplies", -35000),
        ("A002", "2026-09-02", "Beta Consulting", 120050),
        ("A003", "2026-09-04", "Gamma Software License", -8990),
        ("A004", "2026-09-05", "Delta Logistics", 99000),
        ("A005", "2026-09-08", "Epsilon Cleaning Services", -20000),
    )

    matches, unmatched_bank, unmatched_accounting = find_exact_matches(bank, accounting)

    assert pairs(matches) == [("B001", "A001"), ("B002", "A002"), ("B005", "A005")]
    assert ids(unmatched_bank) == ["B003", "B004", "B006"]
    assert ids(unmatched_accounting) == ["A003", "A004"]
    assert list(unmatched_bank.columns) == COLUMNS
