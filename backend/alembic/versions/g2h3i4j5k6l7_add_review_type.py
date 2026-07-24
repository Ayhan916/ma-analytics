"""add review_type to reviews

Revision ID: g2h3i4j5k6l7
Revises: f1a2b3c4d5e6
Create Date: 2026-07-24

"""
from alembic import op
import sqlalchemy as sa

revision = 'g2h3i4j5k6l7'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('reviews', sa.Column('review_type', sa.String(), nullable=True))
    op.create_index('ix_reviews_type', 'reviews', ['datasource_id', 'review_type'])


def downgrade() -> None:
    op.drop_index('ix_reviews_type', table_name='reviews')
    op.drop_column('reviews', 'review_type')
