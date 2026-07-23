"""add conversation metadata column

Revision ID: 002
Revises: 001_initial
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "002"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("metadata", JSONB, server_default="{}", nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "metadata")
