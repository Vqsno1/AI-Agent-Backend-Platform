from fastapi import HTTPException
from sqlalchemy import select

from app.db.models import Task


def get_task(db, task_id, user_id):
    task = db.scalar(select(Task).where(Task.id == str(task_id), Task.user_id == user_id))
    if task is None:
        raise HTTPException(404, "Task not found")
    return task


def create_task(db, user_id, data):
    task = Task(
        user_id=user_id, prompt=data.prompt, max_steps=data.max_steps, use_memory=data.use_memory
    )
    db.add(task)
    db.commit()
    return task
