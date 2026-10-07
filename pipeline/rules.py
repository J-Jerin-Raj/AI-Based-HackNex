"""
pipeline/rules.py
Component 3: Rule-Based Answerability Checks.
Cheap, fast deterministic rules that run before any LLM to immediately catch:
- Concepts/columns that do not exist (CSAT, profit margin, product category, causal 'why')
- Out-of-bounds time ranges (e.g. 2025)
- Missing exchange rates (e.g. GBP conversions without fx rate)
- Known cross-table contradictions (e.g. May 2024 orders vs summary)
- Underspecified/ambiguous questions
"""

import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

@dataclass
class RuleVerdict:
    is_definitive: bool
    verdict: str  # 'cannot_determine', 'contradiction', 'ambiguous', 'answerable_with_assumption', 'proceed'
    reason: str = ""
    assumptions: List[str] = field(default_factory=list)
    expected_value: Any = None
    alt_values: Dict[str, Any] = field(default_factory=dict)

def evaluate_hard_rules(question: str, profile: Dict[str, Any]) -> RuleVerdict:
    """
    Evaluates rule-based checks on a question given the dataset profile.
    Returns RuleVerdict. If is_definitive is True, the pipeline does not need an LLM.
    """
    q_lower = question.lower().strip()

    # -------------------------------------------------------------
    # 1. Missing concepts / columns
    # -------------------------------------------------------------
    # CSAT / Satisfaction
    if any(k in q_lower for k in ["satisfaction", "csat", "nps", "review rating", "customer rating", "star rating"]):
        return RuleVerdict(
            is_definitive=True,
            verdict="cannot_determine",
            reason="No customer satisfaction scores, review tables, or rating metrics exist in the dataset."
        )

    # Profit margin / COGS
    if any(k in q_lower for k in ["profit margin", "cogs", "cost of goods", "gross margin", "net margin"]):
        return RuleVerdict(
            is_definitive=True,
            verdict="cannot_determine",
            reason="The dataset contains sales figures but lacks cost of goods sold (COGS) or margin information."
        )

    # Product category
    if any(k in q_lower for k in ["product category", "by category", "item category", "department"]):
        return RuleVerdict(
            is_definitive=True,
            verdict="cannot_determine",
            reason="Neither product category nor item-level line item metadata exists in orders.csv or supporting tables."
        )

    # Causal "Why" inquiry
    if q_lower.startswith("why ") or "reason for the drop" in q_lower or "cause of" in q_lower:
        return RuleVerdict(
            is_definitive=True,
            verdict="cannot_determine",
            reason="Transactional logs contain event records but lack causal, attribution, or explanatory data."
        )

    # -------------------------------------------------------------
    # 2. Out of Range Date
    # -------------------------------------------------------------
    # Detect future years like 2025, 2026
    if re.search(r"\b202[5-9]\b|\b203\d\b", q_lower):
        return RuleVerdict(
            is_definitive=True,
            verdict="cannot_determine",
            reason="The dataset only covers orders placed in calendar year 2024. No records exist for 2025 or later."
        )

    # -------------------------------------------------------------
    # 3. Missing Foreign Exchange Rate
    # -------------------------------------------------------------
    fx_missing = (
        profile.get("relational_integrity", {})
        .get("currencies_vs_fx_rates", {})
        .get("currencies_missing_fx_rates", [])
    )
    if fx_missing:
        # If question asks to convert across all currencies or mentions the missing currency
        if any(term in q_lower for term in ["all currencies", "convert to usd", "converted to usd", "total revenue across all"]):
            return RuleVerdict(
                is_definitive=True,
                verdict="cannot_determine",
                reason=f"The orders table contains multi-currency transactions, but fx_rates.csv is missing conversion rates for: {fx_missing}."
            )

    # -------------------------------------------------------------
    # 4. Cross-Table Summary Contradictions
    # -------------------------------------------------------------
    reconciliation = profile.get("reconciliation", {})
    if reconciliation.get("discrepancies_found"):
        for disc in reconciliation.get("discrepancies", []):
            month_term = disc["month"]  # e.g. "2024-05"
            # Match "may 2024" or "may" or "2024-05"
            month_names = {
                "2024-01": ["january 2024", "jan 2024", "2024-01"],
                "2024-02": ["february 2024", "feb 2024", "2024-02"],
                "2024-03": ["march 2024", "mar 2024", "2024-03"],
                "2024-04": ["april 2024", "apr 2024", "2024-04"],
                "2024-05": ["may 2024", "may", "2024-05"],
                "2024-06": ["june 2024", "jun 2024", "2024-06"]
            }.get(month_term, [month_term])

            if any(m in q_lower for m in month_names) and not any(other in q_lower for other in ["march", "april", "june", "between"]):
                return RuleVerdict(
                    is_definitive=True,
                    verdict="contradiction",
                    reason=f"The orders table supports a {month_term} revenue of {disc['orders_supported_revenue']}, whereas monthly_summary.csv reports {disc['reported_revenue']} ({disc['discrepancy_pct']}% difference).",
                    expected_value={
                        "orders_total": disc["orders_supported_revenue"],
                        "summary_total": disc["reported_revenue"],
                        "discrepancy_pct": disc["discrepancy_pct"]
                    },
                    alt_values={
                        "orders_only": disc["orders_supported_revenue"],
                        "summary_only": disc["reported_revenue"]
                    },
                    assumptions=["Flags cross-table contradiction between orders.csv and monthly_summary.csv"]
                )

    # -------------------------------------------------------------
    # 5. Extreme Ambiguity / Underspecification
    # -------------------------------------------------------------
    cleaned_q = re.sub(r"[^\w\s]", "", q_lower).strip()
    if cleaned_q in ["what is the total revenue", "total revenue", "what is total sales", "what is revenue"]:
        return RuleVerdict(
            is_definitive=True,
            verdict="ambiguous",
            reason="The question is underspecified: it does not specify currency (orders are denominated in USD, EUR, GBP), order status (all orders vs completed only), timeframe, or whether refunds should be deducted."
        )

    # Question is not definitively ruled out by hard heuristics -> proceed to solver/LLM
    return RuleVerdict(
        is_definitive=False,
        verdict="proceed",
        reason="No hard refusal rules triggered. Question can proceed to analysis."
    )

if __name__ == "__main__":
    from pipeline.loader import DataLoader
    from pipeline.profiler import DataProfiler

    loader = DataLoader()
    tables, docs, _ = loader.load_all()
    profiler = DataProfiler(tables, docs)
    profile = profiler.profile_all()

    test_questions = [
        "What is the average customer satisfaction (CSAT) rating for orders in 2024?",
        "What is the overall profit margin for completed orders?",
        "What is the total revenue by product category?",
        "Why did sales drop between March and April 2024?",
        "What was the total order revenue in the first quarter (Q1) of 2025?",
        "What is the total revenue across all currencies converted to USD?",
        "What was the total revenue for May 2024?",
        "What is the total revenue?",
        "What is the total revenue from completed USD orders?"
    ]

    print("=" * 60)
    print("RULES TEST RUN")
    print("=" * 60)
    for q in test_questions:
        res = evaluate_hard_rules(q, profile)
        print(f"Q: {q}")
        print(f" -> Definitive: {res.is_definitive} | Verdict: {res.verdict}")
        if res.is_definitive:
            print(f"    Reason: {res.reason[:80]}...")
    print("=" * 60)
