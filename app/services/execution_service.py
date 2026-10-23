import hashlib
import json
import logging
import time
from contextlib import nullcontext

from sqlalchemy import select, text

from app.agents.orchestrator import AgentOrchestrator
from app.config import get_settings
from app.db.models import Task, TaskStep, ToolExecution
from app.db.session import SessionLocal, engine
from app.llm.client import LLMClient
from app.services.memory_service import save_memory, search_memory
from app.tools.registry import ToolRegistry

log = logging.getLogger(__name__)
TERMINAL = {"completed", "failed", "cancelled", "queue_failed"}


class Cancelled(Exception):
    pass


def execute_task(task_id, client=None):
    # Session advisory lock is released automatically if a worker connection dies.
    # Unlike row locks, it allows API cancellation while serializing redeliveries.
    postgres = engine.dialect.name == "postgresql"
    with engine.connect() if postgres else nullcontext(None) as lock:
        key = int.from_bytes(hashlib.sha256(task_id.encode()).digest()[:8], "big", signed=True)
        if postgres and not lock.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}):
            return
        try:
            _execute(task_id, client or LLMClient())
        finally:
            if postgres:
                lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})


def _execute(task_id, client):
    settings = get_settings()
    started = time.monotonic()
    with SessionLocal() as db:
        task = db.scalar(select(Task).where(Task.id == task_id).with_for_update())
        if not task or task.status in TERMINAL:
            return

        def check():
            db.refresh(task)
            if task.status in {"cancelling", "cancelled"}:
                raise Cancelled()
            if time.monotonic() - started > settings.task_timeout:
                raise TimeoutError("task_timeout")

        try:
            check()
            task.status = "running"
            db.commit()
            context = {"prompt": task.prompt, "memories": [], "previous": []}
            if task.use_memory:
                context["memories"] = [
                    m.content[:1000] for m in search_memory(db, task.user_id, task.prompt[:80], 3)
                ]
            for index, agent in enumerate(AgentOrchestrator().create_plan(task.max_steps)):
                check()
                step = db.scalar(
                    select(TaskStep).where(
                        TaskStep.task_id == task_id, TaskStep.step_order == index
                    )
                )
                if step is None:
                    step = TaskStep(task_id=task_id, agent_type=agent.role, step_order=index)
                    db.add(step)
                    db.commit()
                if step.status == "completed":
                    context["previous"].append(json.dumps(step.output)[:1600])
                    continue
                output = None
                while step.attempts < settings.max_attempts:
                    check()
                    # One UTF-8 byte per input token is a conservative admission bound.
                    charge = len(json.dumps(context).encode()) + settings.llm_max_tokens + 4000
                    reserved = charge * settings.cost_per_1k_tokens / 1000
                    if task.reserved_cost_usd + reserved > settings.task_budget_usd:
                        raise ValueError("budget_exceeded")
                    task.reserved_cost_usd += reserved
                    step.attempts += 1
                    step.status = "running"
                    db.commit()
                    try:
                        output = agent.run(client, context)
                        check()
                        for call in output.tool_calls:
                            t0 = time.monotonic()
                            try:
                                result = ToolRegistry().execute(
                                    call.get("name"), call.get("arguments", {}), agent.allowed_tools
                                )
                            except Exception:
                                db.add(
                                    ToolExecution(
                                        task_step_id=step.id,
                                        tool_name=str(call.get("name"))[:100],
                                        status="failed",
                                        duration_ms=int((time.monotonic() - t0) * 1000),
                                        error_code="tool_rejected",
                                    )
                                )
                                db.commit()
                                raise
                            db.add(
                                ToolExecution(
                                    task_step_id=step.id,
                                    tool_name=call["name"],
                                    status="completed",
                                    duration_ms=int((time.monotonic() - t0) * 1000),
                                )
                            )
                            output.findings.append(json.dumps(result))
                        break
                    except (Cancelled, TimeoutError):
                        raise
                    except Exception:
                        step.status = "retrying"
                        db.commit()
                        if step.attempts >= settings.max_attempts:
                            raise
                        time.sleep(0.1 * step.attempts)
                if output is None:
                    raise ValueError("attempts_exhausted")
                step.output = output.model_dump()
                step.status = "completed"
                db.commit()
                context["previous"].append(json.dumps(step.output)[:1600])
            # Lock final transition so cancellation cannot be overwritten.
            db.rollback()
            task = db.scalar(select(Task).where(Task.id == task_id).with_for_update())
            db.refresh(task)
            if task.status in {"cancelling", "cancelled"}:
                raise Cancelled()
            task.result = step.output
            task.status = "completed"
            if task.use_memory:
                save_memory(db, task, json.dumps(task.result))
            db.commit()
            log.info(
                "task_completed",
                extra={"task_id": task_id, "duration_ms": int((time.monotonic() - started) * 1000)},
            )
        except Exception as error:
            db.rollback()
            task = db.scalar(select(Task).where(Task.id == task_id).with_for_update())
            db.refresh(task)
            task.status = (
                "cancelled"
                if isinstance(error, Cancelled) or task.status == "cancelling"
                else "failed"
            )
            task.error_code = None if task.status == "cancelled" else type(error).__name__
            for pending in db.scalars(
                select(TaskStep).where(TaskStep.task_id == task_id, TaskStep.status != "completed")
            ):
                pending.status = task.status
            db.commit()
            log.warning("task_stopped", extra={"task_id": task_id, "error_code": task.error_code})
