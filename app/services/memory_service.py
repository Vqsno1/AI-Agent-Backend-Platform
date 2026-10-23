from sqlalchemy import select

from app.db.models import Memory


def search_memory(db, user_id, query, limit=10):
    # Escape LIKE metacharacters; search is always scoped to authenticated identity.
    term = query.replace("!", "!!").replace("%", "!%").replace("_", "!_")
    return db.scalars(
        select(Memory)
        .where(Memory.user_id == user_id, Memory.content.ilike(f"%{term}%", escape="!"))
        .order_by(Memory.created_at.desc())
        .limit(limit)
    ).all()


def save_memory(db, task, content):
    db.add(Memory(user_id=task.user_id, source_task_id=task.id, content=content))
