<<<<<<< Updated upstream
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
=======
# AI-Based-HackNex: Autonomous Quantitative Data Analysis Agent

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Audit: Cryptographic Manifests](https://img.shields.io/badge/audit-SHA--256%20verified-green.svg)](#verifiable-run-manifests)

**AI-Based-HackNex** is a high-reliability, audit-ready AI agent designed for complex quantitative data analytics. Unlike standard conversational AI tools that hallucinate arithmetic and produce unreproducible answers, this agent couples **deterministic rule-based triage**, **profiling of data traps**, **sandboxed Python code execution**, **multi-candidate consensus validation**, and **cryptographic run manifests** to guarantee 100% auditability and mathematical correctness.

---

## Table of Contents

- [System Architecture](#system-architecture)
- [Key Features](#key-features)
- [Repository Structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Quickstart Guide](#quickstart-guide)
  - [1. Clone the Repository](#1-clone-the-repository)
  - [2. Set Up Python Virtual Environment](#2-set-up-python-virtual-environment)
  - [3. Install Dependencies](#3-install-dependencies)
  - [4. Configure LLM Provider](#4-configure-llm-provider)
- [Usage & Execution Modes](#usage--execution-modes)
  - [Interactive Shell (REPL)](#a-interactive-prompt-shell-recommended)
  - [Single Question via CLI](#b-single-question-cli)
  - [Batch Questions from File](#c-batch-processing)
  - [Zero-LLM Fast Mode (Deterministic Rules Only)](#d-zero-llm-fast-mode-deterministic-rules-only)
  - [Data Profiler Mode](#e-data-profiler-mode)
- [Testing & Benchmark Evaluation](#testing--benchmark-evaluation)
- [Understanding Verdicts & Manifests](#understanding-verdicts--manifests)
- [Configuration Reference](#configuration-reference)
- [Troubleshooting & FAQ](#troubleshooting--faq)

---

## System Architecture

```
                                  [ User Query ]
                                         │
                                         ▼
                             ┌───────────────────────┐
                             │ DataLoader & Hasher   │ ── Computes SHA-256 for all inputs
                             └───────────┬───────────┘
                                         │
                                         ▼
                             ┌───────────────────────┐
                             │    Data Profiler      │ ── Scans for dirty data, currency mismatches,
                             └───────────┬───────────┘    orphaned FKs, summary contradictions
                                         │
                                         ▼
                             ┌───────────────────────┐
                             │ Deterministic Rules   │ ── Fast (0.01s) triage for missing data,
                             └───────────┬───────────┘    out-of-range dates, or contradictions
                                   │           │
                     Definitive?  YES          NO (Answerable query)
                                   │           │
                                   ▼           ▼
                      ┌──────────────────┐  ┌───────────────────────┐
                      │ Immediate Result │  │ LLM Code Generator    │
                      └────────┬─────────┘  └───────────┬───────────┘
                               │                        │
                               │                        ▼
                               │            ┌───────────────────────┐
                               │            │  Subprocess Sandbox   │ ── Auto-Repair on failure
                               │            └───────────┬───────────┘
                               │                        │
                               │                        ▼
                               │            ┌───────────────────────┐
                               │            │   Consensus Checker   │ ── Multi-candidate tolerance check
                               │            └───────────┬───────────┘
                               │                        │
                               │                        ▼
                               │            ┌───────────────────────┐
                               │            │   Micro-Explainer     │ ── 1-2 sentence executive summary
                               │            └───────────┬───────────┘
                               │                        │
                               ▼                        ▼
                      ┌─────────────────────────────────────────────┐
                      │        Cryptographic Run Manifest           │
                      │  (SHA-256 Hashes, Executed Code, Verdicts)  │
                      └─────────────────────────────────────────────┘
```

---

## Key Features

1. **Subprocess Python Sandbox (Zero Arithmetic Hallucination)**
   - The LLM never computes numbers in its token space. Instead, it generates Pandas verification scripts executed inside an isolated, resource-guarded Python subprocess.
2. **Deterministic Hard-Rule Refusal Engine (<0.01s)**
   - Instant detection of missing dimensions (e.g. CSAT, COGS, profit margin, product categories), out-of-range dates (e.g., 2025+), unpegged currencies, or causal queries ("Why did sales drop?").
3. **Dirty Data & Trap Profiling**
   - Automatically detects whitespace and casing inconsistencies (`" COMPLETED "`), conflicting currency symbols (e.g. `$` in amount vs `EUR` in currency column), date format ambiguities (`DD/MM/YYYY` vs `MM/DD/YYYY`), orphaned customer/order IDs, and summary discrepancies.
4. **Self-Correction & Consensus**
   - If a script encounters a runtime error, the auto-repair loop provides stderr feedback to the LLM to patch the code.
   - Supports multi-candidate execution with numeric tolerance comparison (\(\pm 0.01\)) to verify consensus.
5. **Verifiable Run Manifests**
   - Every answered question writes a cryptographically linked JSON manifest to `answers/` containing input data SHA-256 hashes, exact Python source code, code SHA-256 hash, execution results, and declared assumptions.
6. **Provider Agnostic**
   - Works completely offline and privately with local LLMs via **Ollama** (`qwen3:4b`, `qwen2.5-coder:7b`, `llama3.2`), or hosted OpenAI-compatible APIs (**OpenAI**, **Groq**, **DeepSeek**, **OpenRouter**).

---

## Repository Structure

```
AI-Based-HackNex/
├── answers/                     # Cryptographic JSON run manifests for auditability
├── data/                        # Datasets, reference notes, and cryptographic hashes
│   ├── customers.csv            # Customer master records
│   ├── orders.csv               # Multi-currency transactional order records
│   ├── refunds.csv              # Refund adjustment records
│   ├── fx_rates.csv             # Foreign exchange conversion tables
│   ├── monthly_summary.csv      # Reported aggregate figures (contains discrepancies)
│   ├── data_notes.txt           # Schema specifications and operational rules
│   └── data_hashes.json         # SHA-256 hash baseline for input files
├── helpers/
│   ├── __init__.py
│   └── cleaning.py              # Robust currency, status, and date cleaning utilities
├── pipeline/
│   ├── __init__.py
│   ├── codegen.py               # Pandas code generation and auto-repair loop
│   ├── consensus.py             # Numerical equivalence & multi-run consensus engine
│   ├── explain.py               # Micro-prompt executive summary synthesizer
│   ├── gate.py                  # LLM answerability and assumption gate
│   ├── llm_client.py            # Unified client (Ollama & OpenAI-compatible APIs)
│   ├── loader.py                # File hashing and Pandas loading
│   ├── manifest.py              # Cryptographic run manifest builder
│   ├── profiler.py              # Comprehensive dirty data profiler
│   ├── rules.py                 # Deterministic fast-refusal rules engine
│   └── sandbox.py               # Subprocess code sandbox runner
├── prompts/                     # Prompt templates
│   ├── codegen_prompt.txt
│   ├── explain_prompt.txt
│   ├── gate_prompt.txt
│   └── repair_prompt.txt
├── tests/
│   ├── evaluate.py              # 18-question benchmark evaluation harness
│   ├── make_test_data.py        # Synthetic test dataset generator with intentional traps
│   ├── questions.json           # Benchmark question catalog
│   ├── questions_answer_key.json# Ground truth answers, assumptions, and verdicts
│   └── test_make_test_data.py   # Dataset validation and integrity unit tests
├── .env.example                 # Environment variables template
├── .gitignore                   # Git ignore file
├── ask.py                       # Lightweight interactive runner
├── make_test_data.py            # Convenience script to generate test data
├── requirements.txt             # Project Python dependencies
├── run.py                       # Main pipeline entry point
└── sample_questions.txt         # Example queries for batch testing
```

---

## Prerequisites

- **Python**: Version `3.10` or higher installed.
- **Operating System**: Windows, macOS, or Linux.
- **LLM Engine** *(Choose one)*:
  - **Local (Free, Offline, Recommended)**: [Ollama](https://ollama.com) installed and running.
  - **Cloud/Hosted**: API key for OpenAI, Groq, DeepSeek, or any OpenAI-compatible provider.

---

## Quickstart Guide

### 1. Clone the Repository

```bash
git clone https://github.com/TANIA-SANGA/AI-Based-HackNex.git
cd AI-Based-HackNex
```

### 2. Set Up Python Virtual Environment

It is strongly recommended to use a virtual environment.

#### On Windows (PowerShell):
```powershell
# Using the py launcher or python:
py -m venv venv

# If PowerShell blocks script execution, run:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned

# Activate virtual environment:
.\venv\Scripts\Activate.ps1
```

#### On Windows (Command Prompt - cmd):
```cmd
py -m venv venv
venv\Scripts\activate.bat
```

#### On macOS / Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

---

### 3. Install Dependencies

Install the verified project dependencies:

```bash
pip install -r requirements.txt
```

---

### 4. Configure LLM Provider

You can run the agent locally with Ollama (no API key required) or connect to hosted cloud models.

#### Option A: Local Ollama (Recommended: Free & Offline)
1. Install Ollama from [ollama.com](https://ollama.com).
2. Start the Ollama service:
   ```bash
   ollama serve
   ```
3. Pull a supported model (e.g., `qwen2.5-coder:7b` or `qwen3:4b`):
   ```bash
   ollama pull qwen2.5-coder:7b
   ```
4. By default, the pipeline connects to `http://localhost:11434`.

#### Option B: Hosted Cloud Models (OpenAI / Groq / DeepSeek)
Copy `.env.example` to `.env` or set your environment variables:

**PowerShell (Windows):**
```powershell
$env:LLM_PROVIDER="openai"
$env:OPENAI_API_KEY="sk-your-openai-api-key"
$env:OPENAI_MODEL="gpt-4o-mini"
```

**Bash / Zsh (macOS / Linux):**
```bash
export LLM_PROVIDER="openai"
export OPENAI_API_KEY="sk-your-openai-api-key"
export OPENAI_MODEL="gpt-4o-mini"
```

**Groq Example:**
```powershell
$env:LLM_PROVIDER="openai"
$env:OPENAI_API_KEY="gsk_your_groq_api_key"
$env:OPENAI_MODEL="llama-3.3-70b-versatile"
$env:OPENAI_BASE_URL="https://api.groq.com/openai/v1"
```

---

## Usage & Execution Modes

### A. Interactive Prompt Shell (Recommended)

Start an interactive prompt session to query datasets in real-time:

```bash
python run.py
# or
python ask.py
```

Inside the shell, you can enter any question, or use special commands:
- `:traps` - Inspect all anomalies, duplicate rates, and contradictions detected across loaded tables.
- `:evaluate` - Run the automated 18-question benchmark test.
- `:model <name>` - Switch the active model on the fly (e.g. `:model qwen2.5-coder:7b`).
- `:provider <name>` - Switch provider (e.g. `:provider openai`).
- `:exit` - Exit the shell.

---

### B. Single Question CLI

Pass a question directly on the command line:

```bash
# Query answerable transaction
python run.py "What is the total revenue from completed USD orders?"

# Query unanswerable metric (triggers instant deterministic refusal)
python run.py "What is our customer satisfaction (CSAT) rating?"

# Query cross-table contradiction
python run.py "What was the total revenue for May 2024?"
```

You can pass CLI arguments to override model or provider settings:
```bash
python run.py "What is total revenue from completed USD orders?" --provider openai --model gpt-4o-mini --api-key sk-...
```

---

### C. Batch Processing

Process an entire batch file of questions (plain text or JSON format):

```bash
python run.py --file sample_questions.txt
```

Each question will be executed, printed with formatted output, and saved as a manifest in `answers/`.

---

### D. Zero-LLM Fast Mode (Deterministic Rules Only)

If you don't have an LLM installed or want to verify rule-based refusals and contradiction detection in `< 0.01s`:

```bash
python run.py --no-llm "Why did sales drop between March and April 2024?"
python run.py --no-llm "What is the profit margin for completed orders?"
```

---

### E. Data Profiler Mode

Inspect data irregularities, missing FX conversions, date ambiguities, and summary reconciliations without answering questions:

```bash
python run.py --profile-only
```

Outputs a detailed JSON report covering all loaded tables, blank rates, duplicate counts, and cross-table discrepancy percentages.

---

## Testing & Benchmark Evaluation

### 1. Run the 18-Question Benchmark Evaluation

The pipeline includes an automated test harness evaluating 18 challenging questions covering answerable questions, assumption-requiring queries, contradictions, and refusals:

```bash
python run.py --evaluate
# or
python tests/evaluate.py
```

### 2. Verify Synthetic Data Generation & Integrity

Validate that all planted data traps, hash baselines, and test files are intact:

```bash
python tests/test_make_test_data.py
```

### 3. Regenerate Synthetic Test Data

To reset or regenerate the test CSV files in `data/`:

```bash
python make_test_data.py
>>>>>>> Stashed changes
```

---

<<<<<<< Updated upstream
## ⚙️ Model Provider Configuration

The agent supports Google Gemini by default, as well as local offline Ollama and OpenAI-compatible hosted endpoints:

### 1. Google Gemini (Default)
Add your Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey) into your `.env` file:
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-2.5-flash
```
Then ask questions normally:
```bash
python ask.py "What is the total revenue from completed USD orders?"
```

### 2. Local Offline Fallback (Ollama)
To run completely offline without an internet connection or API key:
```bash
python ask.py "What is the total revenue?" --provider ollama
```

### 3. Other Hosted Providers (Groq / OpenAI / DeepSeek)
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
=======
## Understanding Verdicts & Manifests

### Verdict Classifications

The agent returns one of the following structured verdicts for every question:

| Verdict | Meaning | Action Taken |
| :--- | :--- | :--- |
| `ANSWERABLE` | Query is mathematically unambiguous and supported by data. | Generates and executes verified Pandas code in sandbox. |
| `ANSWERABLE_WITH_ASSUMPTION` | Answerable only under stated assumptions (e.g. currency precedence, date format). | Returns result and explicitly lists declared assumptions. |
| `CANNOT_DETERMINE` | Required column/metric is missing (e.g. CSAT, COGS, causal "why", unpegged currency). | Safely refuses to answer with detailed explanation. |
| `CONTRADICTION` | Two source files contradict one another (e.g. orders vs monthly summary). | Flags conflicting sources and computes discrepancy percentage. |
| `AMBIGUOUS` | Query is underspecified (e.g. no currency, timeframe, or refund policy declared). | Clarifies missing parameters. |

---

### Verifiable Run Manifests

Every answer produces a tamper-evident audit record stored under `answers/manifest_<QUESTION_ID>.json`:

```json
{
  "question_id": "CLI_Q",
  "question": "What is the total revenue from completed USD orders?",
  "timestamp": "2026-10-07T04:54:08.206823+00:00",
>>>>>>> Stashed changes
  "environment": {
    "python_version": "3.13.7",
    "pandas_version": "2.3.3",
    "platform": "Windows-11"
  },
  "input_file_hashes": {
<<<<<<< Updated upstream
    "orders.csv": "2d9c1dc4a587884dda8ff8316d1695f486000aec18cd57bea67df8c5254d7ce5"
  },
  "verdict": "answerable",
  "code": "import pandas as pd\n...",
  "code_hash": "a4d3f5e9...",
  "output_value": 12633.21
}
```
=======
    "orders.csv": "2d9c1dc4a587884dda8ff8316d1695f486000aec18cd57bea67df8c5254d7ce5",
    "customers.csv": "b6a518f508d869546fb9d5e0710b0ecbef72c44bdd290cea4d4abc7313b735fa"
  },
  "verdict": "answerable",
  "verdict_reason": "Executed verified Pandas script in sandbox",
  "assumptions": ["Deduplicated records and parsed currency formatting"],
  "code": "...",
  "code_hash": "a4f8c9...",
  "output_value": 12313.21,
  "output_hash": "e3b0c4...",
  "consensus_details": {
    "status": "agree",
    "runs": 1
  }
}
```

---

## Configuration Reference

You can configure the pipeline via command line arguments or environment variables:

| Argument | Environment Variable | Default | Description |
| :--- | :--- | :--- | :--- |
| `--provider` | `LLM_PROVIDER` | `ollama` | Provider: `ollama`, `openai`, `groq`, `deepseek`, `openrouter` |
| `--model` | `LLM_MODEL` / `OLLAMA_MODEL` | `qwen3:4b` | Model identifier |
| `--api-key` | `OPENAI_API_KEY` | None | API key for hosted providers |
| `--base-url` | `OPENAI_BASE_URL` | None | Custom OpenAI-compatible endpoint URL |
| `--candidates`| None | `1` | Number of candidate code runs for consensus checking |
| `--no-llm` | None | `False` | Run deterministic rules only (0.01s triage) |
| `--profile-only` | None | `False` | Dump dataset profiling report and exit |
| `--evaluate` | None | `False` | Run full 18-question benchmark evaluation harness |

---

## Troubleshooting & FAQ

#### 1. "Python was not found" on Windows
- Windows sometimes defaults to an App Execution Alias. Use the Python Launcher:
  ```powershell
  py -m venv venv
  py run.py
  ```
- Alternatively, disable the Microsoft Store alias via: *Windows Settings > Apps > Advanced app settings > App execution aliases* (turn off `python.exe` and `python3.exe`).

#### 2. PowerShell script execution error (`cannot be loaded because running scripts is disabled`)
- Temporarily enable script execution for your session:
  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
  .\venv\Scripts\Activate.ps1
  ```

#### 3. "Failed to connect to Ollama at http://localhost:11434"
- Ensure the Ollama daemon is running:
  ```bash
  ollama serve
  ```
- Check available local models:
  ```bash
  ollama list
  ```
- If you don't have Ollama, use `--provider openai --api-key sk-...` or test with `--no-llm`.

#### 4. Need to re-verify or regenerate dataset files?
- Run:
  ```bash
  python make_test_data.py
  ```
  This creates clean baseline tables and computes fresh SHA-256 hashes in `data/data_hashes.json`.

---

## License

This project is licensed under the MIT License.
>>>>>>> Stashed changes
