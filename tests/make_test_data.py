"""
make_test_data.py
Generates synthetic data with planted traps and computes the 18-question benchmark answer key.
Seed is fixed for 100% reproducibility.
"""

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime

# Root paths
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
TESTS_DIR = PROJECT_ROOT / "tests"

DATA_DIR.mkdir(parents=True, exist_ok=True)
TESTS_DIR.mkdir(parents=True, exist_ok=True)

def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def generate_dataset():
    # -------------------------------------------------------------
    # 1. Customers Table (customers.csv)
    # 20 clean base customers + 3 planted traps:
    #   - 1 exact duplicate row (CUST-002)
    #   - 1 near-duplicate whitespace (CUST-005)
    #   - 1 near-duplicate email collision (CUST-021 with CUST-008's email)
    # -------------------------------------------------------------
    base_customers = [
        {"customer_id": "CUST-001", "name": "Alice Smith", "email": "alice.smith@example.com", "signup_date": "2023-01-15"},
        {"customer_id": "CUST-002", "name": "Bob Jones", "email": "bob.jones@example.com", "signup_date": "2023-02-20"},
        {"customer_id": "CUST-003", "name": "Charlie Brown", "email": "charlie.b@example.com", "signup_date": "2023-03-10"},
        {"customer_id": "CUST-004", "name": "Diana Prince", "email": "diana.p@example.com", "signup_date": "2023-04-05"},
        {"customer_id": "CUST-005", "name": "Robert Chen", "email": "robert.chen@example.com", "signup_date": "2023-05-12"},
        {"customer_id": "CUST-006", "name": "Fiona Gallagher", "email": "fiona.g@example.com", "signup_date": "2023-06-18"},
        {"customer_id": "CUST-007", "name": "George Clark", "email": "george.c@example.com", "signup_date": "2023-07-22"},
        {"customer_id": "CUST-008", "name": "Sara Jenkins", "email": "sara.jenkins@example.com", "signup_date": "2023-08-30"},
        {"customer_id": "CUST-009", "name": "Ian Malcolm", "email": "ian.malcolm@example.com", "signup_date": "2023-09-14"},
        {"customer_id": "CUST-010", "name": "Julia Roberts", "email": "julia.r@example.com", "signup_date": "2023-10-05"},
        {"customer_id": "CUST-011", "name": "Kevin Bacon", "email": "kevin.b@example.com", "signup_date": "2023-10-25"},
        {"customer_id": "CUST-012", "name": "Laura Croft", "email": "laura.croft@example.com", "signup_date": "2023-11-02"},
        {"customer_id": "CUST-013", "name": "Michael Scott", "email": "m.scott@example.com", "signup_date": "2023-11-15"},
        {"customer_id": "CUST-014", "name": "Nina Simone", "email": "nina.s@example.com", "signup_date": "2023-12-01"},
        {"customer_id": "CUST-015", "name": "Oscar Martinez", "email": "oscar.m@example.com", "signup_date": "2023-12-10"},
        {"customer_id": "CUST-016", "name": "Pam Beesly", "email": "pam.b@example.com", "signup_date": "2023-12-15"},
        {"customer_id": "CUST-017", "name": "Quinn Fabray", "email": "quinn.f@example.com", "signup_date": "2024-01-05"},
        {"customer_id": "CUST-018", "name": "Ryan Howard", "email": "ryan.h@example.com", "signup_date": "2024-01-12"},
        {"customer_id": "CUST-019", "name": "Stanley Hudson", "email": "stanley.h@example.com", "signup_date": "2024-01-18"},
        {"customer_id": "CUST-020", "name": "Toby Flenderson", "email": "toby.f@example.com", "signup_date": "2024-01-25"},
    ]

    customer_traps = [
        # Trap 1: Exact duplicate of CUST-002
        {"customer_id": "CUST-002", "name": "Bob Jones", "email": "bob.jones@example.com", "signup_date": "2023-02-20"},
        # Trap 2: Near duplicate customer with whitespace in name
        {"customer_id": "CUST-005", "name": "  Robert Chen  ", "email": "robert.chen@example.com", "signup_date": "2023-05-12"},
        # Trap 3: Different customer ID but duplicate email address (CUST-021 has Sara Jenkins' email)
        {"customer_id": "CUST-021", "name": "Sarah Jenkins", "email": "sara.jenkins@example.com", "signup_date": "2024-02-01"}
    ]
    all_customers = base_customers + customer_traps

    import csv

    # Write customers.csv
    customers_csv = DATA_DIR / "customers.csv"
    with open(customers_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["customer_id", "name", "email", "signup_date"])
        writer.writeheader()
        writer.writerows(all_customers)

    # -------------------------------------------------------------
    # 2. FX Rates Table (fx_rates.csv)
    # Planted trap:
    #   Orders contains GBP orders, but GBP rate is deliberately omitted!
    # -------------------------------------------------------------
    fx_rates = [
        {"currency": "USD", "rate_to_usd": 1.0, "effective_date": "2024-01-01"},
        {"currency": "EUR", "rate_to_usd": 1.08, "effective_date": "2024-01-01"},
        {"currency": "CAD", "rate_to_usd": 0.74, "effective_date": "2024-01-01"},
        # Note: GBP is intentionally omitted!
    ]
    fx_csv = DATA_DIR / "fx_rates.csv"
    with open(fx_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["currency", "rate_to_usd", "effective_date"])
        writer.writeheader()
        writer.writerows(fx_rates)

    # -------------------------------------------------------------
    # 3. Base Orders and Planted Traps (orders.csv)
    # Columns: order_id, customer_id, order_date, status, currency, amount
    #
    # Planted traps specified in prompt:
    # - Exact duplicate rows (8)
    # - Duplicates with messy status text like ' COMPLETED ' (3)
    # - Mixed date formats (ISO and DD/MM/YYYY)
    #   Calibrated so March 2024 revenue (Q06) is:
    #     DD/MM interpretation: 2343.21
    #     MM/DD interpretation: 1102.47
    # - Amounts as $12.00, €12.00, £12.00 or bare numbers
    # - Symbol contradicting currency column (2 rows)
    # - Blank currency (4 rows)
    # - Blank amount (6 rows)
    # - Orders whose customer ID doesn't exist (5 rows)
    # - GBP orders with no GBP rate (2 rows)
    # -------------------------------------------------------------

    # Base clean orders
    base_orders = [
        # January orders
        {"order_id": "ORD-1001", "customer_id": "CUST-001", "order_date": "2024-01-10", "status": "COMPLETED", "currency": "USD", "amount": "$150.00"},
        {"order_id": "ORD-1002", "customer_id": "CUST-002", "order_date": "2024-01-14", "status": "COMPLETED", "currency": "USD", "amount": "250.00"},
        {"order_id": "ORD-1003", "customer_id": "CUST-003", "order_date": "2024-01-18", "status": "COMPLETED", "currency": "USD", "amount": "$500.00"},
        {"order_id": "ORD-1004", "customer_id": "CUST-004", "order_date": "2024-01-22", "status": "COMPLETED", "currency": "USD", "amount": "$300.00"},
        {"order_id": "ORD-1005", "customer_id": "CUST-005", "order_date": "2024-01-28", "status": "CANCELLED", "currency": "USD", "amount": "$120.00"},

        # February orders
        {"order_id": "ORD-1006", "customer_id": "CUST-006", "order_date": "2024-02-05", "status": "COMPLETED", "currency": "USD", "amount": "$400.00"},
        {"order_id": "ORD-1007", "customer_id": "CUST-007", "order_date": "2024-02-12", "status": "COMPLETED", "currency": "USD", "amount": "350.00"},
        {"order_id": "ORD-1008", "customer_id": "CUST-008", "order_date": "2024-02-19", "status": "PENDING", "currency": "USD", "amount": "$180.00"},
        {"order_id": "ORD-1009", "customer_id": "CUST-009", "order_date": "2024-02-25", "status": "COMPLETED", "currency": "USD", "amount": "$220.00"},

        # March orders specifically designed for Q06:
        # Unambiguous March orders sum = 200.00 + 300.00 = 500.00
        {"order_id": "ORD-1010", "customer_id": "CUST-001", "order_date": "2024-03-15", "status": "COMPLETED", "currency": "USD", "amount": "$200.00"},
        {"order_id": "ORD-1011", "customer_id": "CUST-002", "order_date": "2024-03-22", "status": "COMPLETED", "currency": "USD", "amount": "$300.00"},
        # Ambiguous 05/03/2024:
        #   DD/MM = March 5 -> In March (+1843.21) -> March total DD/MM = 500 + 1843.21 = 2343.21
        #   MM/DD = May 3   -> In May
        {"order_id": "ORD-1012", "customer_id": "CUST-003", "order_date": "05/03/2024", "status": "COMPLETED", "currency": "USD", "amount": "$1,843.21"},
        # Ambiguous 03/05/2024:
        #   DD/MM = May 3   -> In May
        #   MM/DD = March 5 -> In March (+602.47)  -> March total MM/DD = 500 + 602.47 = 1102.47
        {"order_id": "ORD-1013", "customer_id": "CUST-004", "order_date": "03/05/2024", "status": "COMPLETED", "currency": "USD", "amount": "$602.47"},

        # April orders
        {"order_id": "ORD-1014", "customer_id": "CUST-005", "order_date": "2024-04-04", "status": "COMPLETED", "currency": "USD", "amount": "$450.00"},
        {"order_id": "ORD-1015", "customer_id": "CUST-006", "order_date": "2024-04-16", "status": "COMPLETED", "currency": "USD", "amount": "$550.00"},
        {"order_id": "ORD-1016", "customer_id": "CUST-007", "order_date": "2024-04-20", "status": "CANCELLED", "currency": "USD", "amount": "$200.00"},
        {"order_id": "ORD-1017", "customer_id": "CUST-008", "order_date": "2024-04-28", "status": "COMPLETED", "currency": "USD", "amount": "$600.00"},

        # May orders (unambiguous dates, day > 12 or ISO YYYY-MM-DD):
        # Notice ORD-1013 is on May 3rd under DD/MM: $602.47
        # We add orders summing to 3397.53 so total May completed revenue under DD/MM is exactly $4,000.00!
        {"order_id": "ORD-1020", "customer_id": "CUST-009", "order_date": "2024-05-14", "status": "COMPLETED", "currency": "USD", "amount": "$1,000.00"},
        {"order_id": "ORD-1021", "customer_id": "CUST-010", "order_date": "2024-05-18", "status": "COMPLETED", "currency": "USD", "amount": "$1,400.00"},
        {"order_id": "ORD-1022", "customer_id": "CUST-011", "order_date": "2024-05-26", "status": "COMPLETED", "currency": "USD", "amount": "$997.53"},

        # June orders
        {"order_id": "ORD-1023", "customer_id": "CUST-012", "order_date": "2024-06-10", "status": "COMPLETED", "currency": "USD", "amount": "$800.00"},
        {"order_id": "ORD-1024", "customer_id": "CUST-013", "order_date": "2024-06-22", "status": "COMPLETED", "currency": "USD", "amount": "$950.00"},

        # EUR Orders (for Q03)
        {"order_id": "ORD-1032", "customer_id": "CUST-014", "order_date": "2024-02-10", "status": "COMPLETED", "currency": "EUR", "amount": "€150.00"},
        {"order_id": "ORD-1033", "customer_id": "CUST-015", "order_date": "2024-02-18", "status": "COMPLETED", "currency": "EUR", "amount": "€200.00"},

        # GBP Orders (for Q05 trap: GBP exists in orders but not in fx_rates.csv)
        {"order_id": "ORD-1034", "customer_id": "CUST-016", "order_date": "2024-01-20", "status": "COMPLETED", "currency": "GBP", "amount": "£120.00"},
        {"order_id": "ORD-1035", "customer_id": "CUST-017", "order_date": "2024-01-25", "status": "COMPLETED", "currency": "GBP", "amount": "£180.00"},
    ]

    # Planted traps in orders:
    planted_orders = [
        # Symbol contradicting currency column (2 rows):
        # 1. Symbol $ but currency column is EUR (Q03/Q04 trap)
        {"order_id": "ORD-1030", "customer_id": "CUST-018", "order_date": "2024-04-12", "status": "COMPLETED", "currency": "EUR", "amount": "$350.00"},
        # 2. Symbol € but currency column is USD (Q03/Q04 trap)
        {"order_id": "ORD-1031", "customer_id": "CUST-019", "order_date": "2024-04-14", "status": "COMPLETED", "currency": "USD", "amount": "€450.00"},

        # Blank currency (4 rows):
        {"order_id": "ORD-1036", "customer_id": "CUST-001", "order_date": "2024-02-01", "status": "COMPLETED", "currency": "", "amount": "100.00"},
        {"order_id": "ORD-1037", "customer_id": "CUST-002", "order_date": "2024-02-02", "status": "COMPLETED", "currency": "", "amount": "200.00"},
        {"order_id": "ORD-1038", "customer_id": "CUST-003", "order_date": "2024-02-03", "status": "PENDING", "currency": "", "amount": "150.00"},
        {"order_id": "ORD-1039", "customer_id": "CUST-004", "order_date": "2024-02-04", "status": "CANCELLED", "currency": "", "amount": "50.00"},

        # Blank amount (6 rows):
        {"order_id": "ORD-1040", "customer_id": "CUST-001", "order_date": "2024-03-01", "status": "COMPLETED", "currency": "USD", "amount": ""},
        {"order_id": "ORD-1041", "customer_id": "CUST-002", "order_date": "2024-03-02", "status": "COMPLETED", "currency": "USD", "amount": ""},
        {"order_id": "ORD-1042", "customer_id": "CUST-003", "order_date": "2024-03-03", "status": "PENDING", "currency": "USD", "amount": ""},
        {"order_id": "ORD-1043", "customer_id": "CUST-004", "order_date": "2024-03-04", "status": "CANCELLED", "currency": "USD", "amount": ""},
        {"order_id": "ORD-1044", "customer_id": "CUST-005", "order_date": "2024-03-05", "status": "COMPLETED", "currency": "EUR", "amount": ""},
        {"order_id": "ORD-1045", "customer_id": "CUST-006", "order_date": "2024-03-06", "status": "COMPLETED", "currency": "USD", "amount": ""},

        # Orders whose customer ID doesn't exist in customers.csv (5 rows):
        {"order_id": "ORD-1046", "customer_id": "CUST-999", "order_date": "2024-04-01", "status": "COMPLETED", "currency": "USD", "amount": "$75.00"},
        {"order_id": "ORD-1047", "customer_id": "CUST-998", "order_date": "2024-04-02", "status": "COMPLETED", "currency": "USD", "amount": "$85.00"},
        {"order_id": "ORD-1048", "customer_id": "CUST-997", "order_date": "2024-04-03", "status": "PENDING", "currency": "USD", "amount": "$95.00"},
        {"order_id": "ORD-1049", "customer_id": "CUST-996", "order_date": "2024-04-04", "status": "CANCELLED", "currency": "USD", "amount": "$105.00"},
        {"order_id": "ORD-1050", "customer_id": "CUST-995", "order_date": "2024-04-05", "status": "COMPLETED", "currency": "EUR", "amount": "€115.00"},
    ]

    # Exact duplicate rows (8):
    exact_duplicates = [
        {"order_id": "ORD-1001", "customer_id": "CUST-001", "order_date": "2024-01-10", "status": "COMPLETED", "currency": "USD", "amount": "$150.00"},
        {"order_id": "ORD-1004", "customer_id": "CUST-004", "order_date": "2024-01-22", "status": "COMPLETED", "currency": "USD", "amount": "$300.00"},
        {"order_id": "ORD-1006", "customer_id": "CUST-006", "order_date": "2024-02-05", "status": "COMPLETED", "currency": "USD", "amount": "$400.00"},
        {"order_id": "ORD-1010", "customer_id": "CUST-001", "order_date": "2024-03-15", "status": "COMPLETED", "currency": "USD", "amount": "$200.00"},
        {"order_id": "ORD-1014", "customer_id": "CUST-005", "order_date": "2024-04-04", "status": "COMPLETED", "currency": "USD", "amount": "$450.00"},
        {"order_id": "ORD-1020", "customer_id": "CUST-009", "order_date": "2024-05-14", "status": "COMPLETED", "currency": "USD", "amount": "$1,000.00"},
        {"order_id": "ORD-1023", "customer_id": "CUST-012", "order_date": "2024-06-10", "status": "COMPLETED", "currency": "USD", "amount": "$800.00"},
        {"order_id": "ORD-1032", "customer_id": "CUST-014", "order_date": "2024-02-10", "status": "COMPLETED", "currency": "EUR", "amount": "€150.00"},
    ]

    # Duplicates with messy status text like " COMPLETED " (3):
    messy_status_duplicates = [
        {"order_id": "ORD-1002", "customer_id": "CUST-002", "order_date": "2024-01-14", "status": " COMPLETED ", "currency": "USD", "amount": "250.00"},
        {"order_id": "ORD-1007", "customer_id": "CUST-007", "order_date": "2024-02-12", "status": "completed", "currency": "USD", "amount": "350.00"},
        {"order_id": "ORD-1015", "customer_id": "CUST-006", "order_date": "2024-04-16", "status": " Completed  ", "currency": "USD", "amount": "$550.00"},
    ]

    all_orders = base_orders + planted_orders + exact_duplicates + messy_status_duplicates

    # Write orders.csv
    orders_csv = DATA_DIR / "orders.csv"
    with open(orders_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["order_id", "customer_id", "order_date", "status", "currency", "amount"])
        writer.writeheader()
        writer.writerows(all_orders)

    # -------------------------------------------------------------
    # 4. Refunds Table (refunds.csv)
    # Planted traps:
    # - 2 refunds for nonexistent orders (ORD-9999, ORD-8888)
    # - 1 duplicate refund (REF-101 duplicated)
    # Note: refunds.csv lacks currency column (per prompt & data_notes.txt)
    # -------------------------------------------------------------
    base_refunds = [
        {"refund_id": "REF-101", "order_id": "ORD-1001", "refund_date": "2024-01-25", "refund_amount": "25.00", "reason": "Customer return"},
        {"refund_id": "REF-102", "order_id": "ORD-1004", "refund_date": "2024-02-15", "refund_amount": "45.00", "reason": "Wrong item delivered"},
        {"refund_id": "REF-103", "order_id": "ORD-1020", "refund_date": "2024-05-20", "refund_amount": "100.00", "reason": "Customer discount dispute"},
        {"refund_id": "REF-104", "order_id": "ORD-1022", "refund_date": "2024-05-30", "refund_amount": "50.00", "reason": "Damaged packaging"},
    ]

    refund_traps = [
        # Trap: duplicate refund row (REF-101 duplicated)
        {"refund_id": "REF-101", "order_id": "ORD-1001", "refund_date": "2024-01-25", "refund_amount": "25.00", "reason": "Customer return"},
        # Trap: refund for nonexistent orders (2 rows)
        {"refund_id": "REF-901", "order_id": "ORD-9999", "refund_date": "2024-04-10", "refund_amount": "50.00", "reason": "Order cancelled prior to sync"},
        {"refund_id": "REF-902", "order_id": "ORD-8888", "refund_date": "2024-04-15", "refund_amount": "35.00", "reason": "System adjustment"},
    ]

    all_refunds = base_refunds + refund_traps
    refunds_csv = DATA_DIR / "refunds.csv"
    with open(refunds_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["refund_id", "order_id", "refund_date", "refund_amount", "reason"])
        writer.writeheader()
        writer.writerows(all_refunds)

    # -------------------------------------------------------------
    # 5. Monthly Summary Table (monthly_summary.csv)
    # Planted trap:
    # May 2024 total is 15% higher than orders support:
    # Under canonical DD/MM interpretation:
    # May completed orders total = $4,000.00
    # In monthly_summary.csv: May 2024 reported revenue = 4600.00 (15% higher)
    # Other months match the orders table.
    # -------------------------------------------------------------
    monthly_summaries = [
        {"month": "2024-01", "reported_revenue_usd": "1200.00", "reported_order_count": 4},
        {"month": "2024-02", "reported_revenue_usd": "970.00", "reported_order_count": 3},
        {"month": "2024-03", "reported_revenue_usd": "2343.21", "reported_order_count": 3},
        {"month": "2024-04", "reported_revenue_usd": "1600.00", "reported_order_count": 3},
        # Planted trap: May 2024 is 4600.00 instead of 4000.00 (15% higher than the orders support!)
        {"month": "2024-05", "reported_revenue_usd": "4600.00", "reported_order_count": 4},
        {"month": "2024-06", "reported_revenue_usd": "1750.00", "reported_order_count": 2},
    ]

    summary_csv = DATA_DIR / "monthly_summary.csv"
    with open(summary_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["month", "reported_revenue_usd", "reported_order_count"])
        writer.writeheader()
        writer.writerows(monthly_summaries)

    # -------------------------------------------------------------
    # 6. Data Notes (data_notes.txt)
    # Planted trap:
    # Claims "all amounts in orders.csv are USD", which contradicts
    # the currency column containing EUR and GBP!
    # -------------------------------------------------------------
    notes_content = """# Dataset Information and Schema Notes
Version: 1.0.4-snapshot
Generated: 2024-07-01

## Currency and Monetary Fields
- All transactions in orders.csv are recorded in USD unless otherwise specified. Note: All amounts are USD.
- Refunds do not specify currency directly; each refund amount is denominated in the currency of the associated order.
- Foreign exchange conversions should reference fx_rates.csv.

## Date Formats
- Timestamps are captured from regional store terminals.
- Formats primarily adhere to DD/MM/YYYY or ISO YYYY-MM-DD standard notation.

## Operational Rules
- Only orders with status 'COMPLETED' represent finalized revenue.
- Pending or cancelled orders should not be recognized as realized income.
- Refunds should be matched to their corresponding order_id before applying adjustments.
"""
    notes_file = DATA_DIR / "data_notes.txt"
    with open(notes_file, "w", encoding="utf-8") as f:
        f.write(notes_content)

    # -------------------------------------------------------------
    # 7. Compute SHA-256 Hashes (data_hashes.json)
    # -------------------------------------------------------------
    data_files = [
        "orders.csv",
        "customers.csv",
        "refunds.csv",
        "fx_rates.csv",
        "monthly_summary.csv",
        "data_notes.txt"
    ]
    hashes = {}
    for filename in data_files:
        hashes[filename] = sha256_file(DATA_DIR / filename)

    hashes_file = DATA_DIR / "data_hashes.json"
    with open(hashes_file, "w", encoding="utf-8") as f:
        json.dump(hashes, f, indent=2)

    # -------------------------------------------------------------
    # 8. Compute Ground Truth Answers for the 18 Questions
    # -------------------------------------------------------------
    # Parse orders properly for calculations:
    # Unique orders by order_id:
    # When multiple rows exist for order_id, status should be stripped and normalized.
    # Statuses: 'COMPLETED', 'PENDING', 'CANCELLED'.
    clean_orders = {}
    for o in base_orders + planted_orders:
        clean_orders[o["order_id"]] = o

    # Valid completed orders:
    # Exclude: blank amount, blank currency, orphan customer IDs (CUST-99x)
    valid_customer_ids = {c["customer_id"] for c in base_customers}

    def parse_amt(amt_str):
        if not amt_str:
            return 0.0
        cleaned = amt_str.replace("$", "").replace("€", "").replace("£", "").replace(",", "").strip()
        return float(cleaned) if cleaned else 0.0

    valid_completed_orders = {}
    for oid, o in clean_orders.items():
        st = o["status"].strip().upper()
        if st == "COMPLETED" and o["amount"] and o["currency"] and o["customer_id"] in valid_customer_ids:
            valid_completed_orders[oid] = o

    # USD completed orders (with currency column authoritative):
    # Notice: ORD-1031 has currency='USD' and amount='€450.00'.
    # If currency column is authoritative, ORD-1031 is USD: 450.00.
    # If symbol is authoritative, ORD-1031 is EUR.
    usd_completed_currency_auth = [
        o for o in valid_completed_orders.values() if o["currency"] == "USD"
    ]
    total_usd_rev_currency_auth = sum(parse_amt(o["amount"]) for o in usd_completed_currency_auth)

    # If symbol is authoritative:
    usd_completed_symbol_auth = [
        o for o in valid_completed_orders.values()
        if ("$" in o["amount"] or (o["currency"] == "USD" and "€" not in o["amount"] and "£" not in o["amount"]))
        and "€" not in o["amount"] and "£" not in o["amount"]
    ]
    # In our set:
    # ORD-1030 has currency='EUR', amount='$350.00' (symbol $)
    # ORD-1031 has currency='USD', amount='€450.00' (symbol €)
    total_usd_rev_symbol_auth = sum(
        parse_amt(o["amount"]) for o in valid_completed_orders.values()
        if "$" in o["amount"] or (o["amount"] in ["250.00", "350.00"] and o["currency"] == "USD")
    )

    # EUR completed orders:
    eur_completed_currency_auth = [
        o for o in valid_completed_orders.values() if o["currency"] == "EUR"
    ]
    total_eur_rev_currency_auth = sum(parse_amt(o["amount"]) for o in eur_completed_currency_auth)
    # ORD-1032 (€150), ORD-1033 (€200), ORD-1030 ($350 but currency EUR) -> 700.00

    eur_completed_symbol_auth = [
        o for o in valid_completed_orders.values() if "€" in o["amount"]
    ]
    total_eur_rev_symbol_auth = sum(parse_amt(o["amount"]) for o in eur_completed_symbol_auth)
    # ORD-1032 (€150), ORD-1033 (€200), ORD-1031 (€450) -> 800.00

    # March 2024 DD/MM vs MM/DD:
    # DD/MM: ORD-1010 ($200) + ORD-1011 ($300) + ORD-1012 ($1843.21) = 2343.21
    # MM/DD: ORD-1010 ($200) + ORD-1011 ($300) + ORD-1013 ($602.47) = 1102.47
    march_dd_mm = 2343.21
    march_mm_dd = 1102.47

    # May 2024 total revenue:
    # Orders sum under DD/MM: ORD-1013 ($602.47) + ORD-1020 ($1000) + ORD-1021 ($1400) + ORD-1022 ($997.53) = 4000.00
    # monthly_summary.csv reports 4600.00 (+15.0%)
    may_orders_revenue = 4000.00
    may_summary_revenue = 4600.00

    # Refunds calculations:
    # Valid non-duplicate refunds matching completed USD orders:
    # REF-101 ($25 on ORD-1001), REF-102 ($45 on ORD-1004), REF-103 ($100 on ORD-1020), REF-104 ($50 on ORD-1022)
    # Excludes duplicate REF-101, excludes REF-901 (ORD-9999) and REF-902 (ORD-8888).
    valid_refunds_total = 25.00 + 45.00 + 100.00 + 50.00  # 220.00

    # Unique customers with completed orders:
    customers_with_completed_orders = len(set(o["customer_id"] for o in valid_completed_orders.values()))

    # Total unique completed orders count:
    valid_completed_orders_count = len(valid_completed_orders)

    # Average Order Value (AOV) for USD completed orders:
    usd_order_count = len(usd_completed_currency_auth)
    usd_aov = round(total_usd_rev_currency_auth / usd_order_count, 2)

    # Top customer spend in USD:
    cust_spend = {}
    for o in usd_completed_currency_auth:
        cid = o["customer_id"]
        cust_spend[cid] = cust_spend.get(cid, 0.0) + parse_amt(o["amount"])
    top_customer_id = max(cust_spend, key=cust_spend.get)
    top_customer_spend = cust_spend[top_customer_id]

    # Net revenue (USD completed - valid refunds):
    net_revenue_usd = round(total_usd_rev_currency_auth - valid_refunds_total, 2)

    questions_answer_key = [
        {
            "id": "Q01",
            "question": "What is the total number of unique valid completed orders?",
            "expected_verdict": "answerable",
            "expected_value": valid_completed_orders_count,
            "alt_values": {
                "including_orphan_customers": valid_completed_orders_count + 1  # ORD-1046 (CUST-999)
            },
            "assumptions": [
                "Deduplicates exact duplicate rows and messy status whitespace/casing",
                "Excludes orders with missing amounts, missing currencies, or cancelled/pending status",
                "Excludes orders belonging to nonexistent customer IDs"
            ],
            "reason": "Requires deduplicating duplicate rows, normalizing status whitespace/case (' COMPLETED '), and excluding rows with null amounts or orphan customer IDs."
        },
        {
            "id": "Q02",
            "question": "What is the total revenue from completed USD orders?",
            "expected_verdict": "answerable",
            "expected_value": round(total_usd_rev_currency_auth, 2),
            "alt_values": {
                "symbol_authoritative": round(total_usd_rev_symbol_auth, 2)
            },
            "assumptions": [
                "Assumes currency column takes precedence when currency symbol contradicts currency column",
                "Deduplicates rows and excludes blank amounts and cancelled/pending orders"
            ],
            "reason": "Requires parsing currency amounts (stripping '$', '€', commas), deduplicating rows, and filtering for completed USD transactions."
        },
        {
            "id": "Q03",
            "question": "What is the total revenue for completed EUR orders?",
            "expected_verdict": "answerable_with_assumption",
            "expected_value": round(total_eur_rev_currency_auth, 2),
            "alt_values": {
                "symbol_authoritative": round(total_eur_rev_symbol_auth, 2),
                "unambiguous_only": 350.00
            },
            "assumptions": [
                "Assumes currency column is authoritative over conflicting currency symbols (e.g., ORD-1030 has amount '$350.00' but currency 'EUR')"
            ],
            "reason": "Row ORD-1030 contains a conflicting dollar symbol '$350.00' with currency 'EUR'. Answer is answerable under the assumption that the currency column is authoritative."
        },
        {
            "id": "Q04",
            "question": "What is the total revenue for completed orders where currency is USD, resolving symbol vs currency conflicts?",
            "expected_verdict": "answerable_with_assumption",
            "expected_value": round(total_usd_rev_currency_auth, 2),
            "alt_values": {
                "symbol_authoritative": round(total_usd_rev_symbol_auth, 2)
            },
            "assumptions": [
                "Assumes currency column takes precedence over symbol in amount string (including ORD-1031 which has '€450.00' but currency 'USD')"
            ],
            "reason": "Row ORD-1031 has currency 'USD' but amount '€450.00'. Resolving requires explicitly declaring the assumption that the currency column takes precedence."
        },
        {
            "id": "Q05",
            "question": "What is the total revenue across all currencies converted to USD?",
            "expected_verdict": "cannot_determine",
            "expected_value": None,
            "alt_values": {},
            "assumptions": [],
            "reason": "The orders table contains transactions in GBP (ORD-1034, ORD-1035), but fx_rates.csv does not contain an exchange rate for GBP."
        },
        {
            "id": "Q06",
            "question": "What is the total revenue of completed orders for March 2024?",
            "expected_verdict": "answerable_with_assumption",
            "expected_value": march_dd_mm,
            "alt_values": {
                "MM_DD_YYYY": march_mm_dd
            },
            "assumptions": [
                "Assumes ambiguous date strings (such as 05/03/2024 and 03/05/2024) follow the DD/MM/YYYY convention per regional store notes"
            ],
            "reason": "Orders contains ambiguous dates where DD/MM and MM/DD interpretations diverge into different months. Under DD/MM/YYYY, March total is 2343.21; under MM/DD/YYYY, March total is 1102.47."
        },
        {
            "id": "Q07",
            "question": "What was the total revenue for May 2024?",
            "expected_verdict": "contradiction",
            "expected_value": {
                "orders_total": may_orders_revenue,
                "summary_total": may_summary_revenue,
                "discrepancy_pct": 15.0
            },
            "alt_values": {
                "orders_only": may_orders_revenue,
                "summary_only": may_summary_revenue
            },
            "assumptions": [
                "Flags cross-table contradiction between orders.csv and monthly_summary.csv"
            ],
            "reason": "The orders table supports a May 2024 revenue of 4000.00, whereas monthly_summary.csv reports 4600.00 (exactly 15% higher)."
        },
        {
            "id": "Q08",
            "question": "What is the average customer satisfaction (CSAT) rating for orders in 2024?",
            "expected_verdict": "cannot_determine",
            "expected_value": None,
            "alt_values": {},
            "assumptions": [],
            "reason": "No customer satisfaction scores, review tables, or rating columns exist in the dataset."
        },
        {
            "id": "Q09",
            "question": "What is the overall profit margin for completed orders?",
            "expected_verdict": "cannot_determine",
            "expected_value": None,
            "alt_values": {},
            "assumptions": [],
            "reason": "The dataset contains top-line revenue but no cost of goods sold (COGS), purchase costs, or margin information."
        },
        {
            "id": "Q10",
            "question": "What is the total revenue by product category?",
            "expected_verdict": "cannot_determine",
            "expected_value": None,
            "alt_values": {},
            "assumptions": [],
            "reason": "Neither product category nor item-level line item metadata exists in orders.csv or supporting tables."
        },
        {
            "id": "Q11",
            "question": "How many unique registered customers have placed at least one completed order?",
            "expected_verdict": "answerable",
            "expected_value": customers_with_completed_orders,
            "alt_values": {
                "including_orphan_customers": customers_with_completed_orders + 1
            },
            "assumptions": [
                "Excludes orphaned customer IDs (e.g. CUST-999) not present in customers.csv",
                "Deduplicates customers with messy whitespace or multiple registrations"
            ],
            "reason": "Requires deduplicating customer IDs and verifying membership against registered customers in customers.csv."
        },
        {
            "id": "Q12",
            "question": "What is the net revenue for completed USD orders after subtracting valid refunds?",
            "expected_verdict": "answerable_with_assumption",
            "expected_value": net_revenue_usd,
            "alt_values": {
                "including_duplicate_refunds": round(total_usd_rev_currency_auth - (valid_refunds_total + 25.00), 2)
            },
            "assumptions": [
                "Assumes refunds inherit the currency of the associated order per data_notes.txt",
                "Deduplicates duplicate refund entries (REF-101) and excludes refunds referencing nonexistent orders (REF-901, REF-902)"
            ],
            "reason": "Refunds table has no currency column. Answering requires adopting the assumption in data_notes.txt and pruning orphan/duplicate refunds."
        },
        {
            "id": "Q13",
            "question": "What is the average order value (AOV) for completed USD orders?",
            "expected_verdict": "answerable",
            "expected_value": usd_aov,
            "alt_values": {},
            "assumptions": [
                "Calculated as total completed USD revenue divided by number of unique completed USD orders",
                "Assumes currency column takes precedence for symbol conflict rows"
            ],
            "reason": "Requires computing the quotient of deduplicated completed USD revenue and completed USD order count."
        },
        {
            "id": "Q14",
            "question": "Why did sales drop between March and April 2024?",
            "expected_verdict": "cannot_determine",
            "expected_value": None,
            "alt_values": {},
            "assumptions": [],
            "reason": "The dataset contains transactional event records but no causal, attribution, web traffic, or marketing campaign data to explain why sales changed."
        },
        {
            "id": "Q15",
            "question": "Which customer ID generated the highest total spend on completed USD orders, and what was the amount?",
            "expected_verdict": "answerable",
            "expected_value": {
                "customer_id": top_customer_id,
                "total_spend": top_customer_spend
            },
            "alt_values": {},
            "assumptions": [
                "Aggregates deduplicated completed USD orders per registered customer ID"
            ],
            "reason": "Requires grouping valid completed USD orders by customer_id and finding the argmax."
        },
        {
            "id": "Q16",
            "question": "What was the total order revenue in the first quarter (Q1) of 2025?",
            "expected_verdict": "cannot_determine",
            "expected_value": None,
            "alt_values": {},
            "assumptions": [],
            "reason": "The dataset only covers orders placed in calendar year 2024. No records exist for 2025."
        },
        {
            "id": "Q17",
            "question": "What is the total refund amount for valid, non-duplicated completed orders?",
            "expected_verdict": "answerable",
            "expected_value": valid_refunds_total,
            "alt_values": {
                "including_duplicates": valid_refunds_total + 25.00,
                "including_nonexistent_orders": valid_refunds_total + 85.00
            },
            "assumptions": [
                "Deduplicates identical refund rows (REF-101)",
                "Excludes refunds referencing invalid or nonexistent order IDs (REF-901, REF-902)"
            ],
            "reason": "Requires cross-checking refunds against valid orders and eliminating duplicate submissions."
        },
        {
            "id": "Q18",
            "question": "What is the total revenue?",
            "expected_verdict": "ambiguous",
            "expected_value": None,
            "alt_values": {},
            "assumptions": [],
            "reason": "The question is underspecified: it does not specify currency (orders are denominated in USD, EUR, GBP), order status (all orders vs completed only), timeframe, or whether refunds should be deducted."
        }
    ]

    # Write questions_answer_key.json
    key_file = TESTS_DIR / "questions_answer_key.json"
    with open(key_file, "w", encoding="utf-8") as f:
        json.dump(questions_answer_key, f, indent=2)

    # Write clean questions.json (just the questions for testing runners)
    clean_questions = [
        {"id": q["id"], "question": q["question"]}
        for q in questions_answer_key
    ]
    questions_file = TESTS_DIR / "questions.json"
    with open(questions_file, "w", encoding="utf-8") as f:
        json.dump(clean_questions, f, indent=2)

    print("=" * 60)
    print("TEST DATA GENERATION COMPLETE")
    print("=" * 60)
    print(f"Data files generated in: {DATA_DIR}")
    for fname, sha in hashes.items():
        print(f"  {fname:<20} SHA-256: {sha[:16]}...")
    print(f"\n18 questions and answer key generated in: {key_file}")
    print(f"Planted traps summary:")
    print(f"  - Exact duplicate rows in orders.csv: {len(exact_duplicates)}")
    print(f"  - Messy status duplicates in orders.csv: {len(messy_status_duplicates)}")
    print(f"  - Symbol vs currency conflict rows in orders.csv: 2")
    print(f"  - Blank currency rows in orders.csv: 4")
    print(f"  - Blank amount rows in orders.csv: 6")
    print(f"  - Orphan customer orders in orders.csv: 5")
    print(f"  - GBP orders without fx_rates: 2")
    print(f"  - Duplicate / near-duplicate customers in customers.csv: {len(customer_traps)}")
    print(f"  - Nonexistent order refunds in refunds.csv: 2")
    print(f"  - Duplicate refund in refunds.csv: 1")
    print(f"  - May 2024 monthly summary contradiction: orders={may_orders_revenue:.2f}, summary={may_summary_revenue:.2f} (+15%)")
    print(f"  - Notes contradiction: data_notes.txt claims all amounts are USD")
    print(f"  - Q06 date ambiguity: DD/MM={march_dd_mm:.2f} vs MM/DD={march_mm_dd:.2f}")
    print("=" * 60)

if __name__ == "__main__":
    generate_dataset()
