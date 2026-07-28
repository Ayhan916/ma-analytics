"""add concept_description to innovation_briefs

Revision ID: k7l8m9n0o1p2
Revises: j6k7l8m9n0o1
Create Date: 2026-07-27
"""
from alembic import op
import sqlalchemy as sa

revision = 'k7l8m9n0o1p2'
down_revision = 'j6k7l8m9n0o1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('innovation_briefs', sa.Column('concept_description', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('innovation_briefs', 'concept_description')
