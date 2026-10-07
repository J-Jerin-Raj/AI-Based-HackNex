"""
pipeline/sources.py
Component: Data Source & Value Location Identifier.
Pinpoints the exact file names, columns, lines, and data locations
that contributed to a calculated result, explanation, or refusal.
"""

import re
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd

def locate_data_sources(
    question: str,
    tables: Dict[str, pd.DataFrame],
    docs: Dict[str, str],
    code: Optional[str] = None,
    verdict: Optional[str] = None,
    verdict_reason: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Identifies the exact files, columns, or line numbers of related/relevant values.
    Returns a list of source descriptor dictionaries.
    """
    sources: List[Dict[str, Any]] = []
    seen_files = set()
    q_lower = question.lower()

    # 1. Check Document Matches (e.g. session_document.txt, data_notes.txt)
    # Extract candidate keywords from the question (words > 3 chars, capitalized words, entities)
    q_words = [w.strip("?,.!'\"()") for w in question.split() if len(w.strip("?,.!'\"()")) >= 3]
    entity_phrases = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", question)

    for doc_name, content in docs.items():
        if not content.strip():
            continue
        lines = content.splitlines()
        matched_lines = []

        for idx, line in enumerate(lines, 1):
            line_str = line.strip()
            if not line_str:
                continue
            line_lower = line_str.lower()

            # Check entity phrase match first
            for phrase in entity_phrases:
                if phrase.lower() in line_lower:
                    matched_lines.append((idx, line_str))
                    break
            else:
                # Check keyword overlap (if 2 or more significant words match)
                word_matches = [w for w in q_words if w.lower() in line_lower and w.lower() not in ["what", "when", "where", "how", "many", "according", "document", "times", "did", "was", "the"]]
                if len(word_matches) >= 2:
                    matched_lines.append((idx, line_str))

        if matched_lines:
            seen_files.add(doc_name)
            # Take the top matched line
            first_idx, first_line = matched_lines[0]
            sources.append({
                "filename": doc_name,
                "type": "document",
                "location": f"Line {first_idx}",
                "snippet": first_line if len(first_line) <= 120 else first_line[:120] + "...",
                "description": f"Direct document statement at Line {first_idx}"
            })

    # 2. Check Code References (tables and columns used in execution)
    if code:
        for tbl_name, df in tables.items():
            tbl_csv = f"{tbl_name}.csv"
            # If table is read or referenced in code
            if tbl_name in code or tbl_csv in code:
                seen_files.add(tbl_csv)
                # Find matching columns referenced in code
                used_cols = [c for c in df.columns if c in code]
                loc_str = f"Columns: {', '.join(used_cols)}" if used_cols else "All table columns"
                
                # Check if specific filter values exist in code
                filters = []
                for val in ["COMPLETED", "PENDING", "CANCELLED", "REFUNDED", "USD", "EUR", "GBP"]:
                    if f"'{val}'" in code or f'"{val}"' in code:
                        filters.append(val)
                filter_desc = f" (filtered on {', '.join(filters)})" if filters else ""

                sources.append({
                    "filename": tbl_csv,
                    "type": "table",
                    "location": loc_str + filter_desc,
                    "columns": used_cols,
                    "rows": len(df),
                    "description": f"Queried {len(df)} records in {tbl_csv}"
                })

    # 3. If Rule-based check triggered without code (e.g. Contradictions or Missing Data)
    if not sources and verdict_reason:
        reason_lower = verdict_reason.lower()
        if "orders" in reason_lower and "monthly_summary" in reason_lower:
            sources.append({
                "filename": "orders.csv",
                "type": "table",
                "location": "orders.csv: column 'order_date'",
                "description": "Source transactional orders for queried timeframe"
            })
            sources.append({
                "filename": "monthly_summary.csv",
                "type": "table",
                "location": "monthly_summary.csv: column 'month'",
                "description": "Contradictory monthly reported revenue summary"
            })
        elif "fx_rates" in reason_lower:
            sources.append({
                "filename": "orders.csv",
                "type": "table",
                "location": "Column 'currency'",
                "description": "Foreign currency orders"
            })
            sources.append({
                "filename": "fx_rates.csv",
                "type": "table",
                "location": "Conversion table",
                "description": "Foreign exchange conversion rates"
            })
        elif "dataset consists of commercial" in reason_lower or "does not exist" in reason_lower:
            # Out of scope refusal
            sources.append({
                "filename": "Project Datasets",
                "type": "catalog",
                "location": "Scanned orders.csv, customers.csv, data_notes.txt, session_document.txt",
                "description": "Requested entity not found in any project dataset or document"
            })

    # 4. Fallback if still empty: identify tables with highest column keyword overlap
    if not sources:
        for tbl_name, df in tables.items():
            if any(col.lower() in q_lower for col in df.columns):
                matched_cols = [c for c in df.columns if c.lower() in q_lower]
                sources.append({
                    "filename": f"{tbl_name}.csv",
                    "type": "table",
                    "location": f"Columns: {', '.join(matched_cols)}",
                    "description": f"Potential matching schema in {tbl_name}.csv"
                })

    return sources
