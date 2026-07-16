"""add BKT fields to student_concepts and learning_genomes table

Revision ID: 004
Revises: 003
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Bayesian Knowledge Tracing + predictive forgetting fields
    op.add_column(
        "student_concepts",
        sa.Column("bkt_mastery", sa.Float, server_default="0.1", nullable=False),
    )
    op.add_column(
        "student_concepts",
        sa.Column("memory_stability", sa.Float, server_default="1.0", nullable=False),
    )
    op.add_column(
        "student_concepts",
        sa.Column("predicted_forget_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Learning Genome (cognitive fingerprint)
    op.create_table(
        "learning_genomes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("pace_label", sa.String(20), server_default="average"),
        sa.Column("pace_score", sa.Float, server_default="0.5"),
        sa.Column("preferred_modality", sa.String(50), server_default="concept_qa"),
        sa.Column("optimal_hour", sa.Integer, server_default="18"),
        sa.Column("persistence_score", sa.Float, server_default="0.5"),
        sa.Column("avg_session_minutes", sa.Float, server_default="0.0"),
        sa.Column("misconception_patterns", JSONB, server_default="[]"),
        sa.Column("strengths", JSONB, server_default="[]"),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("data_points", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_learning_genomes_student", "learning_genomes", ["student_id"])


def downgrade() -> None:
    op.drop_index("idx_learning_genomes_student", table_name="learning_genomes")
    op.drop_table("learning_genomes")
    op.drop_column("student_concepts", "predicted_forget_at")
    op.drop_column("student_concepts", "memory_stability")
    op.drop_column("student_concepts", "bkt_mastery")
