import json

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from app.config import get_settings
from app.llm.client import LLMClient


def test_openai_compatible_request(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "llm_api_key", SecretStr("test-placeholder"))
    original = httpx.Client

    def respond(request):
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.content)
        assert payload["max_tokens"] == settings.llm_max_tokens
        assert payload["messages"][0]["role"] == "system"
        assert "untrusted" in payload["messages"][0]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"summary": "Validated provider response", "findings": ["Evidence"]}
                            )
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(
        "app.llm.client.httpx.Client",
        lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs),
    )
    result = LLMClient().generate_structured("analyst", {"prompt": "Compare frameworks"})
    assert result.summary == "Validated provider response"


def test_provider_invalid_json_rejected(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "llm_api_key", SecretStr("test-placeholder"))
    original = httpx.Client
    monkeypatch.setattr(
        "app.llm.client.httpx.Client",
        lambda **kwargs: original(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200, json={"choices": [{"message": {"content": "not json"}}]}
                )
            ),
            **kwargs,
        ),
    )
    with pytest.raises(ValidationError):
        LLMClient().generate_structured("planner", {"prompt": "Test"})
