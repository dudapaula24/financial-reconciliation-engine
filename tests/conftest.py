import pytest

from reconciliation.loader import load_records
from reconciliation.reconciler import reconcile

SAMPLE_BANK_CSV = """\
id,date,description,amount
B001,2026-09-01,Alpha Office Supplies,-350.00
B002,2026-09-02,BETA CONSULTING,1200.50
B003,2026-09-03,Monthly Bank Fee,-15.00
B004,2026-09-05,DELTA LOGISTICS,1000.00
B005,2026-09-08,Epsilon Cleaning Services,-200.00
B006,2026-09-08,Epsilon Cleaning Services,-200.00
"""

SAMPLE_ACCOUNTING_CSV = """\
id,date,description,amount
A001,2026-09-01,Alpha Office Supplies,-350.00
A002,2026-09-02,Beta Consulting,1200.50
A003,2026-09-04,Gamma Software License,-89.90
A004,2026-09-05,Delta Logistics,990.00
A005,2026-09-08,Epsilon Cleaning Services,-200.00
"""


@pytest.fixture
def sample_files(tmp_path):
    """Write the fictional sample dataset to temporary CSV files and return (bank, accounting) paths."""
    bank_path = tmp_path / "bank_transactions.csv"
    accounting_path = tmp_path / "accounting_records.csv"
    bank_path.write_text(SAMPLE_BANK_CSV, encoding="utf-8")
    accounting_path.write_text(SAMPLE_ACCOUNTING_CSV, encoding="utf-8")
    return bank_path, accounting_path


@pytest.fixture
def sample_result(sample_files):
    bank_path, accounting_path = sample_files
    return reconcile(load_records(bank_path), load_records(accounting_path))
