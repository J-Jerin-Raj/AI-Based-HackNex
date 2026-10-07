"""
pipeline/loader.py
Component 1: Loader and Hasher.
Reads every CSV/Excel/doc in data/, computes SHA-256 per file,
and loads tables into pandas DataFrames.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Tuple, Optional
import pandas as pd

def compute_file_sha256(filepath: Path) -> str:
    """Compute the SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

class DataLoader:
    """
    Scans a directory, computes cryptographic hashes, and loads tables into pandas.
    """
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            self.data_dir = Path(__file__).resolve().parent.parent / "data"
        else:
            self.data_dir = Path(data_dir)

    def load_all(self) -> Tuple[Dict[str, pd.DataFrame], Dict[str, str], Dict[str, str]]:
        """
        Loads all datasets from data_dir.
        Returns:
            tables: dict mapping table name (e.g. 'orders') to DataFrame
            docs: dict mapping document name (e.g. 'data_notes.txt') to string content
            hashes: dict mapping filename to SHA-256 hex digest
        """
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")

        tables: Dict[str, pd.DataFrame] = {}
        docs: Dict[str, str] = {}
        hashes: Dict[str, str] = {}

        for item in sorted(self.data_dir.iterdir()):
            if item.is_file():
                filename = item.name
                file_hash = compute_file_sha256(item)
                hashes[filename] = file_hash

                suffix = item.suffix.lower()
                stem = item.stem

                # Handle CSV files
                if suffix == ".csv":
                    # Keep raw empty strings as empty strings rather than auto-converting to NaN
                    # to enable explicit dirty data profiling.
                    df = pd.read_csv(item, keep_default_na=False, dtype=str)
                    tables[stem] = df

                # Handle Excel files if present
                elif suffix in [".xls", ".xlsx"]:
                    df = pd.read_excel(item, dtype=str)
                    tables[stem] = df

                # Handle Text / Markdown / Docs
                elif suffix in [".txt", ".md", ".doc", ".rst"]:
                    with open(item, "r", encoding="utf-8", errors="replace") as f:
                        docs[filename] = f.read()

                # Handle JSON metadata files
                elif suffix == ".json" and filename != "data_hashes.json":
                    with open(item, "r", encoding="utf-8") as f:
                        docs[filename] = f.read()

        return tables, docs, hashes

    def verify_against_manifest(self, manifest_hashes: Dict[str, str]) -> Dict[str, bool]:
        """
        Verifies that current files match expected SHA-256 hashes.
        Returns a dict of filename -> bool (True if matched).
        """
        results = {}
        for filename, expected_hash in manifest_hashes.items():
            path = self.data_dir / filename
            if not path.exists():
                results[filename] = False
            else:
                current_hash = compute_file_sha256(path)
                results[filename] = (current_hash == expected_hash)
        return results

if __name__ == "__main__":
    loader = DataLoader()
    tables, docs, hashes = loader.load_all()
    print(f"Loaded {len(tables)} tables: {list(tables.keys())}")
    print(f"Loaded {len(docs)} documents: {list(docs.keys())}")
    print(f"Computed {len(hashes)} file hashes.")
