"""
pipeline/manifest.py
Component 6: Manifest Builder.
Constructs and writes verifiable cryptographic run manifests containing:
- Input data file SHA-256 hashes
- Python, pandas, and platform environment metadata
- Final answer verdict, reasoning, and declared assumptions
- Self-contained solution code & code SHA-256 hash
- Result value & result SHA-256 hash
"""

import sys
import json
import hashlib
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
import pandas as pd

@dataclass
class RunManifest:
    question_id: str
    question: str
    timestamp: str
    environment: Dict[str, str]
    input_file_hashes: Dict[str, str]
    verdict: str
    verdict_reason: str
    assumptions: List[str]
    code: Optional[str] = None
    code_hash: Optional[str] = None
    output_value: Optional[Any] = None
    output_hash: Optional[str] = None
    consensus_details: Optional[Dict[str, Any]] = None
    relevant_sources: Optional[List[Dict[str, Any]]] = None

class ManifestBuilder:
    """
    Builds and writes cryptographic run records to prove answer lineage.
    """
    def __init__(self, input_hashes: Dict[str, str]):
        self.input_hashes = input_hashes

    def create_manifest(
        self,
        question_id: str,
        question: str,
        verdict: str,
        verdict_reason: str,
        assumptions: Optional[List[str]] = None,
        code: Optional[str] = None,
        output_value: Optional[Any] = None,
        consensus_details: Optional[Dict[str, Any]] = None,
        relevant_sources: Optional[List[Dict[str, Any]]] = None
    ) -> RunManifest:
        # Compute code hash
        code_h = None
        if code:
            code_h = hashlib.sha256(code.encode("utf-8")).hexdigest()

        # Compute output hash
        output_h = None
        if output_value is not None:
            serialized_out = json.dumps(output_value, sort_keys=True, default=str)
            output_h = hashlib.sha256(serialized_out.encode("utf-8")).hexdigest()

        env_info = {
            "python_version": sys.version.split()[0],
            "pandas_version": pd.__version__,
            "platform": platform.platform(),
            "machine": platform.machine()
        }

        return RunManifest(
            question_id=question_id,
            question=question,
            timestamp=datetime.now(timezone.utc).isoformat(),
            environment=env_info,
            input_file_hashes=self.input_hashes,
            verdict=verdict,
            verdict_reason=verdict_reason,
            assumptions=assumptions or [],
            code=code,
            code_hash=code_h,
            output_value=output_value,
            output_hash=output_h,
            consensus_details=consensus_details,
            relevant_sources=relevant_sources
        )

    def save_manifest(self, manifest: RunManifest, output_file: Path) -> Path:
        """Saves manifest to JSON."""
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(asdict(manifest), f, indent=2)
        return output_file

if __name__ == "__main__":
    builder = ManifestBuilder({"orders.csv": "abc123sha256"})
    m = builder.create_manifest(
        question_id="Q02",
        question="What is total USD revenue?",
        verdict="answerable",
        verdict_reason="Executed pandas script cleanly",
        output_value=12313.21,
        code="print(12313.21)"
    )
    print(f"Created manifest for {m.question_id} with output hash: {m.output_hash}")
