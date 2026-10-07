"""
pipeline/explain.py
Component 11: Micro-Prompt Explainer.
Turns the final verified code result and declared assumptions into a concise,
plain-language 1-2 sentence executive response.
Never computes or alters numbers.
"""

from pathlib import Path
from typing import Any, List, Optional
from pipeline.llm_client import BaseLLMClient, get_llm_client

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

class Explainer:
    """
    Generates plain-language executive summaries of verified code outputs.
    """
    def __init__(self, llm_client: Optional[BaseLLMClient] = None):
        self.llm = llm_client or get_llm_client()
        self.prompt_tmpl = (PROMPTS_DIR / "explain_prompt.txt").read_text(encoding="utf-8")

    def explain(
        self,
        question: str,
        verified_result: Any,
        assumptions: Optional[List[str]] = None
    ) -> str:
        """Generates a concise 1-2 sentence executive summary using a micro-call."""
        assumptions_text = "\n".join(f"- {a}" for a in (assumptions or [])) if assumptions else "Standard cleaning applied."

        prompt = self.prompt_tmpl.format(
            question=question,
            result=str(verified_result),
            assumptions=assumptions_text
        )

        try:
            explanation = self.llm.generate(
                prompt=prompt,
                system="You are an executive summary writer. Write strictly 1 or 2 clear sentences. Do not show calculations or thinking.",
                temperature=0.1,
                max_tokens=120
            )
            # Remove any thinking block if present
            if "</think>" in explanation:
                explanation = explanation.split("</think>")[-1].strip()
            return explanation.strip() if explanation.strip() else self._template_fallback(question, verified_result, assumptions)
        except Exception:
            return self._template_fallback(question, verified_result, assumptions)

    def _template_fallback(self, question: str, result: Any, assumptions: Optional[List[str]] = None) -> str:
        """Fast fallback template if LLM is unavailable or slow."""
        if isinstance(result, (int, float)):
            num_fmt = f"${result:,.2f}" if "revenue" in question.lower() or "amount" in question.lower() else f"{result:,}"
            return f"The verified result for this query is {num_fmt}."
        elif isinstance(result, dict):
            return f"The verified result is: {result}."
        return f"The verified result is {result}."

if __name__ == "__main__":
    explainer = Explainer()
    print(explainer.explain("What is total USD revenue?", 12313.21, ["Deduped orders"]))
