"""Persist conservative cost reservations across redelivery."""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "tasks", sa.Column("reserved_cost_usd", sa.Float(), nullable=False, server_default="0")
    )
    op.alter_column("tasks", "reserved_cost_usd", server_default=None)


def downgrade():
    op.drop_column("tasks", "reserved_cost_usd")
