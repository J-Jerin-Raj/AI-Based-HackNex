"""
run.py
Streamlined end-to-end quantitative analysis agent.
Supports:
1. Interactive prompt loop (python run.py or python ask.py)
2. Direct CLI question input (python run.py "What is the revenue for May 2024?")
3. Batch questions file input (python run.py --file my_questions.txt)
4. Local LLMs (Ollama) & hosted LLMs (OpenAI, Groq, DeepSeek, OpenRouter)
5. Full 18-question benchmark evaluation (python run.py --evaluate)
"""

import sys
import json
import time
import argparse
import os
from pathlib import Path
from typing import Optional, Dict, Any, List

from pipeline.loader import DataLoader
from pipeline.profiler import DataProfiler
from pipeline.rules import evaluate_hard_rules, RuleVerdict
from pipeline.llm_client import get_llm_client, BaseLLMClient
from pipeline.codegen import CodeGenerator
from pipeline.sandbox import SandboxExecutor
from pipeline.consensus import ConsensusChecker
from pipeline.explain import Explainer
from pipeline.manifest import ManifestBuilder

def format_output(
    verdict: str,
    reason: str = "",
    value: Any = None,
    assumptions: list = None,
    explanation: str = None,
    manifest_path: str = None
):
    print("\n" + "=" * 70)
    print(f"VERDICT:     {verdict.upper()}")
    print("-" * 70)
    if value is not None:
        print(f"RESULT:      {value}")
    if explanation:
        print(f"EXPLANATION: {explanation}")
    elif reason:
        print(f"EXPLANATION: {reason}")
    if assumptions:
        print("ASSUMPTIONS:")
        for a in assumptions:
            print(f"  * {a}")
    if manifest_path:
        print(f"MANIFEST:    {manifest_path}")
    print("=" * 70 + "\n")

def process_question_pipeline(
    question: str,
    question_id: str = "CLI_Q",
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    use_llm: bool = True,
    num_candidates: int = 1,
    data_dir: Optional[Path] = None,
    answers_dir: Optional[Path] = None
) -> Dict[str, Any]:
    answers_dir = answers_dir or Path(__file__).resolve().parent / "answers"
    answers_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1: per-stage timing (enabled via ENABLE_PERF_TIMING=1, default OFF)
    _timing_on = os.environ.get("ENABLE_PERF_TIMING", "0") == "1"
    _t0_total = time.perf_counter()
    perf: Dict[str, Any] = {"llm_call_count": 0}

    def _ms(t_start: float) -> float:
        return round((time.perf_counter() - t_start) * 1000, 2)

    def _save_perf(path: Path) -> None:
        """Inject 'performance' key into the manifest JSON after it has been written."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["performance"] = perf
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass  # Never let timing code break the audit path

    # 1. Load Data & Compute Cryptographic Hashes
    _t = time.perf_counter()
    loader = DataLoader(data_dir=data_dir)
    tables, docs, file_hashes = loader.load_all()
    manifest_builder = ManifestBuilder(file_hashes)
    if _timing_on:
        perf["load_ms"] = _ms(_t)

    # 2. Profile the Dataset for Traps
    _t = time.perf_counter()
    profiler = DataProfiler(tables, docs)
    profile = profiler.profile_all()
    if _timing_on:
        perf["profile_ms"] = _ms(_t)

    # 3. Deterministic Hard Rules Check (instant 0.01s refusal / contradiction check)
    _t = time.perf_counter()
    rule_verdict: RuleVerdict = evaluate_hard_rules(question, profile)
    if _timing_on:
        perf["gate_ms"] = _ms(_t)
    if rule_verdict.is_definitive:
        manifest = manifest_builder.create_manifest(
            question_id=question_id,
            question=question,
            verdict=rule_verdict.verdict,
            verdict_reason=rule_verdict.reason,
            assumptions=rule_verdict.assumptions,
            output_value=rule_verdict.expected_value
        )
        manifest_path = answers_dir / f"manifest_{question_id}.json"
        _t = time.perf_counter()
        manifest_builder.save_manifest(manifest, manifest_path)
        if _timing_on:
            perf["manifest_write_ms"] = _ms(_t)
            perf["total_ms"] = _ms(_t0_total)
            _save_perf(manifest_path)

        format_output(
            verdict=rule_verdict.verdict,
            reason=rule_verdict.reason,
            value=rule_verdict.expected_value,
            assumptions=rule_verdict.assumptions,
            manifest_path=str(manifest_path)
        )
        result = {
            "question_id": question_id,
            "verdict": rule_verdict.verdict,
            "value": rule_verdict.expected_value,
            "reason": rule_verdict.reason,
            "manifest_file": str(manifest_path)
        }
        if _timing_on:
            result["performance"] = perf
        return result

    # If LLM execution is disabled
    if not use_llm:
        print("[i] Question passed deterministic hard rules. LLM generation skipped (--no-llm).")
        return {"question_id": question_id, "verdict": "passed_rules", "value": None}

    # Instantiate LLM client (local or hosted)
    _t = time.perf_counter()
    llm = get_llm_client(provider=provider, model=model_name, api_key=api_key, base_url=base_url)
    if _timing_on:
        perf["client_init_ms"] = _ms(_t)

    # 4. Code Generation & Sandbox Execution
    provider_name = provider or "gemini"
    print(f"[*] Question identified as answerable. Generating code using {provider_name} ({llm.model})...")
    sandbox = SandboxExecutor()
    consensus = ConsensusChecker()
    codegen = CodeGenerator(llm_client=llm, sandbox=sandbox, consensus=consensus)

    _t = time.perf_counter()
    outcome, best_code, sandbox_results = codegen.generate_and_execute_with_consensus(
        question=question,
        tables=tables,
        profile=profile,
        assumptions=["Standard data cleaning, deduplication, and currency parsing applied"],
        num_candidates=num_candidates
    )
    if _timing_on:
        perf["codegen_total_ms"] = _ms(_t)
        # Count LLM calls: 1 codegen + up to 2 repairs per candidate
        for res in sandbox_results:
            perf["llm_call_count"] += 1  # initial codegen
        # repairs are tracked separately — add heuristic: if a candidate failed initially, count repairs

    if outcome.status == "agree" and outcome.consensus_value is not None:
        if str(outcome.consensus_value).strip().upper() in ["CANNOT_DETERMINE", "NON_ANSWERABLE", "UNANSWERABLE"]:
            verdict = "cannot_determine"
            reason = "The requested entity, column, or metric does not exist in the dataset."
            _t = time.perf_counter()
            manifest = manifest_builder.create_manifest(
                question_id=question_id,
                question=question,
                verdict=verdict,
                verdict_reason=reason,
                code=best_code
            )
            manifest_path = answers_dir / f"manifest_{question_id}.json"
            manifest_builder.save_manifest(manifest, manifest_path)
            if _timing_on:
                perf["manifest_write_ms"] = _ms(_t)
                perf["total_ms"] = _ms(_t0_total)
                _save_perf(manifest_path)

            format_output(
                verdict=verdict,
                reason=reason,
                manifest_path=str(manifest_path)
            )
            result = {
                "question_id": question_id,
                "verdict": verdict,
                "value": None,
                "reason": reason,
                "manifest_file": str(manifest_path)
            }
            if _timing_on:
                result["performance"] = perf
            return result

        # 5. Micro-Prompt Explainer
        print("[*] Code executed successfully. Generating concise explanation...")
        _t = time.perf_counter()
        explainer = Explainer(llm_client=llm)
        explanation = explainer.explain(
            question=question,
            verified_result=outcome.consensus_value,
            assumptions=["Deduplicated records and cleaned currency formats"]
        )
        if _timing_on:
            perf["explain_ms"] = _ms(_t)
            perf["llm_call_count"] += 1  # explainer call

        manifest = manifest_builder.create_manifest(
            question_id=question_id,
            question=question,
            verdict="answerable",
            verdict_reason="Executed verified Pandas script in sandbox",
            assumptions=["Deduplicated records and parsed currency formatting"],
            code=best_code,
            output_value=outcome.consensus_value,
            consensus_details={"status": outcome.status, "runs": outcome.total_runs}
        )
        manifest_path = answers_dir / f"manifest_{question_id}.json"
        _t = time.perf_counter()
        manifest_builder.save_manifest(manifest, manifest_path)
        if _timing_on:
            perf["manifest_write_ms"] = _ms(_t)
            perf["total_ms"] = _ms(_t0_total)
            _save_perf(manifest_path)

        format_output(
            verdict="answerable",
            value=outcome.consensus_value,
            explanation=explanation,
            assumptions=["Deduplicated records and cleaned currency formats"],
            manifest_path=str(manifest_path)
        )
        result = {
            "question_id": question_id,
            "verdict": "answerable",
            "value": outcome.consensus_value,
            "explanation": explanation,
            "manifest_file": str(manifest_path)
        }
        if _timing_on:
            result["performance"] = perf
        return result
    else:
        verdict = "cannot_determine_reliably"
        reason = f"Code execution in sandbox could not reach consensus ({outcome.details})."
        manifest = manifest_builder.create_manifest(
            question_id=question_id,
            question=question,
            verdict=verdict,
            verdict_reason=reason,
            code=best_code
        )
        manifest_path = answers_dir / f"manifest_{question_id}.json"
        _t = time.perf_counter()
        manifest_builder.save_manifest(manifest, manifest_path)
        if _timing_on:
            perf["manifest_write_ms"] = _ms(_t)
            perf["total_ms"] = _ms(_t0_total)
            _save_perf(manifest_path)

        format_output(
            verdict=verdict,
            reason=reason,
            manifest_path=str(manifest_path)
        )
        result = {
            "question_id": question_id,
            "verdict": verdict,
            "value": None,
            "reason": reason,
            "manifest_file": str(manifest_path)
        }
        if _timing_on:
            result["performance"] = perf
        return result

def run_interactive_mode(
    provider: str = "ollama",
    model: Optional[str] = None,
    api_key: Optional[str] = None
):
    """
    Launches an interactive prompt session in the terminal.
    """
    loader = DataLoader()
    tables, docs, _ = loader.load_all()
    profiler = DataProfiler(tables, docs)
    profile = profiler.profile_all()

    current_provider = provider
    current_model = model

    print("=" * 70)
    print(" QUANTITATIVE DATA ANALYSIS AGENT - INTERACTIVE SHELL")
    print("=" * 70)
    print(f"Loaded Tables: {list(tables.keys())}")
    print(f"Traps Flagged: {len(profile.get('critical_traps_detected', []))} anomalies detected")
    print(f"Provider:      {current_provider} (model: {current_model or 'default'})")
    print("-" * 70)
    print("Commands:")
    print("  :traps       - View all detected data traps and anomalies")
    print("  :evaluate    - Run the full 18-question benchmark test")
    print("  :model <m>   - Switch model (e.g. :model qwen2.5-coder:7b)")
    print("  :exit        - Exit the shell")
    print("=" * 70 + "\n")

    q_counter = 1
    while True:
        try:
            user_input = input(f"[{q_counter}] Enter your question > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting session.")
            break

        if not user_input:
            continue

        cmd = user_input.lower()
        if cmd in [":exit", ":quit", "exit", "quit", "q"]:
            print("Session ended.")
            break
        elif cmd in [":traps", ":profile"]:
            print("\n--- DETECTED DATA TRAPS & ANOMALIES ---")
            for t in profile.get("critical_traps_detected", []):
                print(f" [!] {t}")
            print("---------------------------------------\n")
            continue
        elif cmd in [":evaluate", ":benchmark"]:
            from tests.evaluate import EvaluationHarness
            harness = EvaluationHarness()
            harness.run_evaluation()
            continue
        elif cmd.startswith(":model "):
            current_model = user_input.split(" ", 1)[1].strip()
            print(f"[i] Model switched to: {current_model}\n")
            continue
        elif cmd.startswith(":provider "):
            current_provider = user_input.split(" ", 1)[1].strip()
            print(f"[i] Provider switched to: {current_provider}\n")
            continue

        qid = f"USER_Q{q_counter:02d}"
        process_question_pipeline(
            question=user_input,
            question_id=qid,
            provider=current_provider,
            model_name=current_model,
            api_key=api_key
        )
        q_counter += 1

def process_batch_file(filepath: Path, provider: str = "ollama", model: Optional[str] = None):
    """Reads questions from a text or JSON file and runs each one."""
    if not filepath.exists():
        print(f"[!] File not found: {filepath}")
        return

    questions: List[str] = []
    if filepath.suffix.lower() == ".json":
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "question" in item:
                        questions.append(item["question"])
                    elif isinstance(item, str):
                        questions.append(item)
    else:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    questions.append(line)

    print(f"[*] Processing {len(questions)} questions from {filepath.name}...")
    for idx, q in enumerate(questions, 1):
        print(f"\n[{idx}/{len(questions)}] Question: {q}")
        process_question_pipeline(
            question=q,
            question_id=f"BATCH_{idx:02d}",
            provider=provider,
            model_name=model
        )

def main():
    parser = argparse.ArgumentParser(description="End-to-End Quantitative Analysis Agent")
    parser.add_argument("question", nargs="?", help="Question text to answer")
    parser.add_argument("--interactive", "-i", action="store_true", help="Launch interactive prompt shell")
    parser.add_argument("--file", "-f", help="Path to text or JSON file containing questions")
    parser.add_argument("--question-id", default="CLI_Q", help="Identifier for the question")
    parser.add_argument("--provider", default=None, choices=["gemini", "ollama", "openai", "groq", "deepseek", "openrouter"], help="LLM Provider (default: gemini)")
    parser.add_argument("--model", default=None, help="Model name (e.g. gemini-2.5-flash, qwen2.5-coder:1.5b, gpt-4o-mini)")
    parser.add_argument("--api-key", default=None, help="API key for hosted LLM providers")
    parser.add_argument("--base-url", default=None, help="Base URL for hosted LLM providers")
    parser.add_argument("--candidates", type=int, default=1, help="Number of code candidates for consensus (default: 1)")
    parser.add_argument("--no-llm", action="store_true", help="Run deterministic rules only")
    parser.add_argument("--profile-only", action="store_true", help="Print table profiling report only")
    parser.add_argument("--evaluate", action="store_true", help="Run full evaluation harness")

    args = parser.parse_args()

    if args.evaluate:
        from tests.evaluate import EvaluationHarness
        harness = EvaluationHarness()
        harness.run_evaluation()
        return

    if args.profile_only:
        loader = DataLoader()
        tables, docs, _ = loader.load_all()
        profiler = DataProfiler(tables, docs)
        profile = profiler.profile_all()
        print(json.dumps(profile, indent=2, default=str))
        return

    if args.file:
        process_batch_file(Path(args.file), provider=args.provider, model=args.model)
        return

    if args.interactive or not args.question:
        run_interactive_mode(provider=args.provider, model=args.model, api_key=args.api_key)
        return

    process_question_pipeline(
        question=args.question,
        question_id=args.question_id,
        provider=args.provider,
        model_name=args.model,
        api_key=args.api_key,
        base_url=args.base_url,
        use_llm=not args.no_llm,
        num_candidates=args.candidates
    )

if __name__ == "__main__":
    main()
