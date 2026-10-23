from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://agentflow:agentflow@localhost:5432/agentflow"
    redis_url: str = "redis://localhost:6379/0"
    # JSON mapping: API key -> stable user ID. No default access key.
    api_keys: dict[str, str] = {}
    llm_provider: str = "mock"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = "gpt-4o-mini"
    llm_max_tokens: int = Field(default=1000, ge=64, le=4096)
    task_timeout: int = Field(default=120, ge=10, le=600)
    max_attempts: int = Field(default=3, ge=1, le=5)
    # Conservative upper bound supplied by operator, not inferred provider pricing.
    cost_per_1k_tokens: float = Field(default=0.01, gt=0)
    task_budget_usd: float = Field(default=1.0, gt=0)


@lru_cache
def get_settings():
    return Settings()
