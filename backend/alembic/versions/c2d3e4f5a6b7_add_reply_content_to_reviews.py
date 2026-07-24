"""add reply_content and reply_at to reviews

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-07-24

"""
from alembic import op
import sqlalchemy as sa

revision = 'c2d3e4f5a6b7'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('reviews', sa.Column('reply_content', sa.Text(), nullable=True))
    op.add_column('reviews', sa.Column('reply_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('reviews', 'reply_at')
    op.drop_column('reviews', 'reply_content')
