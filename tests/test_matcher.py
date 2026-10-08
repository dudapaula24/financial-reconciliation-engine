import pandas as pd
import pytest

from reconciliation.matcher import find_amount_mismatches, find_exact_matches, normalize_description

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


# --- Description normalization ---


@pytest.mark.parametrize(
    "text",
    [
        "delta logistics",
        "DELTA LOGISTICS",
        "Delta Logistics",
        "  Delta Logistics  ",
        "Delta   Logistics",
        "Delta\tLogistics",
    ],
)
def test_normalize_description_ignores_case_and_extra_whitespace(text):
    assert normalize_description(text) == "delta logistics"


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("Café Central", "Cafe Central"),
        ("Delta-Logistics", "Delta Logistics"),
        ("DELTA LOG", "Delta Logistics"),
    ],
    ids=["accents", "punctuation", "abbreviation"],
)
def test_normalize_description_keeps_accents_punctuation_and_abbreviations(first, second):
    # Documents a known limitation: these are not treated as the same description.
    assert normalize_description(first) != normalize_description(second)


# --- Amount mismatches ---


def mismatch_rows(mismatches):
    return list(
        zip(mismatches["bank_id"], mismatches["accounting_id"], mismatches["difference_cents"])
    )


def test_amount_mismatch_pairs_same_date_and_normalized_description():
    bank = make_records(("B004", "2026-09-05", "DELTA LOGISTICS", 100000))
    accounting = make_records(("A004", "2026-09-05", "Delta Logistics", 99000))

    mismatches, remaining_bank, remaining_accounting = find_amount_mismatches(bank, accounting)

    assert list(mismatches.columns) == ["bank_id", "accounting_id", "difference_cents"]
    assert mismatch_rows(mismatches) == [("B004", "A004", 1000)]
    assert mismatches["difference_cents"].dtype == "int64"
    assert remaining_bank.empty
    assert remaining_accounting.empty


def test_amount_mismatch_difference_is_negative_when_bank_amount_is_lower():
    bank = make_records(("B004", "2026-09-05", "Delta Logistics", 99000))
    accounting = make_records(("A004", "2026-09-05", "Delta Logistics", 100000))

    mismatches, _, _ = find_amount_mismatches(bank, accounting)

    assert mismatch_rows(mismatches) == [("B004", "A004", -1000)]


@pytest.mark.parametrize(
    "accounting_row",
    [
        ("A004", "2026-09-06", "Delta Logistics", 99000),
        ("A004", "2026-09-05", "Zeta Rentals", 99000),
    ],
    ids=["different_date", "different_description"],
)
def test_amount_mismatch_requires_same_date_and_description(accounting_row):
    bank = make_records(("B004", "2026-09-05", "Delta Logistics", 100000))
    accounting = make_records(accounting_row)

    mismatches, remaining_bank, remaining_accounting = find_amount_mismatches(bank, accounting)

    assert mismatches.empty
    assert ids(remaining_bank) == ["B004"]
    assert ids(remaining_accounting) == ["A004"]


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
                ("B2", "2026-09-05", "DELTA LOGISTICS", 50000),
            ],
            [
                ("A1", "2026-09-05", "Delta Logistics", 99000),
                ("A2", "2026-09-05", "delta logistics", 51000),
            ],
        ),
    ],
    ids=["2_bank_vs_1_accounting", "1_bank_vs_2_accounting", "2_bank_vs_2_accounting"],
)
def test_amount_mismatch_skips_ambiguous_keys(bank_rows, accounting_rows):
    bank = make_records(*bank_rows)
    accounting = make_records(*accounting_rows)

    mismatches, remaining_bank, remaining_accounting = find_amount_mismatches(bank, accounting)

    assert mismatches.empty
    assert ids(remaining_bank) == ids(bank)
    assert ids(remaining_accounting) == ids(accounting)


def test_amount_mismatch_ambiguous_key_does_not_block_other_keys():
    bank = make_records(
        ("B1", "2026-09-05", "Delta Logistics", 100000),
        ("B2", "2026-09-05", "Delta Logistics", 50000),
        ("B3", "2026-09-06", "Zeta Rentals", 30000),
    )
    accounting = make_records(
        ("A1", "2026-09-05", "Delta Logistics", 99000),
        ("A2", "2026-09-06", "Zeta Rentals", 31000),
    )

    mismatches, remaining_bank, remaining_accounting = find_amount_mismatches(bank, accounting)

    assert mismatch_rows(mismatches) == [("B3", "A2", -1000)]
    assert ids(remaining_bank) == ["B1", "B2"]
    assert ids(remaining_accounting) == ["A1"]


def test_amount_mismatch_rejects_equal_amounts():
    # Equal amounts can only reach this function if find_exact_matches was skipped.
    bank = make_records(("B001", "2026-09-01", "Alpha Office Supplies", -35000))
    accounting = make_records(("A001", "2026-09-01", "Alpha Office Supplies", -35000))

    with pytest.raises(ValueError, match="B001/A001"):
        find_amount_mismatches(bank, accounting)


@pytest.mark.parametrize(
    ("bank_rows", "accounting_rows"),
    [
        ([], [("A004", "2026-09-05", "Delta Logistics", 99000)]),
        ([("B004", "2026-09-05", "Delta Logistics", 100000)], []),
        ([], []),
    ],
    ids=["empty_bank", "empty_accounting", "both_empty"],
)
def test_amount_mismatch_handles_empty_inputs(bank_rows, accounting_rows):
    bank = make_records(*bank_rows)
    accounting = make_records(*accounting_rows)

    mismatches, remaining_bank, remaining_accounting = find_amount_mismatches(bank, accounting)

    assert mismatches.empty
    assert list(mismatches.columns) == ["bank_id", "accounting_id", "difference_cents"]
    assert ids(remaining_bank) == ids(bank)
    assert ids(remaining_accounting) == ids(accounting)


def test_amount_mismatch_does_not_modify_inputs():
    bank = make_records(("B004", "2026-09-05", "DELTA LOGISTICS", 100000))
    accounting = make_records(("A004", "2026-09-05", "Delta Logistics", 99000))
    bank_before = bank.copy()
    accounting_before = accounting.copy()

    find_amount_mismatches(bank, accounting)

    pd.testing.assert_frame_equal(bank, bank_before)
    pd.testing.assert_frame_equal(accounting, accounting_before)


# --- Pipeline: exact matches first, then amount mismatches on the leftovers ---


def test_pipeline_does_not_reuse_exact_matched_records():
    bank = make_records(
        ("B005", "2026-09-08", "Epsilon Cleaning Services", -20000),
        ("B006", "2026-09-08", "Epsilon Cleaning Services", -20000),
    )
    accounting = make_records(("A005", "2026-09-08", "Epsilon Cleaning Services", -20000))

    matches, unmatched_bank, unmatched_accounting = find_exact_matches(bank, accounting)
    mismatches, remaining_bank, remaining_accounting = find_amount_mismatches(
        unmatched_bank, unmatched_accounting
    )

    assert pairs(matches) == [("B005", "A005")]
    assert mismatches.empty
    assert ids(remaining_bank) == ["B006"]
    assert remaining_accounting.empty


def test_pipeline_sample_dataset():
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
    mismatches, remaining_bank, remaining_accounting = find_amount_mismatches(
        unmatched_bank, unmatched_accounting
    )

    assert pairs(matches) == [("B001", "A001"), ("B002", "A002"), ("B005", "A005")]
    assert mismatch_rows(mismatches) == [("B004", "A004", 1000)]
    assert ids(remaining_bank) == ["B003", "B006"]
    assert ids(remaining_accounting) == ["A003"]
