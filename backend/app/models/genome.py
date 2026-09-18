import uuid
from datetime import datetime

from sqlalchemy import String, Text, Float, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LearningGenome(Base):
    """A per-student cognitive fingerprint that all agents adapt to."""

    __tablename__ = "learning_genomes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    # Every trait below is nullable: a student with no relevant activity yet has
    # an genuinely unknown trait, and a default would read as an observed one.
    # Learning pace: slow / average / fast (derived from attempts-to-mastery)
    pace_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pace_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Preferred interaction modality (concept_qa / teach_me / viva / exam_prep ...)
    preferred_modality: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Optimal study hour of day (0-23) based on activity + performance
    optimal_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Persistence: how often the student revisits weak concepts (0-1)
    persistence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Average active session length in minutes
    avg_session_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Recurring misconception patterns + error signatures (LLM-derived)
    misconception_patterns: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    strengths: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    # Natural-language summary injected into agent prompts
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_points: Mapped[int] = mapped_column(Integer, default=0)
    # Social/peer-collaboration signals (study rooms, annotations, peer debate)
    collaboration_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    peer_sessions_count: Mapped[int] = mapped_column(Integer, default=0)
    social_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
