"""Record pending and completed pipeline work durably."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003_pipeline_jobs"
down_revision = "0002_workspace_scope"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pipeline_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage", sa.String(20), nullable=False),
        sa.Column("run_key", sa.String(255), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("session_id", "stage", "run_key", name="uq_pipeline_stage_run"),
    )
    for column in ("session_id", "available_at"):
        op.create_index(f"ix_pipeline_jobs_{column}", "pipeline_jobs", [column])

    # Segments can contain identical audio, but their positions must be unique.
    op.drop_constraint("uq_chunk_session_checksum", "audio_chunks", type_="unique")


def downgrade():
    raise RuntimeError("Downgrade would remove pending pipeline work")
