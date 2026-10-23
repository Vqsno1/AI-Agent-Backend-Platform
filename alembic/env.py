from alembic import context
from app.db.models import Base
from app.db.session import engine


def run_migrations():
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
