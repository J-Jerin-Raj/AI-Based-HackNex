"""
pipeline/codegen.py
Components 9 & 10: Code Generator and Repair Loop.
Given table schemas, sample rows, and data profile:
- Generates executable Pandas scripts
- Runs scripts in the sandbox
- Supports local (Ollama) and hosted (OpenAI/Groq/DeepSeek) models
"""

import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd

from pipeline.llm_client import BaseLLMClient, get_llm_client
from pipeline.sandbox import SandboxExecutor, SandboxResult
from pipeline.consensus import ConsensusChecker, ConsensusOutcome

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

class CodeGenerator:
    """
    Generates and repairs executable pandas scripts.
    """
    def __init__(
        self,
        llm_client: Optional[BaseLLMClient] = None,
        sandbox: Optional[SandboxExecutor] = None,
        consensus: Optional[ConsensusChecker] = None
    ):
        self.llm = llm_client or get_llm_client()
        self.sandbox = sandbox or SandboxExecutor()
        self.consensus = consensus or ConsensusChecker()
        self.codegen_prompt_tmpl = (PROMPTS_DIR / "codegen_prompt.txt").read_text(encoding="utf-8")
        self.repair_prompt_tmpl = (PROMPTS_DIR / "repair_prompt.txt").read_text(encoding="utf-8")

    def format_table_schemas(self, tables: Dict[str, pd.DataFrame]) -> str:
        parts = []
        for name, df in tables.items():
            cols = list(df.columns)
            sample_str = df.head(2).to_string(index=False)
            parts.append(f"Table: {name} (Columns: {cols})\nSample:\n{sample_str}\n")
        return "\n".join(parts)

    def format_profile_for_codegen(self, profile: Dict[str, Any]) -> str:
        flags = profile.get("critical_traps_detected", [])
        return "\n".join(f"- {f}" for f in flags[:6]) if flags else "Data is standard."

    def generate_single_script(
        self,
        question: str,
        table_schemas_text: str,
        profile_text: str,
        assumptions: List[str],
        temperature: float = 0.1,
        seed: int = 42
    ) -> str:
        """Generates one candidate Python script."""
        assumptions_str = "\n".join(f"- {a}" for a in assumptions) if assumptions else "None"
        prompt = self.codegen_prompt_tmpl.format(
            question=question,
            table_schemas=table_schemas_text,
            data_profile=profile_text,
            assumptions=assumptions_str
        )

        response = self.llm.generate(
            prompt=prompt,
            system="You are a code-only assistant. Return ONLY executable Python code inside ```python ``` code block. No explanations.",
            temperature=temperature,
            seed=seed
        )
        return self.llm.extract_python_code(response)

    def repair_script(
        self,
        failed_code: str,
        error_message: str,
        question: str,
        profile_text: str
    ) -> str:
        """Feeds traceback and failed script back to LLM for correction."""
        prompt = self.repair_prompt_tmpl.format(
            question=question,
            failed_code=failed_code,
            error_message=error_message,
            data_profile=profile_text
        )

        response = self.llm.generate(
            prompt=prompt,
            system="You are a code debugging assistant. Return ONLY corrected Python code inside ```python ``` block. No conversational text.",
            temperature=0.1
        )
        return self.llm.extract_python_code(response)

    def generate_and_execute_with_consensus(
        self,
        question: str,
        tables: Dict[str, pd.DataFrame],
        profile: Dict[str, Any],
        assumptions: List[str],
        num_candidates: int = 1,
        max_repairs_per_script: int = 2
    ) -> Tuple[ConsensusOutcome, str, List[SandboxResult]]:
        schemas_text = self.format_table_schemas(tables)
        profile_text = self.format_profile_for_codegen(profile)

        temperatures = [0.1, 0.3, 0.5][:num_candidates]
        while len(temperatures) < num_candidates:
            temperatures.append(0.1)

        sandbox_results: List[SandboxResult] = []
        candidate_codes: List[str] = []

        for i, temp in enumerate(temperatures):
            seed = 42 + i * 17
            print(f"[*] Candidate {i+1} generating code (temp={temp})...")
            code = self.generate_single_script(
                question=question,
                table_schemas_text=schemas_text,
                profile_text=profile_text,
                assumptions=assumptions,
                temperature=temp,
                seed=seed
            )

            # Check if code is empty before sandbox
            if not code or not code.strip():
                print(f"[!] Candidate {i+1} received empty code from LLM.")
                res = SandboxResult(
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr="",
                    execution_time_ms=0,
                    error_message="LLM generated an empty script."
                )
            else:
                # Execute in sandbox
                res = self.sandbox.run_code(code)

            if res.success and res.extracted_value is not None:
                print(f"[+] Candidate {i+1} executed successfully. Result: {res.extracted_value}")
            elif res.success and res.extracted_value is None:
                print(f"[!] Candidate {i+1} executed but printed no value (empty stdout).")
                res.success = False
                res.error_message = "Script did not print a value to stdout. Ensure script calls print(final_answer)."
            else:
                err_preview = res.error_message.splitlines()[0] if res.error_message else "execution error"
                print(f"[!] Candidate {i+1} failed in sandbox: {err_preview}")

            # Repair loop if failed
            repair_attempts = 0
            while not res.success and repair_attempts < max_repairs_per_script:
                repair_attempts += 1
                print(f"[*] Repair attempt {repair_attempts}/{max_repairs_per_script} for Candidate {i+1}...")
                repaired_code = self.repair_script(
                    failed_code=code,
                    error_message=res.error_message or res.stderr,
                    question=question,
                    profile_text=profile_text
                )
                res = self.sandbox.run_code(repaired_code)
                if res.success and res.extracted_value is not None:
                    print(f"[+] Candidate {i+1} repaired successfully! Result: {res.extracted_value}")
                    code = repaired_code
                    break
                else:
                    err_preview = res.error_message.splitlines()[0] if res.error_message else "error"
                    print(f"[!] Repair {repair_attempts} failed: {err_preview}")

            sandbox_results.append(res)
            candidate_codes.append(code)

        # Consensus check
        outcome = self.consensus.evaluate(sandbox_results)

        # Pick best code
        best_code = candidate_codes[0]
        if outcome.status == "agree":
            for code, res in zip(candidate_codes, sandbox_results):
                if res.success and res.extracted_value == outcome.consensus_value:
                    best_code = code
                    break

        return outcome, best_code, sandbox_results
