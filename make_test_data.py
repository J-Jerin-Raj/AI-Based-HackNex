"""
Convenience entry point to run make_test_data.py from the project root.
"""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tests.make_test_data import generate_dataset

if __name__ == "__main__":
    generate_dataset()
