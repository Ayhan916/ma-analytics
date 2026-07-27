"""add feature_request_narrative to feature_narratives

Revision ID: i5j6k7l8m9n0
Revises: h4i5j6k7l8m9
Create Date: 2026-07-27
"""
from alembic import op
import sqlalchemy as sa

revision = 'i5j6k7l8m9n0'
down_revision = 'h4i5j6k7l8m9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('feature_narratives', sa.Column('feature_request_narrative', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('feature_narratives', 'feature_request_narrative')
