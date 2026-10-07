# Verifiable Quantitative Data Analysis Agent

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Audit: SHA-256 Manifests](https://img.shields.io/badge/audit-SHA--256%20verified-green.svg)](#audit-manifests)

An audit-grade agent that answers business questions on dirty enterprise tables **without ever doing arithmetic in LLM prose**. Every number is the output of a Pandas script executed in an isolated sandbox, and every answer ships with a tamper-evident provenance manifest.

## Table of Contents

- [Why this exists](#why-this-exists)
- [Architecture](#architecture)
- [Repository structure](#repository-structure)
- [Quickstart](#quickstart)
- [LLM providers](#llm-providers)
- [Usage modes](#usage-modes)
- [Benchmark](#benchmark)
- [Verdicts](#verdicts)
- [Audit manifests](#audit-manifests)
- [Configuration reference](#configuration-reference)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Why this exists

1. **LLMs hallucinate math.** Token predictors cannot reliably sum, average, or join hundreds of rows in text.
2. **LLMs comply blindly with dirty data.** Duplicate transactions, whitespace/casing drift, mixed currency symbols, ambiguous dates (`DD/MM/YYYY` vs `MM/DD/YYYY`), and cross-table contradictions produce confident but wrong answers instead of refusals.
3. **Chat answers are unauditable.** Finance and compliance teams cannot see which rows were used or how gaps were handled.

**Core guarantee:** every reported number is the executed, sandboxed output of a Python/Pandas script, recorded with SHA-256 hashes of the inputs and the code.

---

## Architecture

```
                       User question
                             │
                             ▼
            ┌──────────────────────────────────┐
            │ DataLoader + Profiler            │  SHA-256 all inputs, scan for traps
            └────────────────┬─────────────────┘
                             ▼
            ┌──────────────────────────────────┐
            │ Deterministic Rules Gatekeeper   │  < 0.05 ms, zero LLM calls
            └───────┬──────────────────┬───────┘
          definitive│                  │answerable
                    ▼                  ▼
         Immediate refusal /   ┌──────────────────────┐
         contradiction flag    │ Code Generator (LLM) │
                               └──────────┬───────────┘
                                          ▼
                               ┌──────────────────────┐
                               │ Subprocess Sandbox   │◄── Auto-repair loop
                               └──────────┬───────────┘     (traceback fed back)
                                          ▼
                               ┌──────────────────────┐
                               │ Consensus Checker    │  multi-candidate agreement
                               └──────────┬───────────┘
                                          ▼
                               ┌──────────────────────┐
                               │ Micro-Explainer      │  prose only, never computes
                               └──────────┬───────────┘
                                          ▼
            ┌──────────────────────────────────┐
            │ Manifest Builder (SHA-256 audit) │
            └──────────────────────────────────┘
```

| Module | Role |
| :--- | :--- |
| `pipeline/loader.py` | Loads CSVs and notes, computes SHA-256 hashes of every input |
| `pipeline/profiler.py` | Detects null amounts, duplicate keys, orphan FKs, date ambiguity, missing FX rates, cross-table discrepancies |
| `pipeline/rules.py` | Deterministic refusal engine for missing metrics (CSAT, margin, category), unmapped FX, known contradictions, out-of-range dates, causal "why" questions |
| `pipeline/gate.py` | LLM answerability and assumption gate |
| `pipeline/codegen.py` | Generates concise Pandas code using verified helpers; runs the self-repair loop |
| `pipeline/sandbox.py` | Subprocess execution with timeouts and stdout/stderr capture |
| `pipeline/consensus.py` | Compares multiple runs with numeric tolerance (±0.01) |
| `pipeline/explain.py` | Turns the verified number into 1-2 sentences of prose |
| `pipeline/manifest.py` | Emits the JSON audit manifest |
| `pipeline/llm_client.py` | Unified client for Gemini, Ollama, and OpenAI-compatible APIs |
| `tests/evaluate.py` | 18-question benchmark harness |

---

## Repository structure

```
├── answers/            # Run manifests and generated solution scripts
├── data/               # orders, customers, refunds, fx_rates, monthly_summary,
│                       #   data_notes.txt, data_hashes.json
├── helpers/cleaning.py # Currency, status, and date cleaning utilities
├── pipeline/           # Modules listed above
├── prompts/            # codegen, explain, gate, repair prompt templates
├── tests/              # evaluate.py, make_test_data.py, questions.json,
│                       #   questions_answer_key.json, test_make_test_data.py
├── .env.example        # Environment variable template
├── ask.py              # Lightweight runner
├── run.py              # Main entry point
├── make_test_data.py   # Convenience wrapper for dataset generation
├── sample_questions.txt
└── requirements.txt
```

---

## Quickstart

**Prerequisites:** Python 3.10+ and either a Gemini/OpenAI-compatible API key or a local [Ollama](https://ollama.com) install.

```bash
git clone https://github.com/J-Jerin-Raj/AI-Based-HackNex.git
cd AI-Based-HackNex

python -m venv venv
source venv/bin/activate          # Windows: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt

cp .env.example .env              # then add your API key
python make_test_data.py          # generate the benchmark dataset
python ask.py "What is the total revenue from completed USD orders?"
```

If PowerShell blocks activation: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`.

---

## LLM providers

The default provider is **Google Gemini** (`gemini-2.5-flash`). Set it in `.env`; never commit this file.

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-2.5-flash
```

Get a key at [Google AI Studio](https://aistudio.google.com/apikey).

**Local, offline (Ollama):**

```bash
ollama serve
ollama pull qwen2.5-coder:7b
python run.py "What is the total revenue?" --provider ollama --model qwen2.5-coder:7b
```

**Hosted OpenAI-compatible (OpenAI, Groq, DeepSeek, OpenRouter):**

```bash
export OPENAI_API_KEY="your-key-here"
export OPENAI_BASE_URL="https://api.groq.com/openai/v1"
python run.py "What is the total revenue?" --provider openai --model llama-3.3-70b-versatile
```

PowerShell: `$env:OPENAI_API_KEY="your-key-here"`.

---

## Usage modes

| Mode | Command |
| :--- | :--- |
| Interactive shell | `python run.py` or `python ask.py` |
| Single question | `python run.py "What was the total revenue for May 2024?"` |
| Show executed code | `python ask.py "..." --code` |
| Batch file (txt or JSON) | `python run.py --file sample_questions.txt` |
| Rules only, no LLM | `python run.py --no-llm "What is the profit margin?"` |
| Data profile report | `python run.py --profile-only` |
| Full benchmark | `python run.py --evaluate` |

Interactive shell commands: `:traps`, `:evaluate`, `:model <name>`, `:provider <name>`, `:exit`.

---

## Benchmark

The dataset in `data/` has 5 tables and 1 notes file with 12 planted traps:

| File | Planted traps |
| :--- | :--- |
| `orders.csv` | Duplicate keys, whitespace/casing in status, null amounts, ambiguous dates (`05/03/2024`), conflicting symbols (`$350` in a EUR row, `€450` in a USD row), orphan customer `CUST-999`, unlisted currency GBP |
| `customers.csv` | Duplicates with inconsistent capitalization and whitespace |
| `refunds.csv` | Duplicate refund IDs, refunds for nonexistent orders, missing currency column |
| `fx_rates.csv` | No GBP rate |
| `monthly_summary.csv` | May 2024 reports $4,600 vs $4,000 from raw completed orders (15% gap) |
| `data_notes.txt` | Claims "all amounts are USD", contradicting row-level currencies |

Results on the 18-question ground-truth set (`python run.py --evaluate`):

| Metric | Score |
| :--- | :--- |
| Verdict accuracy | 18 / 18 (100%) |
| Refusal correctness | 8 / 8 (100%) |
| Rules-gate latency | < 0.05 ms |

Validate the dataset itself with `python tests/test_make_test_data.py`.

---

## Verdicts

| Verdict | Meaning | Action |
| :--- | :--- | :--- |
| `ANSWERABLE` | Unambiguous and supported by the data | Generate, execute, and report |
| `ANSWERABLE_WITH_ASSUMPTION` | Answerable under stated assumptions (currency, date format) | Report the result and list assumptions |
| `CANNOT_DETERMINE` | Required metric or rate is missing | Refuse with the reason |
| `CONTRADICTION` | Sources disagree | Flag both and report the discrepancy |
| `AMBIGUOUS` | Question is underspecified | Ask for the missing parameter |

---

## Audit manifests

Each run writes `answers/manifest_<QUESTION_ID>.json`. Note that the default ID `CLI_Q` is overwritten on each CLI run; pass `--question-id` to keep history.

```json
{
  "question_id": "CLI_Q",
  "question": "What is the total revenue from completed USD orders?",
  "timestamp": "2026-10-07T04:54:08+00:00",
  "environment": { "python_version": "3.13.7", "pandas_version": "2.3.3", "platform": "Windows-11" },
  "input_file_hashes": { "orders.csv": "2d9c1dc4...", "customers.csv": "b6a518f5..." },
  "verdict": "answerable",
  "verdict_reason": "Executed verified Pandas script in sandbox",
  "assumptions": ["Deduplicated records and parsed currency formatting"],
  "code": "...",
  "code_hash": "a4f8c9...",
  "output_value": 12313.21,
  "output_hash": "e3b0c4...",
  "consensus_details": { "status": "agree", "runs": 1 }
}
```

---

## Configuration reference

| Argument | Env var | Default | Description |
| :--- | :--- | :--- | :--- |
| `--provider` | `LLM_PROVIDER` | `gemini` | `gemini`, `ollama`, `openai`, `groq`, `deepseek`, `openrouter` |
| `--model` | `GEMINI_MODEL` / `OPENAI_MODEL` / `OLLAMA_MODEL` | `gemini-2.5-flash` | Model identifier |
| `--api-key` | `GEMINI_API_KEY` / `OPENAI_API_KEY` | none | Key for hosted providers |
| `--base-url` | `OPENAI_BASE_URL` | none | Custom OpenAI-compatible endpoint |
| `--candidates` | none | `1` | Candidate runs for consensus |
| `--question-id` | none | `CLI_Q` | Manifest/solution filename ID |
| `--no-llm` | none | off | Deterministic rules only |
| `--profile-only` | none | off | Print profiling report and exit |
| `--evaluate` | none | off | Run the benchmark |

---

## Troubleshooting

- **"Python was not found" (Windows):** use the launcher (`py -m venv venv`, `py run.py`) or disable the Store aliases under *Settings > Apps > Advanced app settings > App execution aliases*.
- **"Failed to connect to Ollama":** run `ollama serve`, check `ollama list`, or switch to a hosted provider, or use `--no-llm`.
- **Missing or altered data:** re-run `python make_test_data.py` to regenerate the CSVs and `data/data_hashes.json`.

---

## License

MIT
