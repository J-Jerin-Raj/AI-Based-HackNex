"""
pipeline/gate.py
Component 8: LLM Answerability Gate.
Given the question, dataset schemas, sample rows, and data profile,
queries the LLM to output a schema-constrained decision:
{verdict, reason, assumptions[], ambiguities[]}
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import pandas as pd

from pipeline.llm_client import OllamaClient

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

@dataclass
class GateDecision:
    verdict: str  # 'answerable', 'answerable_with_assumption', 'cannot_determine', 'contradiction', 'ambiguous'
    reason: str
    assumptions: List[str]
    ambiguities: List[str]

class AnswerabilityGate:
    """
    LLM refusal and answerability decision gate.
    """
    def __init__(self, llm_client: Optional[OllamaClient] = None):
        self.llm = llm_client or OllamaClient()
        self.prompt_template = (PROMPTS_DIR / "gate_prompt.txt").read_text(encoding="utf-8")

    def format_table_schemas(self, tables: Dict[str, pd.DataFrame]) -> str:
        """Constructs concise schemas and 2 sample rows per table."""
        parts = []
        for name, df in tables.items():
            cols = list(df.columns)
            sample_str = df.head(2).to_string(index=False)
            parts.append(f"Table: {name} (Columns: {cols})\nSample:\n{sample_str}\n")
        return "\n".join(parts)

    def format_data_profile(self, profile: Dict[str, Any]) -> str:
        """Extracts critical flags and traps from the profiler into prompt context."""
        summary_lines = []
        for trap in profile.get("critical_traps_detected", []):
            summary_lines.append(f"- [FLAG] {trap}")

        recon = profile.get("reconciliation", {})
        if recon.get("discrepancies_found"):
            for d in recon.get("discrepancies", []):
                summary_lines.append(
                    f"- [CONTRADICTION] Month {d['month']}: summary reports {d['reported_revenue']} "
                    f"vs orders support {d['orders_supported_revenue']} (discrepancy {d['discrepancy_pct']}%)"
                )

        rel = profile.get("relational_integrity", {})
        fx = rel.get("currencies_vs_fx_rates", {})
        if fx.get("currencies_missing_fx_rates"):
            summary_lines.append(f"- [MISSING FX] Unpegged currencies missing exchange rates: {fx['currencies_missing_fx_rates']}")

        return "\n".join(summary_lines) if summary_lines else "No major anomalies detected."

    def evaluate(
        self,
        question: str,
        tables: Dict[str, pd.DataFrame],
        profile: Dict[str, Any]
    ) -> GateDecision:
        """
        Submits prompt to LLM and returns structured GateDecision.
        """
        schemas_text = self.format_table_schemas(tables)
        profile_text = self.format_data_profile(profile)

        prompt = self.prompt_template.format(
            question=question,
            table_schemas=schemas_text,
            data_profile=profile_text
        )

        try:
            data = self.llm.generate_json(prompt=prompt, temperature=0.0)
            verdict = str(data.get("verdict", "answerable")).strip().lower()
            if verdict not in ["answerable", "answerable_with_assumption", "cannot_determine", "contradiction", "ambiguous"]:
                verdict = "answerable"

            return GateDecision(
                verdict=verdict,
                reason=data.get("reason", "No reason provided."),
                assumptions=data.get("assumptions", []),
                ambiguities=data.get("ambiguities", [])
            )
        except Exception as e:
            # Fallback to answerable if JSON parse failed
            return GateDecision(
                verdict="answerable",
                reason=f"Gate evaluation error (fallback to answerable): {str(e)}",
                assumptions=["Proceeding with standard data cleaning"],
                ambiguities=[]
            )

if __name__ == "__main__":
    from pipeline.loader import DataLoader
    from pipeline.profiler import DataProfiler

    loader = DataLoader()
    tables, docs, _ = loader.load_all()
    profiler = DataProfiler(tables, docs)
    profile = profiler.profile_all()

    gate = AnswerabilityGate()
    decision = gate.evaluate("What is the total revenue for March 2024?", tables, profile)
    print(f"Gate Verdict: {decision.verdict}")
    print(f"Reason:       {decision.reason}")
    print(f"Assumptions:  {decision.assumptions}")
