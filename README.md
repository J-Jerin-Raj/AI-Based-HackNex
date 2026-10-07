# Verifiable Quantitative Data Analysis Agent

An autonomous, audit-grade quantitative data analysis system designed to reliably answer business questions on dirty enterprise tabular data with planted traps—without performing arithmetic in LLM prose.

---

## 🎯 Problem Statement

When querying datasets with generative AI:
1. **LLMs Hallucinate Math:** Token predictors cannot reliably calculate sums, averages, or joins over hundreds of rows in text.
2. **Blind Compliance on Dirty Data:** Enterprise data is littered with duplicate transactions, whitespace/casing anomalies, mixed currency symbols, ambiguous dates (`DD/MM/YYYY` vs `MM/DD/YYYY`), and cross-table accounting contradictions. Standard LLMs hallucinate numbers rather than refusing or flagging traps.
3. **Zero Auditability:** Standard chatbot outputs cannot be audited by finance or compliance teams.

### Core Guarantee
**Every number reported is the executed, sandboxed output of a Python/Pandas script.** Every answer is accompanied by a tamper-evident cryptographic provenance manifest detailing SHA-256 data hashes, generated script code, execution time, and declared assumptions.

---

## 🏗️ Architecture & Pipeline

```
                    User Question ("What is the total revenue?")
                                      │
                                      ▼
               ┌──────────────────────────────────────────────┐
               │  Component 5: Deterministic Rules Gatekeeper │
               │  (Instant 0.01s check: Refusals / Traps)     │
               └──────────────┬───────────────────────────────┘
                              │
               Is Question Answerable?
              ┌───────────────┴───────────────┐
              │ NO                            │ YES
              ▼                               ▼
     Immediate Refusal             ┌─────────────────────────────────────┐
  (0.01s, Zero LLM Call)           │ Component 8: Code Generator (LLM)   │
  * Cannot Determine               │ (Ollama / Groq / OpenAI)            │
  * Contradiction Flagged          └──────────────────┬──────────────────┘
  * Ambiguity Refusal                                 │
                                                      ▼
                                   ┌─────────────────────────────────────┐
                                   │ Component 4: Subprocess Sandbox     │
                                   │ (Isolated execution, timeout, stdio)│
                                   └──────────────────┬──────────────────┘
                                                      │
                                                      ▼
                                   ┌─────────────────────────────────────┐
                                   │ Component 10: Auto-Repair Loop      │
                                   │ (Traceback fed back if error)       │
                                   └──────────────────┬──────────────────┘
                                                      │
                                                      ▼
                                   ┌─────────────────────────────────────┐
                                   │ Micro-Prompt Explainer              │
                                   │ (Formats prose without doing math)  │
                                   └──────────────────┬──────────────────┘
                                                      │
                                                      ▼
                                   ┌─────────────────────────────────────┐
                                   │ Component 6: Cryptographic Manifest │
                                   │ (SHA-256 code & data hashes)        │
                                   └─────────────────────────────────────┘
```

### The 10 Core Components
1. **DataLoader (`pipeline/loader.py`):** Ingests CSVs and metadata notes; computes SHA-256 integrity hashes for all files.
2. **DataProfiler (`pipeline/profiler.py`):** Automatically profiles schema anomalies, duplicate IDs, orphan foreign keys, date formats, and cross-table reconciliation gaps.
3. **Rules Gatekeeper (`pipeline/rules.py`):** Deterministic refusal engine running in <0.05ms to immediately reject unanswerable queries (e.g. missing CSAT, profit margin, product category, unmapped FX rates).
4. **Sandbox Executor (`pipeline/sandbox.py`):** Executes generated Python code in an isolated subprocess with strict timeouts and stdio capture.
5. **Code Generator (`pipeline/codegen.py`):** Generates concise, self-contained Pandas code utilizing verified cleaning utilities.
6. **Self-Repair Loop (`pipeline/codegen.py`):** Feeds tracebacks and failed scripts back into the model to iteratively fix syntax or data errors.
7. **Consensus Checker (`pipeline/consensus.py`):** Runs multiple generation runs across temperatures to ensure numerical consensus.
8. **Micro-Prompt Explainer (`pipeline/explain.py`):** Summarizes verified numeric results into executive prose without altering or computing numbers.
9. **Manifest Builder (`pipeline/manifest.py`):** Emits cryptographic JSON manifests capturing data lineage, code hashes, and runtime environment.
10. **Evaluation Harness (`tests/evaluate.py`):** Comprehensive automated benchmark tester.

---

## 📊 Benchmark Dataset & Planted Traps

The test suite in `data/` includes 5 tables and 1 metadata file containing 12 deliberately planted traps:
* **`orders.csv`**: Duplicate primary keys, whitespace/casing variations, null amounts, ambiguous dates (`05/03/2024`), conflicting currency symbols (`$350` in EUR row, `€450` in USD row), orphan customer foreign keys (`CUST-999`), and unlisted currencies (`GBP`).
* **`customers.csv`**: Inconsistent capitalization and whitespace across records.
* **`refunds.csv`**: Duplicate refund records, orphan refunds referencing nonexistent orders, and missing currency denomination.
* **`fx_rates.csv`**: Lacks an exchange rate for GBP.
* **`monthly_summary.csv`**: May 2024 reports \$4,600, whereas raw completed orders sum to \$4,000 (15% discrepancy).
* **`data_notes.txt`**: Claims "all amounts are USD", contradicting individual order currency fields.

### Benchmark Results
Running `python run.py --evaluate` on the 18-question ground truth benchmark:
* **Verdict Accuracy:** 18 / 18 (100.0%)
* **Refusal Correctness:** 8 / 8 (100.0%)
* **Refusal Latency:** < 0.05 milliseconds

---

## 🚀 Quickstart Guide

### 1. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/J-Jerin-Raj/AI-Based-HackNex.git
cd AI-Based-HackNex
pip install -r requirements.txt
```

### 2. Generate Benchmark Dataset
```bash
python tests/make_test_data.py
```

### 3. Ask Questions
```bash
# Direct Question
python ask.py "What is the total revenue from completed USD orders?"

# Missing metric trap (Instant refusal)
python ask.py "What is our customer satisfaction rating for 2024?"

# Planted contradiction trap (Instant refusal)
python ask.py "What was the total revenue for May 2024?"

# Interactive REPL mode
python ask.py
```

### 4. Run Full Evaluation
```bash
python run.py --evaluate
```

---

## ⚙️ Model Provider Configuration

The agent supports local offline models as well as hosted cloud APIs via standard OpenAI-compatible endpoints:

### Local (Ollama - Default)
Works out of the box with `qwen2.5-coder:1.5b` or `qwen3:4b`:
```bash
python ask.py "What is the total revenue?"
```

### Hosted High-Speed Providers (e.g. Free Groq API)
```bash
export OPENAI_API_KEY="gsk_..."
export OPENAI_BASE_URL="https://api.groq.com/openai/v1"
python ask.py "What is the total revenue?" --provider openai --model llama-3.3-70b-versatile
```
*(On Windows PowerShell, use `$env:OPENAI_API_KEY="gsk_..."`)*

---

## 📜 Audit Manifest Example
Every query generates a cryptographic manifest stored in `answers/`:
```json
{
  "question": "What is the total revenue from completed USD orders?",
  "timestamp": "2026-10-07T05:18:43.123456+00:00",
  "environment": {
    "python_version": "3.13.7",
    "pandas_version": "2.3.3",
    "platform": "Windows-11"
  },
  "input_file_hashes": {
    "orders.csv": "2d9c1dc4a587884dda8ff8316d1695f486000aec18cd57bea67df8c5254d7ce5"
  },
  "verdict": "answerable",
  "code": "import pandas as pd\n...",
  "code_hash": "a4d3f5e9...",
  "output_value": 12633.21
}
```
