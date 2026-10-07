"""
pipeline/llm_client.py
Unified, provider-agnostic LLM client.
Supports:
1. Local Ollama (default: qwen3:4b, or qwen2.5-coder:7b)
2. Hosted OpenAI-compatible providers (OpenAI, Groq, DeepSeek, Together, OpenRouter, vLLM)
Switch providers via CLI flags (--provider, --model), constructor arguments,
or environment variables:
  LLM_PROVIDER=ollama | openai
  LLM_MODEL=qwen3:4b | gpt-4o-mini | deepseek-chat
  OPENAI_API_KEY=sk-...
  OPENAI_BASE_URL=https://api.openai.com/v1
"""

import os
import re
import json
from pathlib import Path
from typing import Any, Dict, Optional, Union
import requests

def _load_env_file():
    """Load variables from .env if present into os.environ."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass

_load_env_file()

DEFAULT_PROVIDER = os.environ.get("LLM_PROVIDER", "gemini").lower()

DEFAULT_GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
DEFAULT_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
DEFAULT_GEMINI_URL = os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")

DEFAULT_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:1.5b")
DEFAULT_OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

DEFAULT_OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_OPENAI_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
DEFAULT_OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

class BaseLLMClient:
    """Abstract base interface for LLM providers."""
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        seed: Optional[int] = 42
    ) -> str:
        raise NotImplementedError

    def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0
    ) -> Dict[str, Any]:
        raise NotImplementedError

    @staticmethod
    def extract_python_code(response_text: str) -> str:
        """
        Extracts executable Python code from markdown code fences (```python ... ```)
        or raw script text. Strips leading language tags and reasoning blocks (<think>).
        """
        if not response_text:
            return ""

        # Remove chain-of-thought blocks if present (qwen3, deepseek-r1, etc.)
        cleaned = re.sub(r"<think>[\s\S]*?</think>", "", response_text, flags=re.DOTALL)
        if "<think>" in cleaned and "</think>" not in cleaned:
            cleaned = re.sub(r"<think>[\s\S]*", "", cleaned, flags=re.DOTALL)

        target = cleaned.strip() if cleaned.strip() else response_text.strip()

        pattern = r"```(?:python)?\s*(.*?)(?:```|$)"
        match = re.search(pattern, target, re.DOTALL | re.IGNORECASE)
        if match:
            code = match.group(1).strip()
        else:
            code = target.strip()

        code = re.sub(r"^```(?:python)?", "", code, flags=re.IGNORECASE).strip()
        code = re.sub(r"```$", "", code).strip()

        lines = code.splitlines()
        if lines and lines[0].strip().lower() == "python":
            code = "\n".join(lines[1:]).strip()

        return code

class OllamaClient(BaseLLMClient):
    """Client for local Ollama daemon."""
    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 240
    ):
        self.model = model or DEFAULT_OLLAMA_MODEL
        self.base_url = (base_url or DEFAULT_OLLAMA_URL).rstrip("/")
        self.timeout = timeout

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        seed: Optional[int] = 42
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens
        if seed is not None:
            payload["options"]["seed"] = seed
        if system:
            payload["system"] = system

        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "").strip()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Ollama API request failed for model '{self.model}': {str(e)}") from e

    def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": temperature,
                "num_predict": 1024
            }
        }
        if system:
            payload["system"] = system

        resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=self.timeout)
        resp.raise_for_status()
        raw = resp.json().get("response", "")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"(\{.*\})", raw, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            raise ValueError(f"Model failed to return valid JSON: {raw}")

class HostedOpenAIClient(BaseLLMClient):
    """
    Client for hosted LLMs via standard OpenAI-compatible endpoints
    (Gemini, OpenAI, Groq, DeepSeek, OpenRouter, Together, vLLM).
    """
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 60
    ):
        target_url = (base_url or DEFAULT_OPENAI_URL).rstrip("/")
        is_gemini = (
            "generativelanguage.googleapis.com" in target_url
            or (model and "gemini" in model.lower())
            or (not base_url and DEFAULT_PROVIDER == "gemini")
        )

        self.is_gemini = is_gemini
        if is_gemini:
            self.model = model or DEFAULT_GEMINI_MODEL
            self.api_key = api_key or DEFAULT_GEMINI_KEY or DEFAULT_OPENAI_KEY
            self.base_url = (base_url or DEFAULT_GEMINI_URL).rstrip("/")
        else:
            self.model = model or DEFAULT_OPENAI_MODEL
            self.api_key = api_key or DEFAULT_OPENAI_KEY
            self.base_url = target_url

        self.timeout = timeout

        if not self.api_key and "localhost" not in self.base_url:
            if is_gemini:
                raise ValueError(
                    "\n" + "=" * 65 + "\n"
                    "[!] GEMINI API KEY MISSING!\n"
                    "Please add your Gemini API key to your .env file:\n"
                    "  GEMINI_API_KEY=AIzaSy...\n\n"
                    "Or set it in PowerShell:\n"
                    "  $env:GEMINI_API_KEY=\"AIzaSy...\"\n"
                    "=" * 65 + "\n"
                )
            else:
                raise ValueError("API key must be provided or set in environment for hosted LLMs.")

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1500,
        seed: Optional[int] = 42
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if seed is not None and not getattr(self, "is_gemini", False):
            payload["seed"] = seed

        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=payload,
            timeout=self.timeout
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

    def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0
    ) -> Dict[str, Any]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"}
        }

        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=payload,
            timeout=self.timeout
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        return json.loads(raw)

def get_llm_client(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None
) -> BaseLLMClient:
    """
    Factory to instantiate the appropriate LLM client.
    Supports 'gemini' (default), 'ollama' (local), and OpenAI-compatible endpoints.
    """
    prov = (provider or DEFAULT_PROVIDER).lower()
    if prov in ["gemini", "google"]:
        return HostedOpenAIClient(
            model=model or DEFAULT_GEMINI_MODEL,
            api_key=api_key or DEFAULT_GEMINI_KEY or DEFAULT_OPENAI_KEY,
            base_url=base_url or DEFAULT_GEMINI_URL
        )
    elif prov in ["openai", "hosted", "groq", "deepseek", "together", "openrouter"]:
        return HostedOpenAIClient(model=model, api_key=api_key, base_url=base_url)
    elif prov == "ollama":
        return OllamaClient(model=model, base_url=base_url)
    else:
        # Fallback based on available credentials
        if DEFAULT_GEMINI_KEY or prov == "gemini":
            return HostedOpenAIClient(
                model=model or DEFAULT_GEMINI_MODEL,
                api_key=api_key or DEFAULT_GEMINI_KEY or DEFAULT_OPENAI_KEY,
                base_url=base_url or DEFAULT_GEMINI_URL
            )
        return OllamaClient(model=model, base_url=base_url)

if __name__ == "__main__":
    client = get_llm_client(provider="ollama")
    print(f"Instantiated client for provider 'ollama' with model: {client.model}")
