import pandas as pd
import pytest

from reconciliation.reconciler import RESULT_COLUMNS
from reconciliation.summary import SUMMARY_COLUMNS, summarize

SAMPLE_RESULT = [
    ("MATCHED", "B001", "A001"),
    ("MATCHED", "B002", "A002"),
    ("MATCHED", "B005", "A005"),
    ("AMOUNT_MISMATCH", "B004", "A004"),
    ("BANK_ONLY", "B003", None),
    ("BANK_ONLY", "B006", None),
    ("ACCOUNTING_ONLY", None, "A003"),
]


def make_result(*rows):
    """Build a reconciliation result from (status, bank_id, accounting_id) tuples.

    The other result columns are left empty because summarize does not use them.
    """
    df = pd.DataFrame(list(rows), columns=["status", "bank_id", "accounting_id"])
    return df.reindex(columns=RESULT_COLUMNS)


def summary_rows(summary):
    return [tuple(row) for row in summary.itertuples(index=False)]


def test_summarize_sample_dataset():
    summary = summarize(make_result(*SAMPLE_RESULT))

    assert list(summary.columns) == SUMMARY_COLUMNS
    assert summary_rows(summary) == [
        ("MATCHED", 3, 3, 3),
        ("AMOUNT_MISMATCH", 1, 1, 1),
        ("BANK_ONLY", 2, 2, 0),
        ("ACCOUNTING_ONLY", 1, 0, 1),
    ]


def test_summarize_empty_result_lists_every_status_with_zero():
    summary = summarize(make_result())

    assert summary_rows(summary) == [
        ("MATCHED", 0, 0, 0),
        ("AMOUNT_MISMATCH", 0, 0, 0),
        ("BANK_ONLY", 0, 0, 0),
        ("ACCOUNTING_ONLY", 0, 0, 0),
    ]


def test_summarize_keeps_missing_statuses_in_status_order():
    summary = summarize(
        make_result(
            ("ACCOUNTING_ONLY", None, "A003"),
            ("MATCHED", "B001", "A001"),
        )
    )

    assert summary_rows(summary) == [
        ("MATCHED", 1, 1, 1),
        ("AMOUNT_MISMATCH", 0, 0, 0),
        ("BANK_ONLY", 0, 0, 0),
        ("ACCOUNTING_ONLY", 1, 0, 1),
    ]


@pytest.mark.parametrize(
    "rows",
    [
        SAMPLE_RESULT,
        [("MATCHED", "B1", "A1"), ("MATCHED", "B2", "A2")],
        [("BANK_ONLY", "B1", None), ("ACCOUNTING_ONLY", None, "A1")],
        [],
    ],
    ids=["sample_dataset", "only_pairs", "only_single_records", "empty"],
)
def test_summarize_totals_close_without_double_counting(rows):
    result = make_result(*rows)

    summary = summarize(result)

    assert summary["items"].sum() == len(result)
    assert summary["bank_records"].sum() == result["bank_id"].notna().sum()
    assert summary["accounting_records"].sum() == result["accounting_id"].notna().sum()


def test_summarize_counts_a_pair_as_one_item_and_one_record_per_side():
    summary = summarize(make_result(("MATCHED", "B001", "A001")))

    matched = summary[summary["status"] == "MATCHED"].iloc[0]
    assert matched["items"] == 1
    assert matched["bank_records"] == 1
    assert matched["accounting_records"] == 1


def test_summarize_returns_integer_counts():
    summary = summarize(make_result(*SAMPLE_RESULT))

    for column in ["items", "bank_records", "accounting_records"]:
        assert summary[column].dtype == "int64", column


def test_summarize_does_not_modify_input():
    result = make_result(*SAMPLE_RESULT)
    result_before = result.copy()

    summarize(result)

    pd.testing.assert_frame_equal(result, result_before)
