"""Assign new recordings to verified workspaces and preserve legacy recordings."""

from alembic import op
import sqlalchemy as sa

revision = "0002_workspace_scope"
down_revision = "0001_recording_baseline"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sessions", sa.Column("workspace_id", sa.Uuid()))
    op.add_column("sessions", sa.Column("owner_id", sa.String(255)))
    op.create_index("ix_sessions_workspace_id", "sessions", ["workspace_id"])


def downgrade():
    raise RuntimeError("Downgrade would remove the recording access boundary")
