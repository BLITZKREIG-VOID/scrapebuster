"""LLM client for Ollama generation and model status (master plan §9)."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Literal

import httpx

logger = logging.getLogger(__name__)

OPTIONS = {"temperature": 0, "seed": 42, "num_predict": 96}
TIMEOUT_S = 25.0

_last_mode: str | None = None


@dataclass
class LLMResult:
    text: str
    mode: str
    model_name: str
    model_digest: str | None
    latency_ms: int


def _client(timeout: float = TIMEOUT_S) -> httpx.Client:
    return httpx.Client(timeout=timeout)


def build_prompt(chunks: list[str], question: str) -> str:
    return "Answer the question using only the context. Context: " + "\n\n".join(chunks) + " Question: " + question


def model_info() -> dict[str, Any]:
    url = os.getenv("SB_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    model_name = os.getenv("SB_LLM_MODEL", "qwen2.5:3b")
    try:
        with _client(timeout=3.0) as client:
            resp = client.get(f"{url}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("models", [])
                for item in models:
                    if item.get("name") == model_name or item.get("model") == model_name:
                        return {"name": model_name, "digest": item.get("digest")}
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Ollama tags request failed: %s", exc)
    return {"name": model_name, "digest": None}


def generate(prompt: str, fallback_text: str, replay_text: str | None = None) -> LLMResult:
    global _last_mode
    start = time.perf_counter()
    model_name = os.getenv("SB_LLM_MODEL", "qwen2.5:3b")

    if replay_text is not None:
        _last_mode = "replay"
        latency = int((time.perf_counter() - start) * 1000)
        return LLMResult(
            text=replay_text,
            mode="replay",
            model_name=model_name,
            model_digest=None,
            latency_ms=latency,
        )

    url = os.getenv("SB_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": OPTIONS,
    }

    try:
        with _client(timeout=TIMEOUT_S) as client:
            resp = client.post(f"{url}/api/generate", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                if "response" in data and isinstance(data["response"], str):
                    text = data["response"].strip()
                    info = model_info()
                    _last_mode = "live"
                    latency = int((time.perf_counter() - start) * 1000)
                    return LLMResult(
                        text=text,
                        mode="live",
                        model_name=model_name,
                        model_digest=info.get("digest"),
                        latency_ms=latency,
                    )
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Ollama generate request failed: %s", exc)

    _last_mode = "extractive_fallback"
    latency = int((time.perf_counter() - start) * 1000)
    return LLMResult(
        text=fallback_text,
        mode="extractive_fallback",
        model_name=model_name,
        model_digest=None,
        latency_ms=latency,
    )


def llm_status() -> Literal["ok", "down", "fallback"]:
    url = os.getenv("SB_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    model_name = os.getenv("SB_LLM_MODEL", "qwen2.5:3b")
    try:
        with _client(timeout=3.0) as client:
            resp = client.get(f"{url}/api/tags")
            if resp.status_code != 200:
                return "down"
            data = resp.json()
            models = data.get("models", [])
            model_found = any(
                item.get("name") == model_name or item.get("model") == model_name
                for item in models
            )
            if not model_found:
                return "fallback"
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Ollama status check failed: %s", exc)
        return "down"

    if _last_mode == "extractive_fallback":
        return "fallback"
    return "ok"
