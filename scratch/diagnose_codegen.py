import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.loader import DataLoader
from pipeline.profiler import DataProfiler
from pipeline.codegen import CodeGenerator
from pipeline.llm_client import OllamaClient

loader = DataLoader()
tables, docs, _ = loader.load_all()
profile = DataProfiler(tables, docs).profile_all()

codegen = CodeGenerator()
schemas_text = codegen.format_table_schemas(tables)
profile_text = codegen.format_profile_for_codegen(profile)
assumptions = ["Proceeding with standard data cleaning"]
question = "What is the total revenue from completed USD orders?"

assumptions_str = "\n".join(f"- {a}" for a in assumptions)
prompt = codegen.codegen_prompt_tmpl.format(
    question=question,
    table_schemas=schemas_text,
    data_profile=profile_text,
    assumptions=assumptions_str
)

print("Prompt length:", len(prompt))
import requests
resp = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": codegen.llm.model,
        "prompt": prompt,
        "system": "You are a code-only assistant. Return ONLY executable Python code inside ```python ``` code block. No explanations.",
        "stream": False,
        "options": {"num_predict": 4096, "temperature": 0.1}
    },
    timeout=180
)
data = resp.json()
print("done_reason:", data.get("done_reason"))
print("eval_count:", data.get("eval_count"))
print("thinking length:", len(data.get("thinking", "")))
print("response length:", len(data.get("response", "")))
print("response text:\n", data.get("response", ""))
