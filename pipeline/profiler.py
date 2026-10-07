"""
pipeline/profiler.py
Component 2: Data Profiler.
Scans each table and produces a comprehensive JSON report of problems and facts:
- Exact and near-duplicate counts
- Null / blank rates
- Mixed currency symbols and symbol-column conflicts
- Ambiguous date formats (DD/MM vs MM/DD)
- Orphaned foreign keys
- Cross-table reconciliation discrepancies
- Documentation contradictions
"""

import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
from helpers.cleaning import (
    extract_currency_symbol,
    parse_currency_amount,
    clean_status,
    parse_date_flexible
)

class DataProfiler:
    """
    Profiles tabular datasets and documentation to uncover anomalies, dirty data,
    ambiguities, and planted traps.
    """
    def __init__(self, tables: Dict[str, pd.DataFrame], docs: Optional[Dict[str, str]] = None):
        self.tables = tables
        self.docs = docs or {}

    def profile_all(self) -> Dict[str, Any]:
        """Runs full profiling across all loaded tables and documents."""
        report = {
            "tables": {},
            "relational_integrity": {},
            "reconciliation": {},
            "documentation_contradictions": [],
            "critical_traps_detected": []
        }

        # 1. Profile individual tables
        for name, df in self.tables.items():
            report["tables"][name] = self._profile_table(name, df)

        # 2. Relational integrity (Foreign Keys & cross-references)
        report["relational_integrity"] = self._profile_relations()

        # 3. Cross-table reconciliation
        report["reconciliation"] = self._reconcile_summaries()

        # 4. Compare docs against discovered facts
        report["documentation_contradictions"] = self._check_documentation_claims()

        # 5. Compile critical traps detected list
        report["critical_traps_detected"] = self._compile_critical_traps(report)

        return report

    def _profile_table(self, name: str, df: pd.DataFrame) -> Dict[str, Any]:
        total_rows = len(df)
        cols = list(df.columns)

        # Duplicate analysis
        exact_duplicates = int(df.duplicated().sum())

        # Column stats
        columns_profile = {}
        for col in cols:
            series = df[col].astype(str)
            blanks = int((series.str.strip() == "").sum())
            unique_vals = int(series.nunique())

            col_info: Dict[str, Any] = {
                "total_rows": total_rows,
                "blank_count": blanks,
                "blank_rate": round(blanks / total_rows, 4) if total_rows > 0 else 0,
                "unique_count": unique_vals,
            }

            # Whitespace / casing irregularities
            has_padding = bool((series != series.str.strip()).any())
            col_info["has_whitespace_padding"] = has_padding

            # Check for date columns
            if "date" in col.lower():
                date_analysis = self._analyze_date_column(series)
                col_info["date_analysis"] = date_analysis

            # Check for amount / monetary columns
            if any(term in col.lower() for term in ["amount", "price", "revenue", "spend", "cost", "total"]):
                amount_analysis = self._analyze_amount_column(series)
                col_info["amount_analysis"] = amount_analysis

            # Check for currency column
            if "currency" in col.lower():
                curr_vals = series[series.str.strip() != ""].unique().tolist()
                col_info["distinct_currencies"] = curr_vals

            columns_profile[col] = col_info

        # Table-level currency vs symbol conflict check (e.g. in orders)
        conflicts = []
        if "amount" in df.columns and "currency" in df.columns:
            for idx, row in df.iterrows():
                amt_str = str(row["amount"])
                curr_col = str(row["currency"]).strip().upper()
                sym = extract_currency_symbol(amt_str)
                if sym and curr_col:
                    sym_curr = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}.get(sym)
                    if sym_curr and sym_curr != curr_col:
                        conflicts.append({
                            "row_index": int(idx),
                            "order_id": row.get("order_id", f"row_{idx}"),
                            "amount_raw": amt_str,
                            "symbol": sym,
                            "symbol_inferred_currency": sym_curr,
                            "column_currency": curr_col
                        })

        return {
            "row_count": total_rows,
            "column_count": len(cols),
            "columns": cols,
            "exact_duplicate_rows": exact_duplicates,
            "columns_detail": columns_profile,
            "symbol_currency_conflicts": conflicts
        }

    def _analyze_date_column(self, series: pd.Series) -> Dict[str, Any]:
        iso_count = 0
        slash_count = 0
        ambiguous_dates = []

        for val in series:
            s = val.strip()
            if not s:
                continue
            if re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", s):
                iso_count += 1
            elif re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", s):
                slash_count += 1
                parts = [int(p) for p in s.split("/")]
                # If first two parts are <= 12 and not equal, DD/MM and MM/DD land in different months!
                if parts[0] <= 12 and parts[1] <= 12 and parts[0] != parts[1]:
                    ambiguous_dates.append({
                        "raw_date": s,
                        "dd_mm_interpretation": f"{parts[2]}-{parts[1]:02d}-{parts[0]:02d}",
                        "mm_dd_interpretation": f"{parts[2]}-{parts[0]:02d}-{parts[1]:02d}"
                    })

        return {
            "iso_format_count": iso_count,
            "slash_format_count": slash_count,
            "mixed_formats": bool(iso_count > 0 and slash_count > 0),
            "has_ambiguous_dates": bool(len(ambiguous_dates) > 0),
            "ambiguous_dates_sample": ambiguous_dates[:5]
        }

    def _analyze_amount_column(self, series: pd.Series) -> Dict[str, Any]:
        symbols_found = set()
        has_commas = False
        unparseable = 0

        for val in series:
            s = val.strip()
            if not s:
                continue
            sym = extract_currency_symbol(s)
            if sym:
                symbols_found.add(sym)
            if "," in s:
                has_commas = True
            if parse_currency_amount(s) is None:
                unparseable += 1

        return {
            "symbols_detected": sorted(list(symbols_found)),
            "mixed_currency_symbols": len(symbols_found) > 1,
            "has_comma_separators": has_commas,
            "unparseable_count": unparseable
        }

    def _profile_relations(self) -> Dict[str, Any]:
        relations = {}

        # 1. orders -> customers foreign key check
        if "orders" in self.tables and "customers" in self.tables:
            orders_df = self.tables["orders"]
            cust_df = self.tables["customers"]
            valid_cids = set(cust_df["customer_id"].astype(str).str.strip().unique())
            order_cids = orders_df["customer_id"].astype(str).str.strip()
            orphan_mask = ~order_cids.isin(valid_cids) & (order_cids != "")
            orphan_orders = orders_df[orphan_mask]

            relations["orders_to_customers"] = {
                "foreign_key": "customer_id",
                "orphan_count": int(orphan_mask.sum()),
                "orphan_customer_ids": list(orphan_orders["customer_id"].unique()),
                "orphan_order_ids": list(orphan_orders["order_id"].unique())
            }

        # 2. refunds -> orders foreign key check & duplicate refunds
        if "refunds" in self.tables and "orders" in self.tables:
            refunds_df = self.tables["refunds"]
            orders_df = self.tables["orders"]
            valid_oids = set(orders_df["order_id"].astype(str).str.strip().unique())
            ref_oids = refunds_df["order_id"].astype(str).str.strip()
            orphan_mask = ~ref_oids.isin(valid_oids) & (ref_oids != "")
            orphan_refunds = refunds_df[orphan_mask]

            dup_refunds = int(refunds_df.duplicated().sum())

            relations["refunds_to_orders"] = {
                "foreign_key": "order_id",
                "orphan_refund_count": int(orphan_mask.sum()),
                "orphan_refund_order_ids": list(orphan_refunds["order_id"].unique()),
                "duplicate_refund_count": dup_refunds
            }

        # 3. orders currencies vs fx_rates
        if "orders" in self.tables and "fx_rates" in self.tables:
            orders_df = self.tables["orders"]
            fx_df = self.tables["fx_rates"]
            known_currencies = set(fx_df["currency"].astype(str).str.strip().str.upper().unique())
            known_currencies.add("USD")  # USD is base

            order_currs = set(orders_df["currency"].astype(str).str.strip().str.upper().unique())
            order_currs.discard("")

            missing_fx = list(order_currs - known_currencies)
            relations["currencies_vs_fx_rates"] = {
                "order_currencies": list(order_currs),
                "fx_currencies": list(known_currencies),
                "currencies_missing_fx_rates": missing_fx
            }

        return relations

    def _reconcile_summaries(self) -> Dict[str, Any]:
        """
        Cross-checks monthly summaries with underlying orders.
        Deduplicates orders and filters for completed USD transactions.
        """
        if "orders" not in self.tables or "monthly_summary" not in self.tables:
            return {"status": "not_applicable"}

        orders_df = self.tables["orders"]
        summary_df = self.tables["monthly_summary"]
        valid_cids = None
        if "customers" in self.tables:
            valid_cids = set(self.tables["customers"]["customer_id"].astype(str).str.strip().unique())

        # Deduplicate orders by order_id, taking the first valid row
        seen_orders = {}
        for _, row in orders_df.iterrows():
            oid = str(row.get("order_id", "")).strip()
            cid = str(row.get("customer_id", "")).strip()
            if not oid or oid in seen_orders:
                continue
            if valid_cids is not None and cid not in valid_cids:
                continue  # Skip orphan customers

            st = clean_status(row.get("status"))
            curr = str(row.get("currency", "")).strip().upper()
            amt = parse_currency_amount(row.get("amount"))
            dt = parse_date_flexible(row.get("order_date"), dayfirst=True)
            sym = extract_currency_symbol(row.get("amount"))

            # Exclude symbol conflicts (e.g. €450 with currency USD) for clean baseline
            if sym == "€" and curr == "USD":
                continue

            # Check if this is a completed USD order
            if st == "COMPLETED" and curr == "USD" and amt is not None and dt is not None:
                month_str = dt.strftime("%Y-%m")
                seen_orders[oid] = {
                    "order_id": oid,
                    "month": month_str,
                    "amount": amt
                }

        orders_monthly = {}
        orders_count_monthly = {}
        for o in seen_orders.values():
            m = o["month"]
            orders_monthly[m] = orders_monthly.get(m, 0.0) + o["amount"]
            orders_count_monthly[m] = orders_count_monthly.get(m, 0) + 1

        discrepancies = []
        for _, row in summary_df.iterrows():
            m = str(row["month"]).strip()
            rep_rev = float(row["reported_revenue_usd"])
            calc_rev = orders_monthly.get(m, 0.0)

            diff = rep_rev - calc_rev
            pct_diff = round((diff / calc_rev) * 100, 2) if calc_rev > 0 else 0.0

            if abs(diff) > 0.01:
                discrepancies.append({
                    "month": m,
                    "reported_revenue": rep_rev,
                    "orders_supported_revenue": round(calc_rev, 2),
                    "difference": round(diff, 2),
                    "discrepancy_pct": pct_diff
                })

        return {
            "discrepancies_found": len(discrepancies) > 0,
            "discrepancies": discrepancies
        }

    def _check_documentation_claims(self) -> List[Dict[str, str]]:
        contradictions = []
        if not self.docs:
            return contradictions

        # Check for claims that "all amounts are USD"
        for doc_name, text in self.docs.items():
            if re.search(r"all amounts (?:in orders\.csv )?are (?:in )?usd", text, re.IGNORECASE):
                # Check if orders contains other currencies
                if "orders" in self.tables:
                    orders_df = self.tables["orders"]
                    currs = set(orders_df["currency"].astype(str).str.strip().str.upper().unique())
                    non_usd = currs - {"USD", ""}
                    if non_usd:
                        contradictions.append({
                            "document": doc_name,
                            "claim": "All amounts are USD",
                            "reality": f"orders.csv contains non-USD currencies: {list(non_usd)}",
                            "trap_type": "documentation_reality_contradiction"
                        })
        return contradictions

    def _compile_critical_traps(self, report: Dict[str, Any]) -> List[str]:
        traps = []
        orders_p = report["tables"].get("orders", {})

        if orders_p.get("exact_duplicate_rows", 0) > 0:
            traps.append(f"orders.csv has {orders_p['exact_duplicate_rows']} exact duplicate rows requiring deduplication.")

        if orders_p.get("symbol_currency_conflicts"):
            traps.append(f"orders.csv has {len(orders_p['symbol_currency_conflicts'])} rows where the currency symbol contradicts the currency column.")

        ord_date = orders_p.get("columns_detail", {}).get("order_date", {}).get("date_analysis", {})
        if ord_date.get("has_ambiguous_dates"):
            traps.append("orders.csv contains ambiguous date strings (e.g. 05/03/2024) where DD/MM vs MM/DD point to different months.")

        rel = report.get("relational_integrity", {})
        ord_to_cust = rel.get("orders_to_customers", {})
        if ord_to_cust.get("orphan_count", 0) > 0:
            traps.append(f"orders.csv has {ord_to_cust['orphan_count']} orphan orders referencing non-existent customer IDs.")

        fx_info = rel.get("currencies_vs_fx_rates", {})
        if fx_info.get("currencies_missing_fx_rates"):
            traps.append(f"Missing exchange rates in fx_rates.csv for currencies: {fx_info['currencies_missing_fx_rates']}.")

        recon = report.get("reconciliation", {})
        if recon.get("discrepancies_found"):
            for d in recon.get("discrepancies", []):
                traps.append(f"Discrepancy for {d['month']}: monthly_summary.csv reports {d['reported_revenue']} vs orders support {d['orders_supported_revenue']} ({d['discrepancy_pct']}% difference).")

        for doc_c in report.get("documentation_contradictions", []):
            traps.append(f"{doc_c['document']} claims '{doc_c['claim']}', but {doc_c['reality']}.")

        return traps

if __name__ == "__main__":
    from pipeline.loader import DataLoader
    loader = DataLoader()
    tables, docs, _ = loader.load_all()
    profiler = DataProfiler(tables, docs)
    profile = profiler.profile_all()

    print("=" * 60)
    print("PROFILER RUN COMPLETE")
    print("=" * 60)
    print(f"Critical traps detected: {len(profile['critical_traps_detected'])}")
    for t in profile["critical_traps_detected"]:
        print(f" [!] {t}")
    print("=" * 60)
