"""
pipeline/consensus.py
Component 5: Consensus Checker.
Compares outputs across N independent runs, applying numeric tolerances
for floating-point and rounding differences. Decides: agree, disagree, or too many failures.
"""

from typing import List, Any, Dict, Optional
from dataclasses import dataclass
from pipeline.sandbox import SandboxResult

@dataclass
class ConsensusOutcome:
    status: str  # 'agree', 'disagree', 'too_many_failures'
    consensus_value: Optional[Any]
    agreement_count: int
    total_runs: int
    success_count: int
    distinct_values: List[Any]
    details: str

def are_values_equivalent(val1: Any, val2: Any, float_tolerance: float = 1e-2) -> bool:
    """Check if two values are equal within floating point tolerance."""
    if val1 is None and val2 is None:
        return True
    if val1 is None or val2 is None:
        return False

    # Numeric comparison
    if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
        return abs(float(val1) - float(val2)) <= float_tolerance

    # Dict comparison (e.g. structured outputs like {"orders_total": ...})
    if isinstance(val1, dict) and isinstance(val2, dict):
        if set(val1.keys()) != set(val2.keys()):
            return False
        return all(are_values_equivalent(val1[k], val2[k], float_tolerance) for k in val1)

    # String comparison
    if isinstance(val1, str) and isinstance(val2, str):
        return val1.strip().lower() == val2.strip().lower()

    return val1 == val2

class ConsensusChecker:
    """
    Evaluates self-consistency across N sandbox executions.
    """
    def __init__(self, float_tolerance: float = 1e-2, min_agreement_ratio: float = 0.6):
        self.float_tolerance = float_tolerance
        self.min_agreement_ratio = min_agreement_ratio

    def evaluate(self, results: List[SandboxResult]) -> ConsensusOutcome:
        total_runs = len(results)
        if total_runs == 0:
            return ConsensusOutcome(
                status="too_many_failures",
                consensus_value=None,
                agreement_count=0,
                total_runs=0,
                success_count=0,
                distinct_values=[],
                details="No runs provided."
            )

        successful_runs = [r for r in results if r.success and r.extracted_value is not None]
        success_count = len(successful_runs)

        # If majority of runs failed to execute cleanly
        if success_count < (total_runs * 0.5):
            return ConsensusOutcome(
                status="too_many_failures",
                consensus_value=None,
                agreement_count=0,
                total_runs=total_runs,
                success_count=success_count,
                distinct_values=[],
                details=f"Only {success_count}/{total_runs} runs executed successfully."
            )

        # Cluster equivalent values
        clusters: List[List[Any]] = []
        for run in successful_runs:
            val = run.extracted_value
            placed = False
            for cluster in clusters:
                if are_values_equivalent(val, cluster[0], self.float_tolerance):
                    cluster.append(val)
                    placed = True
                    break
            if not placed:
                clusters.append([val])

        # Find the largest cluster
        clusters.sort(key=len, reverse=True)
        largest_cluster = clusters[0]
        largest_cluster_size = len(largest_cluster)

        distinct_vals = [c[0] for c in clusters]

        agreement_ratio = largest_cluster_size / total_runs

        if agreement_ratio >= self.min_agreement_ratio or largest_cluster_size >= 2:
            return ConsensusOutcome(
                status="agree",
                consensus_value=largest_cluster[0],
                agreement_count=largest_cluster_size,
                total_runs=total_runs,
                success_count=success_count,
                distinct_values=distinct_vals,
                details=f"Consensus reached: {largest_cluster_size}/{total_runs} runs agreed on value {largest_cluster[0]}."
            )
        else:
            return ConsensusOutcome(
                status="disagree",
                consensus_value=None,
                agreement_count=largest_cluster_size,
                total_runs=total_runs,
                success_count=success_count,
                distinct_values=distinct_vals,
                details=f"Runs disagreed. Distinct results: {distinct_vals}."
            )

if __name__ == "__main__":
    checker = ConsensusChecker()
    mock_results = [
        SandboxResult(True, 0, "12313.21", "", 100, 12313.21),
        SandboxResult(True, 0, "12313.2100", "", 100, 12313.21),
        SandboxResult(True, 0, "12313.20", "", 100, 12313.20),
    ]
    res = checker.evaluate(mock_results)
    print(f"Status: {res.status}")
    print(f"Consensus: {res.consensus_value}")
    print(f"Agreement count: {res.agreement_count}/{res.total_runs}")
