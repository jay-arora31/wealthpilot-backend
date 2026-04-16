"""add_source_quote_to_data_conflicts

Revision ID: a3f1c9d8b2e4
Revises: 7cb8dfd8dd81
Create Date: 2026-04-16 00:45:00.000000

Stores the source phrase from the audio transcript (or Excel cell label)
that produced an incoming value. Makes conflict review auditable — the
advisor can see the exact words that led to a proposed change.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3f1c9d8b2e4"
down_revision: Union[str, Sequence[str], None] = "7cb8dfd8dd81"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "data_conflicts",
        sa.Column("source_quote", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("data_conflicts", "source_quote")
