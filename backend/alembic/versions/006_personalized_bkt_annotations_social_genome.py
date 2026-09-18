"""Personalized BKT parameters, BKT observation log, material annotations,
and social signals on the Learning Genome.

Implements three "Future Work" items from the EduAgent paper:
  - Per-student BKT parameter fitting via EM (replaces global P(L0)/P(T)/
    P(S)/P(G) defaults with individually calibrated ones once enough
    observations exist).
  - Collaborative annotation of course materials within study rooms.
  - Extending the Learning Genome with social/peer-collaboration signals.

Revision ID: 006
Revises: 005
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Per-student personalized BKT parameters -------------------------
    op.create_table(
        "student_bkt_params",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("p_l0", sa.Float, nullable=True),
        sa.Column("p_slip", sa.Float, nullable=True),
        sa.Column("p_guess", sa.Float, nullable=True),
        # Difficulty-tiered learning-transition rates, mirroring the global defaults.
        sa.Column("p_transit_tier1", sa.Float, nullable=True),
        sa.Column("p_transit_tier2", sa.Float, nullable=True),
        sa.Column("p_transit_tier3", sa.Float, nullable=True),
        sa.Column("n_observations", sa.Integer, server_default="0", nullable=False),
        sa.Column("fitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_student_bkt_params_student", "student_bkt_params", ["student_id"])

    # --- Raw observation log (fuel for EM fitting) ------------------------
    op.create_table(
        "bkt_observations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("concept_id", UUID(as_uuid=True), sa.ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("difficulty_tier", sa.Integer, server_default="1", nullable=False),
        sa.Column("correct", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_bkt_observations_student", "bkt_observations", ["student_id", "created_at"])

    # --- Collaborative annotation of course materials ---------------------
    op.create_table(
        "material_annotations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("subject_id", UUID(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("room_id", UUID(as_uuid=True), sa.ForeignKey("study_rooms.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_file", sa.String(255), nullable=False),
        sa.Column("page", sa.Integer, server_default="0", nullable=False),
        sa.Column("highlight_text", sa.Text, nullable=True),
        sa.Column("note", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "idx_material_annotations_lookup", "material_annotations", ["subject_id", "source_file", "page"]
    )

    # --- Learning Genome social/collaboration signals ----------------------
    op.add_column("learning_genomes", sa.Column("collaboration_score", sa.Float, nullable=True))
    op.add_column("learning_genomes", sa.Column("peer_sessions_count", sa.Integer, server_default="0", nullable=False))
    op.add_column("learning_genomes", sa.Column("social_summary", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("learning_genomes", "social_summary")
    op.drop_column("learning_genomes", "peer_sessions_count")
    op.drop_column("learning_genomes", "collaboration_score")

    op.drop_index("idx_material_annotations_lookup", table_name="material_annotations")
    op.drop_table("material_annotations")

    op.drop_index("idx_bkt_observations_student", table_name="bkt_observations")
    op.drop_table("bkt_observations")

    op.drop_index("idx_student_bkt_params_student", table_name="student_bkt_params")
    op.drop_table("student_bkt_params")
