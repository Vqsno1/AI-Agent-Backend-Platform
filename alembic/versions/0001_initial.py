"""Initial durable task schema."""

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False, index=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, index=True),
        sa.Column("max_steps", sa.Integer(), nullable=False),
        sa.Column("use_memory", sa.Boolean(), nullable=False),
        sa.Column("result", sa.JSON()),
        sa.Column("error_code", sa.String()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "task_steps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id"), nullable=False, index=True),
        sa.Column("agent_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("output", sa.JSON()),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.UniqueConstraint("task_id", "step_order"),
    )
    op.create_table(
        "memories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False, index=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "source_task_id", sa.String(36), sa.ForeignKey("tasks.id"), nullable=False, unique=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "tool_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "task_step_id",
            sa.String(36),
            sa.ForeignKey("task_steps.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("tool_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String()),
    )


def downgrade():
    for table in ("tool_executions", "memories", "task_steps", "tasks"):
        op.drop_table(table)
