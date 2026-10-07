import requests

prompt = """Write a self-contained python script to calculate total revenue from completed USD orders.
Load data/orders.csv.
from helpers.cleaning import parse_currency_amount, clean_status
Clean status, clean amount, deduplicate by order_id.
Print the final sum. Return only python code inside ```python ```."""

r = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "qwen3:4b",
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": 2048,
            "temperature": 0.0
        }
    },
    timeout=60
)
data = r.json()
print("Thinking length:", len(data.get("thinking", "")))
print("Response length:", len(data.get("response", "")))
print("Response text:\n", data.get("response", ""))
