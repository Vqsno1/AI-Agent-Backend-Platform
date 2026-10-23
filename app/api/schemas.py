from typing import Literal

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000, pattern=r"\S")
    workflow: Literal["research_and_analysis"] = "research_and_analysis"
    max_steps: int = Field(default=6, ge=4, le=8)
    use_memory: bool = True


class MemorySearch(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=10, ge=1, le=50)
