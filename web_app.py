"""
web_app.py
Interactive Document Assistant & Quantitative Analysis Web App.
Connects the Python verified quantitative analysis pipeline to a sleek
Lime & Black web interface.
"""

import os
import sys
import json
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List

from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.loader import DataLoader, compute_file_sha256
from pipeline.profiler import DataProfiler
from pipeline.rules import evaluate_hard_rules
from pipeline.llm_client import (
    DEFAULT_PROVIDER,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OPENAI_MODEL
)
from run import process_question_pipeline
from tests.evaluate import EvaluationHarness

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32MB max upload
DATA_DIR = PROJECT_ROOT / "data"
ANSWERS_DIR = PROJECT_ROOT / "answers"
DATA_DIR.mkdir(parents=True, exist_ok=True)
ANSWERS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".csv", ".txt", ".json", ".xlsx", ".xls", ".md"}

def is_allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/models", methods=["GET"])
def get_models():
    """Returns available model choices and defaults."""
    active_provider = os.environ.get("LLM_PROVIDER", DEFAULT_PROVIDER)
    active_gemini_model = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    active_ollama_model = os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)

    models = [
        {
            "id": "gemini-3.1-flash-lite",
            "name": "Gemini 3.1 Flash-Lite (Recommended)",
            "provider": "gemini",
            "badge": "Active • Free Tier • Fast",
            "default": active_gemini_model == "gemini-3.1-flash-lite"
        },
        {
            "id": "gemini-flash-lite-latest",
            "name": "Gemini Flash-Lite Latest",
            "provider": "gemini",
            "badge": "Google Gemini",
            "default": active_gemini_model == "gemini-flash-lite-latest"
        },
        {
            "id": "gemini-3.8-flash",
            "name": "Gemini 3.8 Flash",
            "provider": "gemini",
            "badge": "Google Gemini",
            "default": active_gemini_model == "gemini-3.8-flash"
        },
        {
            "id": "qwen2.5-coder:1.5b",
            "name": "Qwen 2.5 Coder 1.5B (Ollama)",
            "provider": "ollama",
            "badge": "Local • Offline",
            "default": active_provider == "ollama" and active_ollama_model == "qwen2.5-coder:1.5b"
        },
        {
            "id": "qwen3:4b",
            "name": "Qwen 3 4B (Ollama)",
            "provider": "ollama",
            "badge": "Local • Offline",
            "default": False
        }
    ]
    return jsonify({
        "current_provider": active_provider,
        "current_model": active_gemini_model,
        "models": models
    })

@app.route("/api/query", methods=["POST"])
def run_query():
    """
    Executes a user question through the verifiable quantitative analysis agent pipeline.
    """
    data = request.get_json(force=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Question is required."}), 400

    provider = data.get("provider") or os.environ.get("LLM_PROVIDER", "gemini")
    model_name = data.get("model") or os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
    num_candidates = int(data.get("candidates", 1))

    # Unique question ID for web trace
    qid = f"WEB_{uuid.uuid4().hex[:8].upper()}"

    # Synchronously persist active document canvas as an authoritative source document
    doc_context = data.get("document_context")
    if doc_context is not None:
        try:
            (DATA_DIR / "session_document.txt").write_text(doc_context, encoding="utf-8")
        except Exception:
            pass

    # Enable timing
    os.environ["ENABLE_PERF_TIMING"] = "1"
    start_time = time.perf_counter()

    try:
        pipeline_res = process_question_pipeline(
            question=question,
            question_id=qid,
            provider=provider,
            model_name=model_name,
            num_candidates=num_candidates
        )
        elapsed_s = round(time.perf_counter() - start_time, 3)

        # Retrieve solution code if generated
        solution_file = ANSWERS_DIR / f"solution_{qid}.py"
        solution_code = ""
        if solution_file.exists():
            solution_code = solution_file.read_text(encoding="utf-8")

        # Retrieve saved manifest
        manifest_file = ANSWERS_DIR / f"manifest_{qid}.json"
        manifest_data = {}
        if manifest_file.exists():
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
            except Exception:
                pass

        return jsonify({
            "success": True,
            "question_id": qid,
            "question": question,
            "verdict": pipeline_res.get("verdict", "unknown"),
            "value": pipeline_res.get("value"),
            "explanation": pipeline_res.get("explanation") or pipeline_res.get("reason", ""),
            "assumptions": pipeline_res.get("assumptions", []),
            "code": solution_code or manifest_data.get("code", ""),
            "code_hash": manifest_data.get("code_hash"),
            "output_hash": manifest_data.get("output_hash"),
            "manifest": manifest_data,
            "performance": pipeline_res.get("performance", {}),
            "execution_time_seconds": elapsed_s,
            "model_used": model_name,
            "provider_used": provider
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "question_id": qid
        }), 500

@app.route("/api/tables", methods=["GET"])
def get_tables():
    """Lists datasets in data/ with row counts, column names, preview, and SHA-256."""
    try:
        loader = DataLoader(data_dir=DATA_DIR)
        tables, docs, file_hashes = loader.load_all()

        table_list = []
        for name, df in tables.items():
            filepath = DATA_DIR / f"{name}.csv"
            size_bytes = filepath.stat().st_size if filepath.exists() else 0
            
            preview_rows = df.head(3).to_dict(orient="records")

            table_list.append({
                "name": name,
                "filename": f"{name}.csv",
                "rows": len(df),
                "columns": list(df.columns),
                "size_kb": round(size_bytes / 1024, 2),
                "sha256": file_hashes.get(f"{name}.csv", ""),
                "preview": preview_rows
            })

        doc_list = []
        for name, text in docs.items():
            filepath = DATA_DIR / name
            size_bytes = filepath.stat().st_size if filepath.exists() else 0
            doc_list.append({
                "name": name,
                "filename": name,
                "size_kb": round(size_bytes / 1024, 2),
                "sha256": file_hashes.get(name, ""),
                "preview": text[:200] + ("..." if len(text) > 200 else "")
            })

        return jsonify({
            "tables": table_list,
            "documents": doc_list,
            "total_files": len(table_list) + len(doc_list)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/file/<filename>", methods=["GET"])
def get_file_content(filename: str):
    """Returns detailed rows or raw text for inspecting a dataset."""
    clean_name = secure_filename(filename)
    filepath = DATA_DIR / clean_name
    if not filepath.exists() or not filepath.is_file():
        return jsonify({"error": "File not found"}), 404

    try:
        sha = compute_file_sha256(filepath)
        size_kb = round(filepath.stat().st_size / 1024, 2)
        suffix = filepath.suffix.lower()

        if suffix == ".csv":
            import pandas as pd
            df = pd.read_csv(filepath, keep_default_na=False, dtype=str)
            return jsonify({
                "type": "table",
                "filename": clean_name,
                "rows": len(df),
                "columns": list(df.columns),
                "data": df.head(100).to_dict(orient="records"),
                "sha256": sha,
                "size_kb": size_kb
            })
        else:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return jsonify({
                "type": "text",
                "filename": clean_name,
                "content": content,
                "sha256": sha,
                "size_kb": size_kb
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/upload", methods=["POST"])
def upload_files():
    """Accepts file uploads to data/ directory and returns updated status."""
    if "files" not in request.files:
        return jsonify({"error": "No files uploaded"}), 400

    uploaded = request.files.getlist("files")
    saved = []
    skipped = []

    for f in uploaded:
        if not f.filename:
            continue
        clean_name = secure_filename(f.filename)
        if is_allowed_file(clean_name):
            save_path = DATA_DIR / clean_name
            f.save(save_path)
            h = compute_file_sha256(save_path)
            saved.append({"filename": clean_name, "sha256": h})
        else:
            skipped.append(f.filename)

    return jsonify({
        "success": True,
        "saved": saved,
        "skipped": skipped,
        "message": f"Saved {len(saved)} file(s)."
    })

@app.route("/api/profile", methods=["GET"])
def get_data_profile():
    """Runs data profiler and returns detected traps and reconciliation discrepancies."""
    try:
        loader = DataLoader(data_dir=DATA_DIR)
        tables, docs, _ = loader.load_all()
        profiler = DataProfiler(tables, docs)
        profile = profiler.profile_all()

        return jsonify({
            "critical_traps": profile.get("critical_traps_detected", []),
            "reconciliation": profile.get("reconciliation", {}),
            "documentation_contradictions": profile.get("documentation_contradictions", []),
            "relational_integrity": profile.get("relational_integrity", {})
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/benchmark", methods=["POST"])
def run_benchmark():
    """Runs the full 18-question benchmark evaluation harness."""
    try:
        harness = EvaluationHarness()
        report = harness.run_evaluation()
        return jsonify({
            "success": True,
            "verdict_accuracy_pct": report["verdict_accuracy_pct"],
            "refusal_accuracy_pct": report["refusal_accuracy_pct"],
            "total_questions": report["total_questions"],
            "verdict_matches": report["verdict_matches"],
            "refusal_total": report["refusal_total"],
            "results": report["results"]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/document", methods=["GET"])
def get_document():
    """Retrieves current content and hash of session_document.txt."""
    doc_path = DATA_DIR / "session_document.txt"
    if doc_path.exists():
        try:
            content = doc_path.read_text(encoding="utf-8")
            h = compute_file_sha256(doc_path)
            return jsonify({
                "exists": True,
                "content": content,
                "sha256": h,
                "size_kb": round(doc_path.stat().st_size / 1024, 2)
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify({"exists": False, "content": "", "sha256": "", "size_kb": 0})

@app.route("/api/document/save", methods=["POST"])
def save_document():
    """Real-time auto-save endpoint for editable document canvas."""
    data = request.get_json(force=True) or {}
    content = data.get("content", "")
    try:
        doc_path = DATA_DIR / "session_document.txt"
        doc_path.write_text(content, encoding="utf-8")
        h = compute_file_sha256(doc_path)
        return jsonify({
            "success": True,
            "sha256": h,
            "size_kb": round(doc_path.stat().st_size / 1024, 2),
            "updated_at": time.strftime("%H:%M:%S")
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print("=" * 70)
    print(" HACKNEX QUANTITATIVE DATA AGENT - DOCUMENT ASSISTANT WEB APP")
    print("=" * 70)
    print(f" -> Local Web App URL: http://127.0.0.1:{port}")
    print(f" -> Color Palette:    Electric Lime (#CCFF00) & Carbon Black (#090A0B)")
    print(f" -> Default Model:    {os.environ.get('GEMINI_MODEL', 'gemini-3.1-flash-lite')}")
    print("=" * 70)
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
