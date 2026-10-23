import json

import httpx
from pydantic import BaseModel, Field

from app.config import get_settings


class AgentOutput(BaseModel):
    summary: str = Field(min_length=1, max_length=12000)
    findings: list[str] = Field(default_factory=list, max_length=20)
    recommendation: str | None = None
    tool_calls: list[dict] = Field(default_factory=list, max_length=2)


class LLMClient:
    def __init__(self):
        self.settings = get_settings()

    def generate_structured(self, role, context):
        s = self.settings
        if s.llm_provider == "mock":
            return AgentOutput(
                summary=f"Mock {role} output (no live research performed).",
                findings=[context["prompt"][:200]],
                recommendation="Configure a live model for substantive recommendations."
                if role == "summarizer"
                else None,
            )
        if s.llm_provider != "openai" or not s.llm_api_key.get_secret_value():
            raise ValueError("provider_not_configured")
        from app.agents.prompts import SYSTEM_PROMPT

        with httpx.Client(timeout=20, follow_redirects=False) as client:
            response = client.post(
                s.llm_base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {s.llm_api_key.get_secret_value()}"},
                json={
                    "model": s.llm_model,
                    "max_tokens": s.llm_max_tokens,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {
                            "role": "system",
                            "content": SYSTEM_PROMPT
                            + f" Your role is {role}. Schema: "
                            + json.dumps(AgentOutput.model_json_schema()),
                        },
                        {"role": "user", "content": json.dumps(context)},
                    ],
                },
            )
            response.raise_for_status()
            return AgentOutput.model_validate_json(
                response.json()["choices"][0]["message"]["content"]
            )
