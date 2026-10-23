from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from redis import Redis
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.api.schemas import MemorySearch, TaskCreate
from app.config import get_settings
from app.core.logging import configure_logging
from app.db.models import Task, TaskStep
from app.db.session import get_db
from app.dependencies import current_user
from app.services.memory_service import search_memory
from app.services.task_service import create_task, get_task
from app.workers.worker import run_task

configure_logging()


def task_view(task):
    return {
        "task_id": task.id,
        "status": task.status,
        "prompt": task.prompt,
        "result": task.result,
        "error_code": task.error_code,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def create_app():
    app = FastAPI(title="AgentFlow", version="0.1.0")

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready(db: Session = Depends(get_db)):
        try:
            db.execute(text("SELECT 1 FROM tasks LIMIT 1"))
            with Redis.from_url(
                get_settings().redis_url, socket_connect_timeout=2, socket_timeout=2
            ) as redis:
                redis.ping()
        except Exception:
            raise HTTPException(503, "Dependencies unavailable") from None
        return {"status": "ready"}

    @app.post("/api/v1/tasks", status_code=202)
    def submit(data: TaskCreate, user: str = Depends(current_user), db: Session = Depends(get_db)):
        task = create_task(db, user, data)
        try:
            run_task.apply_async(args=[task.id], retry=False)
        except Exception:
            # A publish error can follow broker acceptance; do not overwrite a worker's state.
            changed = db.execute(
                update(Task)
                .where(Task.id == task.id, Task.status == "pending")
                .values(status="queue_failed", error_code="queue_unavailable")
            ).rowcount
            db.commit()
            db.refresh(task)
            if changed:
                raise HTTPException(
                    503, {"task_id": task.id, "error": "Queue unavailable"}
                ) from None
        return task_view(task)

    @app.get("/api/v1/tasks")
    def listing(
        user: str = Depends(current_user),
        db: Session = Depends(get_db),
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ):
        return [
            task_view(t)
            for t in db.scalars(
                select(Task)
                .where(Task.user_id == user)
                .order_by(Task.created_at.desc(), Task.id)
                .offset(offset)
                .limit(limit)
            )
        ]

    @app.get("/api/v1/tasks/{task_id}")
    def retrieve(task_id: UUID, user: str = Depends(current_user), db: Session = Depends(get_db)):
        return task_view(get_task(db, task_id, user))

    @app.post("/api/v1/tasks/{task_id}/cancel")
    def cancel(task_id: UUID, user: str = Depends(current_user), db: Session = Depends(get_db)):
        task = db.scalar(
            select(Task).where(Task.id == str(task_id), Task.user_id == user).with_for_update()
        )
        if not task:
            raise HTTPException(404, "Task not found")
        if task.status == "pending":
            task.status = "cancelled"
        elif task.status == "running":
            task.status = "cancelling"
        db.commit()
        return task_view(task)

    @app.get("/api/v1/tasks/{task_id}/steps")
    def steps(task_id: UUID, user: str = Depends(current_user), db: Session = Depends(get_db)):
        get_task(db, task_id, user)
        return [
            {
                "id": s.id,
                "agent_type": s.agent_type,
                "status": s.status,
                "output": s.output,
                "attempts": s.attempts,
                "step_order": s.step_order,
            }
            for s in db.scalars(
                select(TaskStep)
                .where(TaskStep.task_id == str(task_id))
                .order_by(TaskStep.step_order)
            )
        ]

    @app.get("/api/v1/agents")
    def agents(user: str = Depends(current_user)):
        return {"agents": ["planner", "research", "analyst", "summarizer"]}

    @app.post("/api/v1/memories/search")
    def memories(
        data: MemorySearch, user: str = Depends(current_user), db: Session = Depends(get_db)
    ):
        return [
            {"id": m.id, "content": m.content, "source_task_id": m.source_task_id}
            for m in search_memory(db, user, data.query, data.limit)
        ]

    return app


app = create_app()
