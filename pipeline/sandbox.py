"""
pipeline/sandbox.py
Component 4: Sandbox Executor.
Safely runs generated python code in an isolated subprocess with a strict timeout,
captures stdout/stderr, and parses printed output into structured values.
"""

import sys
import json
import time
import subprocess
from pathlib import Path
from typing import Any, Optional, Dict
from dataclasses import dataclass

@dataclass
class SandboxResult:
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    execution_time_ms: float
    extracted_value: Optional[Any] = None
    error_message: Optional[str] = None

class SandboxExecutor:
    """
    Subprocess sandbox runner for Python/pandas scripts.
    """
    def __init__(self, timeout_seconds: int = 15, base_dir: Optional[Path] = None):
        self.timeout_seconds = timeout_seconds
        self.base_dir = base_dir or Path(__file__).resolve().parent.parent

    def run_code(self, script_code: str, custom_cwd: Optional[Path] = None) -> SandboxResult:
        """
        Runs the Python script_code in a subprocess.
        """
        cwd = custom_cwd or self.base_dir
        start_time = time.perf_counter()

        try:
            process = subprocess.run(
                [sys.executable, "-c", script_code],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            stdout = process.stdout.strip()
            stderr = process.stderr.strip()

            if process.returncode != 0:
                return SandboxResult(
                    success=False,
                    exit_code=process.returncode,
                    stdout=stdout,
                    stderr=stderr,
                    execution_time_ms=elapsed_ms,
                    error_message=f"Process exited with non-zero status code: {process.returncode}\n{stderr}"
                )

            # Parse extracted value from stdout
            extracted = self._parse_output(stdout)

            return SandboxResult(
                success=True,
                exit_code=0,
                stdout=stdout,
                stderr=stderr,
                execution_time_ms=elapsed_ms,
                extracted_value=extracted
            )

        except subprocess.TimeoutExpired:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return SandboxResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="",
                execution_time_ms=elapsed_ms,
                error_message=f"Execution timed out after {self.timeout_seconds} seconds."
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return SandboxResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="",
                execution_time_ms=elapsed_ms,
                error_message=f"Sandbox execution error: {str(e)}"
            )

    def _parse_output(self, stdout: str) -> Any:
        """
        Extracts the final printed value from stdout.
        Attempts JSON first, then float/int, then raw string.
        """
        if not stdout:
            return None

        # Take the last non-empty line
        lines = [line.strip() for line in stdout.splitlines() if line.strip()]
        if not lines:
            return None
        last_line = lines[-1]

        # Try JSON
        try:
            return json.loads(last_line)
        except json.JSONDecodeError:
            pass

        # Try float / int
        try:
            if "." in last_line:
                return round(float(last_line), 4)
            return int(last_line)
        except ValueError:
            pass

        # Return stripped string
        return last_line

if __name__ == "__main__":
    sandbox = SandboxExecutor()
    sample_code = """
import pandas as pd
df = pd.read_csv('data/orders.csv', keep_default_na=False)
print(len(df))
"""
    res = sandbox.run_code(sample_code)
    print(f"Success: {res.success}")
    print(f"Extracted Value: {res.extracted_value} (type: {type(res.extracted_value)})")
    print(f"Execution time: {res.execution_time_ms:.2f}ms")
