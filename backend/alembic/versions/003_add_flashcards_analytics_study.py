"""add flashcards, analytics, study tables

Revision ID: 003
Revises: 002
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Flashcards
    op.create_table(
        "flashcards",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("concept_id", UUID(as_uuid=True), sa.ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("subject_id", UUID(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("front", sa.Text, nullable=False),
        sa.Column("back", sa.Text, nullable=False),
        sa.Column("source", sa.String(50), server_default="auto"),
        sa.Column("easiness_factor", sa.Float, server_default="2.5"),
        sa.Column("interval_days", sa.Float, server_default="1.0"),
        sa.Column("repetitions", sa.Integer, server_default="0"),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_flashcards_student", "flashcards", ["student_id"])
    op.create_index("idx_flashcards_review", "flashcards", ["next_review_at"])

    # Agent Logs
    op.create_table(
        "agent_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("agent_type", sa.String(50), nullable=False),
        sa.Column("intent", sa.String(50), nullable=False),
        sa.Column("response_time_ms", sa.Integer, server_default="0"),
        sa.Column("input_tokens", sa.Integer, server_default="0"),
        sa.Column("output_tokens", sa.Integer, server_default="0"),
        sa.Column("rag_chunks_used", sa.Integer, server_default="0"),
        sa.Column("success", sa.Boolean, server_default="true"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_agent_logs_created", "agent_logs", ["created_at"])

    # Learning Events
    op.create_table(
        "learning_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("concept_id", UUID(as_uuid=True), sa.ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("subject_id", UUID(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("agent_type", sa.String(50), nullable=True),
        sa.Column("data", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_learning_events_student", "learning_events", ["student_id", "created_at"])

    # Study Plans
    op.create_table(
        "study_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_id", UUID(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exam_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("study_hours_per_day", sa.Float, server_default="2.0"),
        sa.Column("plan_data", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Custom Agents
    op.create_table(
        "custom_agents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("system_prompt", sa.Text, nullable=False),
        sa.Column("rubric", JSONB, server_default="{}"),
        sa.Column("agent_type", sa.String(50), server_default="custom"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Study Rooms
    op.create_table(
        "study_rooms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("subject_id", UUID(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("max_members", sa.Integer, server_default="5"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Study Room Members
    op.create_table(
        "study_room_members",
        sa.Column("room_id", UUID(as_uuid=True), sa.ForeignKey("study_rooms.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("study_room_members")
    op.drop_table("study_rooms")
    op.drop_table("custom_agents")
    op.drop_table("study_plans")
    op.drop_table("learning_events")
    op.drop_table("agent_logs")
    op.drop_table("flashcards")
