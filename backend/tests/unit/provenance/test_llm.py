"""Unit tests for sb.provenance.llm."""

from __future__ import annotations

import httpx
import pytest
from sb.provenance.llm import (
    OPTIONS,
    build_prompt,
    generate,
    llm_status,
    model_info,
)


def test_build_prompt() -> None:
    chunks = ["Paragraph 1 about cooling.", "Paragraph 2 about ledger."]
    question = "Who is the principal architect?"
    expected = (
        "Answer the question using only the context. "
        "Context: Paragraph 1 about cooling.\n\nParagraph 2 about ledger. "
        "Question: Who is the principal architect?"
    )
    assert build_prompt(chunks, question) == expected


def test_generate_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail_client(*args: object, **kwargs: object) -> httpx.Client:
        raise RuntimeError("Network should not be accessed during replay mode")

    monkeypatch.setattr("sb.provenance.llm._client", _fail_client)

    result = generate("Prompt", fallback_text="fallback", replay_text="Replayed answer")
    assert result.mode == "replay"
    assert result.text == "Replayed answer"
    assert result.model_name == "qwen2.5:3b"
    assert result.model_digest is None
    assert result.latency_ms >= 0


def test_generate_live_success(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_requests: list[httpx.Request] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        if request.url.path == "/api/generate":
            assert request.method == "POST"
            import json

            body = json.loads(request.content.decode("utf-8"))
            assert body["stream"] is False
            assert body["options"] == OPTIONS
            assert body["model"] == "qwen2.5:3b"
            assert body["prompt"] == "Test prompt"
            return httpx.Response(
                200,
                json={"response": "   Live response text from model. \n\n"},
            )
        elif request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "qwen2.5:3b",
                            "digest": "sha256:abcd1234efgh5678",
                        }
                    ]
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(mock_handler)
    monkeypatch.setattr(
        "sb.provenance.llm._client",
        lambda timeout=25.0: httpx.Client(transport=transport, timeout=timeout),
    )

    result = generate("Test prompt", fallback_text="fallback")
    assert result.mode == "live"
    assert result.text == "Live response text from model."
    assert result.model_name == "qwen2.5:3b"
    assert result.model_digest == "sha256:abcd1234efgh5678"
    assert result.latency_ms >= 0


def test_generate_http_500(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "Internal Server Error"})

    transport = httpx.MockTransport(mock_handler)
    monkeypatch.setattr(
        "sb.provenance.llm._client",
        lambda timeout=25.0: httpx.Client(transport=transport, timeout=timeout),
    )

    result = generate("Test prompt", fallback_text="extractive fallback content")
    assert result.mode == "extractive_fallback"
    assert result.text == "extractive fallback content"
    assert result.model_digest is None


def test_closed_port_t_pr_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SB_OLLAMA_URL", "http://127.0.0.1:9")

    # Use real _client against closed port
    result = generate("Test prompt", fallback_text="fallback text")
    assert result.mode == "extractive_fallback"
    assert result.text == "fallback text"

    status = llm_status()
    assert status == "down"

    info = model_info()
    assert info["name"] == "qwen2.5:3b"
    assert info["digest"] is None


def test_model_info_and_llm_status_with_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "qwen2.5:3b",
                            "digest": "sha256:tagsdigest999",
                        }
                    ]
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(mock_handler)
    monkeypatch.setattr(
        "sb.provenance.llm._client",
        lambda timeout=3.0: httpx.Client(transport=transport, timeout=timeout),
    )
    monkeypatch.setattr("sb.provenance.llm._last_mode", None)

    info = model_info()
    assert info == {"name": "qwen2.5:3b", "digest": "sha256:tagsdigest999"}

    status = llm_status()
    assert status == "ok"
