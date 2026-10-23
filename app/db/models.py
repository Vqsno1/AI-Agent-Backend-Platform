import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now():
    return datetime.now(UTC)


def uid():
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    prompt: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(default="pending", index=True)
    max_steps: Mapped[int] = mapped_column(default=6)
    reserved_cost_usd: Mapped[float] = mapped_column(default=0.0)
    use_memory: Mapped[bool] = mapped_column(default=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class TaskStep(Base):
    __tablename__ = "task_steps"
    __table_args__ = (UniqueConstraint("task_id", "step_order"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    agent_type: Mapped[str]
    status: Mapped[str] = mapped_column(default="pending")
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    step_order: Mapped[int]
    attempts: Mapped[int] = mapped_column(default=0)


class Memory(Base):
    __tablename__ = "memories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    content: Mapped[str] = mapped_column(Text)
    source_task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ToolExecution(Base):
    __tablename__ = "tool_executions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    task_step_id: Mapped[str] = mapped_column(ForeignKey("task_steps.id"), index=True)
    tool_name: Mapped[str]
    status: Mapped[str]
    duration_ms: Mapped[int]
    error_code: Mapped[str | None] = mapped_column(nullable=True)
