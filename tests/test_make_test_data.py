"""
test_make_test_data.py
Unit tests and integrity validation for make_test_data.py.
Asserts that all planted traps, tables, hashes, and 18-question answer keys exist
and conform strictly to specification.
"""

import json
import sys
import unittest
import pandas as pd
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.make_test_data import DATA_DIR, TESTS_DIR, sha256_file, generate_dataset

def test_generation_and_integrity():
    # Run generator
    generate_dataset()

    # Check files exist
    assert (DATA_DIR / "orders.csv").exists()
    assert (DATA_DIR / "customers.csv").exists()
    assert (DATA_DIR / "refunds.csv").exists()
    assert (DATA_DIR / "fx_rates.csv").exists()
    assert (DATA_DIR / "monthly_summary.csv").exists()
    assert (DATA_DIR / "data_notes.txt").exists()
    assert (DATA_DIR / "data_hashes.json").exists()
    assert (TESTS_DIR / "questions_answer_key.json").exists()
    assert (TESTS_DIR / "questions.json").exists()

    # Verify SHA-256 hashes
    with open(DATA_DIR / "data_hashes.json", "r", encoding="utf-8") as f:
        hashes = json.load(f)

    for fname, expected_hash in hashes.items():
        assert sha256_file(DATA_DIR / fname) == expected_hash

    # Verify 18 questions
    with open(TESTS_DIR / "questions_answer_key.json", "r", encoding="utf-8") as f:
        key = json.load(f)
    assert len(key) == 18

    verdicts = {q["id"]: q["expected_verdict"] for q in key}
    assert verdicts["Q01"] == "answerable"
    assert verdicts["Q02"] == "answerable"
    assert verdicts["Q03"] == "answerable_with_assumption"
    assert verdicts["Q04"] == "answerable_with_assumption"
    assert verdicts["Q05"] == "cannot_determine"
    assert verdicts["Q06"] == "answerable_with_assumption"
    assert verdicts["Q07"] == "contradiction"
    assert verdicts["Q08"] == "cannot_determine"
    assert verdicts["Q09"] == "cannot_determine"
    assert verdicts["Q10"] == "cannot_determine"
    assert verdicts["Q11"] == "answerable"
    assert verdicts["Q12"] == "answerable_with_assumption"
    assert verdicts["Q13"] == "answerable"
    assert verdicts["Q14"] == "cannot_determine"
    assert verdicts["Q15"] == "answerable"
    assert verdicts["Q16"] == "cannot_determine"
    assert verdicts["Q17"] == "answerable"
    assert verdicts["Q18"] == "ambiguous"

    # Verify Q06 values
    q06 = next(q for q in key if q["id"] == "Q06")
    assert q06["expected_value"] == 2343.21
    assert q06["alt_values"]["MM_DD_YYYY"] == 1102.47

    # Verify Q07 contradiction values
    q07 = next(q for q in key if q["id"] == "Q07")
    assert q07["expected_value"]["orders_total"] == 4000.00
    assert q07["expected_value"]["summary_total"] == 4600.00
    assert q07["expected_value"]["discrepancy_pct"] == 15.0

    # Verify orders traps directly from CSV
    orders_df = pd.read_csv(DATA_DIR / "orders.csv", keep_default_na=False)
    
    # 8 exact duplicates
    exact_dups = orders_df[orders_df.duplicated(keep=False)]
    assert len(exact_dups) == 16  # 8 pairs of duplicates = 16 rows

    # Blank amounts
    blank_amounts = orders_df[orders_df["amount"] == ""]
    assert len(blank_amounts) == 6

    # Blank currency
    blank_currencies = orders_df[orders_df["currency"] == ""]
    assert len(blank_currencies) == 4

    # Nonexistent customer IDs
    cust_df = pd.read_csv(DATA_DIR / "customers.csv")
    valid_cids = set(cust_df["customer_id"].unique())
    orphan_orders = orders_df[~orders_df["customer_id"].isin(valid_cids)]
    assert len(orphan_orders) == 5

    # Refunds traps
    refunds_df = pd.read_csv(DATA_DIR / "refunds.csv")
    valid_oids = set(orders_df["order_id"].unique())
    orphan_refunds = refunds_df[~refunds_df["order_id"].isin(valid_oids)]
    assert len(orphan_refunds) == 2

    dup_refunds = refunds_df[refunds_df.duplicated(keep=False)]
    assert len(dup_refunds) == 2  # 1 duplicate pair = 2 rows

    print("All tests and planted trap validations passed successfully!")

if __name__ == "__main__":
    test_generation_and_integrity()
