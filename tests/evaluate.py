"""
tests/evaluate.py
Component 7: Evaluation Harness.
Runs questions against the benchmark answer key (questions_answer_key.json)
and computes:
- Overall verdict accuracy
- Refusal correctness (cannot_determine, contradiction, ambiguous)
- Numerical/value accuracy on answerable questions
- Discrepancy analysis
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

# Setup project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.loader import DataLoader
from pipeline.profiler import DataProfiler
from pipeline.rules import evaluate_hard_rules, RuleVerdict
from pipeline.consensus import are_values_equivalent

class EvaluationHarness:
    """
    Evaluator that tests rule verdicts and pipeline solutions against the answer key.
    """
    def __init__(self, key_path: Optional[Path] = None):
        self.key_path = key_path or PROJECT_ROOT / "tests" / "questions_answer_key.json"
        self.loader = DataLoader()
        self.tables, self.docs, self.hashes = self.loader.load_all()
        self.profiler = DataProfiler(self.tables, self.docs)
        self.profile = self.profiler.profile_all()

    def load_answer_key(self) -> List[Dict[str, Any]]:
        with open(self.key_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def run_evaluation(self, solver_func=None) -> Dict[str, Any]:
        """
        Runs evaluation across all benchmark questions.
        If solver_func is provided, it is invoked for questions that pass hard rules.
        """
        questions = self.load_answer_key()
        results = []

        total_questions = len(questions)
        verdict_matches = 0
        value_matches = 0
        refusal_tests = 0
        refusal_correct = 0

        print("=" * 80)
        print(f"RUNNING BENCHMARK EVALUATION ({total_questions} questions)")
        print("=" * 80)

        import time
        start_eval_time = time.perf_counter()

        for q in questions:
            t0 = time.perf_counter()
            qid = q["id"]
            q_text = q["question"]
            expected_verdict = q["expected_verdict"]
            expected_val = q.get("expected_value")
            alt_vals = q.get("alt_values", {})

            # Step 1: Run deterministic hard rules
            rule_res: RuleVerdict = evaluate_hard_rules(q_text, self.profile)

            predicted_verdict = None
            predicted_val = None
            pred_source = "rule"

            if rule_res.is_definitive:
                predicted_verdict = rule_res.verdict
                predicted_val = rule_res.expected_value
            elif solver_func is not None:
                # If solver provided, call it
                sol = solver_func(q, self.profile)
                predicted_verdict = sol.get("verdict", "answerable")
                predicted_val = sol.get("value")
                pred_source = "solver"
            else:
                # Without an LLM/solver, questions passing rules are treated as answerable candidates
                predicted_verdict = "answerable"
                pred_source = "rules_fallback"

            # Check verdict correctness
            is_verdict_correct = False
            if predicted_verdict == expected_verdict:
                is_verdict_correct = True
            elif expected_verdict in ["answerable", "answerable_with_assumption"] and predicted_verdict in ["answerable", "answerable_with_assumption"]:
                is_verdict_correct = True

            if is_verdict_correct:
                verdict_matches += 1

            # Check refusal tracking
            if expected_verdict in ["cannot_determine", "contradiction", "ambiguous"]:
                refusal_tests += 1
                if is_verdict_correct:
                    refusal_correct += 1

            # Check value correctness
            is_value_correct = False
            if expected_val is not None and predicted_val is not None:
                if are_values_equivalent(predicted_val, expected_val):
                    is_value_correct = True
                elif any(are_values_equivalent(predicted_val, av) for av in alt_vals.values()):
                    is_value_correct = True

                if is_value_correct:
                    value_matches += 1

            q_time_ms = (time.perf_counter() - t0) * 1000
            result_entry = {
                "id": qid,
                "question": q_text,
                "expected_verdict": expected_verdict,
                "predicted_verdict": predicted_verdict,
                "verdict_correct": is_verdict_correct,
                "expected_value": expected_val,
                "predicted_value": predicted_val,
                "value_correct": is_value_correct,
                "time_ms": round(q_time_ms, 2),
                "source": pred_source
            }
            results.append(result_entry)

            status_icon = "[OK]" if is_verdict_correct else "[FAIL]"
            print(f"{status_icon} {qid:<4} | Exp: {expected_verdict:<26} | Got: {predicted_verdict:<16} | Time: {q_time_ms:5.2f}ms | Source: {pred_source}")

        total_elapsed_s = time.perf_counter() - start_eval_time
        verdict_accuracy = (verdict_matches / total_questions) * 100 if total_questions > 0 else 0
        refusal_acc = (refusal_correct / refusal_tests) * 100 if refusal_tests > 0 else 0

        print("=" * 80)
        print("BENCHMARK SUMMARY")
        print(f"Total Questions:       {total_questions}")
        print(f"Verdict Accuracy:      {verdict_matches}/{total_questions} ({verdict_accuracy:.1f}%)")
        print(f"Refusal Correctness:   {refusal_correct}/{refusal_tests} ({refusal_acc:.1f}%)")
        print(f"Total Execution Time:  {total_elapsed_s:.3f} seconds (avg {total_elapsed_s * 1000 / total_questions:.2f}ms / question)")
        print("=" * 80)

        return {
            "total_questions": total_questions,
            "verdict_matches": verdict_matches,
            "verdict_accuracy_pct": round(verdict_accuracy, 2),
            "refusal_correct": refusal_correct,
            "refusal_total": refusal_tests,
            "refusal_accuracy_pct": round(refusal_acc, 2),
            "results": results
        }

if __name__ == "__main__":
    harness = EvaluationHarness()
    harness.run_evaluation()
