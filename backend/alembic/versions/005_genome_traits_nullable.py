"""Make learning genome traits nullable

An unmeasured trait must read as unknown rather than as a default value, so a
student with no relevant activity is not shown an invented cognitive profile.

Revision ID: 005
Revises: 004
"""

import sqlalchemy as sa
from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None

TRAITS = [
    ("pace_label", sa.String(20)),
    ("pace_score", sa.Float()),
    ("preferred_modality", sa.String(50)),
    ("optimal_hour", sa.Integer()),
    ("persistence_score", sa.Float()),
    ("avg_session_minutes", sa.Float()),
]


def upgrade() -> None:
    for name, col_type in TRAITS:
        op.alter_column(
            "learning_genomes", name, existing_type=col_type, nullable=True
        )


def downgrade() -> None:
    for name, col_type in TRAITS:
        op.alter_column(
            "learning_genomes", name, existing_type=col_type, nullable=False
        )
