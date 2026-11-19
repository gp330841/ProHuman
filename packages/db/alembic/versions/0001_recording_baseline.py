"""Baseline the recording schema created by legacy gateway startup."""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR

revision = "0001_recording_baseline"
down_revision = None
branch_labels = None
depends_on = None


def record_columns():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def session_ref():
    return sa.Column("session_id", sa.Uuid(), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    status = sa.Enum(
        "CREATED", "RECORDING", "PROCESSING", "TRANSCRIBING", "TRANSCRIBED",
        "INDEXING", "INDEXED", "EXTRACTING", "COMPLETED", "FAILED",
        name="sessionstatusenum",
    )
    existing = set(sa.inspect(op.get_bind()).get_table_names()) if not op.get_context().as_sql else set()
    tables = {"sessions", "audio_chunks", "transcript_segments", "feature_results"}
    if tables <= existing:
        return
    if tables & existing:
        raise RuntimeError("Expected either a fresh database or the complete legacy recording schema")

    op.create_table(
        "sessions", *record_columns(),
        sa.Column("device_id", sa.String(255), nullable=False),
        sa.Column("status", status, nullable=False),
        sa.Column("duration_seconds", sa.Float()),
        sa.Column("audio_format", sa.String(50)),
        sa.Column("sample_rate", sa.Integer()),
        sa.Column("s3_key", sa.String(512)),
        sa.Column("metadata", JSONB(), server_default="{}"),
    )
    for column in ("status", "device_id"):
        op.create_index(f"ix_sessions_{column}", "sessions", [column])

    op.create_table(
        "audio_chunks", *record_columns(), session_ref(),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("s3_key", sa.String(512), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.UniqueConstraint("session_id", "chunk_index", name="uq_chunk_session_index"),
        sa.UniqueConstraint("session_id", "checksum", name="uq_chunk_session_checksum"),
    )
    op.create_index("ix_audio_chunks_session_id", "audio_chunks", ["session_id"])

    op.create_table(
        "transcript_segments", *record_columns(), session_ref(),
        sa.Column("segment_index", sa.Integer(), nullable=False),
        sa.Column("speaker_label", sa.String(50), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("start_time", sa.Float(), nullable=False),
        sa.Column("end_time", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float()),
        sa.Column("embedding", Vector(1536)),
        sa.Column("search_vector", TSVECTOR(),
                  sa.Computed("to_tsvector('english', coalesce(text, ''))", persisted=True)),
        sa.Column("word_timestamps", JSONB(), server_default="[]"),
        sa.CheckConstraint("end_time >= start_time", name="check_segment_time_validity"),
    )
    for column in ("session_id", "start_time"):
        op.create_index(f"ix_transcript_segments_{column}", "transcript_segments", [column])
    op.create_index("ix_segment_session_time", "transcript_segments", ["session_id", "start_time"])
    op.create_index("ix_segment_search_vector_gin", "transcript_segments", ["search_vector"], postgresql_using="gin")
    op.create_index(
        "ix_segment_embedding_hnsw", "transcript_segments", ["embedding"],
        postgresql_using="hnsw", postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "feature_results", *record_columns(), session_ref(),
        sa.Column("feature_name", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("data", JSONB(), nullable=False),
        sa.Column("processing_time_ms", sa.Integer()),
        sa.Column("provider_model", sa.String(100)),
        sa.UniqueConstraint("session_id", "feature_name", "version", name="uq_feature_session_name_version"),
    )
    for column in ("session_id", "feature_name"):
        op.create_index(f"ix_feature_results_{column}", "feature_results", [column])


def downgrade():
    raise RuntimeError("The baseline may contain existing recordings and cannot be downgraded")
