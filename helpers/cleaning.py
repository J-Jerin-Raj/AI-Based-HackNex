"""
helpers/cleaning.py
Reusable data cleaning utilities designed to be imported by pipeline components
or embedded directly into generated verification scripts.
"""

import re
from datetime import datetime
from typing import Optional, Tuple, Any
import pandas as pd

CURRENCY_SYMBOLS = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "₹": "INR",
    "C$": "CAD",
    "A$": "AUD"
}

def clean_status(val: Any) -> str:
    """Normalize status string by stripping surrounding whitespace and converting to uppercase."""
    if val is None or pd.isna(val):
        return ""
    return str(val).strip().upper()

def extract_currency_symbol(val: Any) -> Optional[str]:
    """Detect and return the currency symbol present in an amount string."""
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    for sym in ["$", "€", "£", "¥", "₹", "C$", "A$"]:
        if sym in s:
            return sym
    return None

def parse_currency_amount(val: Any) -> Optional[float]:
    """
    Parse monetary string into a clean float.
    Handles symbols ($, €, £, etc.), commas, whitespace, and negative values.
    Returns None if value is blank/unparseable.
    """
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    if not s:
        return None
    # Strip known currency symbols
    for sym in ["$", "€", "£", "¥", "₹", "C$", "A$"]:
        s = s.replace(sym, "")
    # Remove commas
    s = s.replace(",", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None

def parse_date_flexible(val: Any, dayfirst: bool = True) -> Optional[datetime]:
    """
    Parse a date string that may be formatted as ISO (YYYY-MM-DD),
    European (DD/MM/YYYY), or US (MM/DD/YYYY).
    """
    if val is None or pd.isna(val):
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, pd.Timestamp):
        return val.to_pydatetime()
    s = str(val).strip()
    if not s:
        return None

    # Handle ISO YYYY-MM-DD (including possible timestamp suffixes)
    iso_match = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if iso_match:
        try:
            return datetime(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
        except ValueError:
            pass
        except ValueError:
            pass

    # Try slash formats
    if re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", s):
        parts = [int(p) for p in s.split("/")]
        try:
            if dayfirst:
                # DD/MM/YYYY
                return datetime(year=parts[2], month=parts[1], day=parts[0])
            else:
                # MM/DD/YYYY
                return datetime(year=parts[2], month=parts[0], day=parts[1])
        except ValueError:
            # Fallback to alternate if day was out of range
            try:
                if dayfirst:
                    return datetime(year=parts[2], month=parts[0], day=parts[1])
                else:
                    return datetime(year=parts[2], month=parts[1], day=parts[0])
            except ValueError:
                pass

    return None
