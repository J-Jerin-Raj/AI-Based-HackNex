"""
ask.py
Convenient interactive question runner for the quantitative data analysis agent.

Usage:
  python ask.py                               # Launches interactive prompt
  python ask.py "What is the total revenue?"  # Runs a single question
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run import run_interactive_mode, process_question_pipeline

def main():
    args = sys.argv[1:]
    if not args:
        # Launch interactive REPL mode
        run_interactive_mode()
    else:
        question = " ".join(args)
        process_question_pipeline(question=question)

if __name__ == "__main__":
    main()
