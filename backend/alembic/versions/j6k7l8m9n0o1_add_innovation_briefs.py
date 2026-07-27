"""add innovation_briefs table

Revision ID: j6k7l8m9n0o1
Revises: i5j6k7l8m9n0
Create Date: 2026-07-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'j6k7l8m9n0o1'
down_revision = 'i5j6k7l8m9n0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'innovation_briefs',
        sa.Column('id', sa.String(), primary_key=True, server_default=sa.text("gen_random_uuid()::text")),
        sa.Column('user_id', sa.String(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('mode', sa.String(20), nullable=False),
        sa.Column('scope', sa.String(20), nullable=False),
        sa.Column('industry', sa.String(100), nullable=True),
        sa.Column('market', sa.String(10), nullable=True),
        sa.Column('user_hypothesis', sa.Text(), nullable=True),
        sa.Column('product_name', sa.String(200), nullable=False),
        sa.Column('tagline', sa.Text(), nullable=True),
        sa.Column('core_problem', sa.Text(), nullable=True),
        sa.Column('market_gap', sa.Text(), nullable=True),
        sa.Column('features', postgresql.JSONB(), nullable=True),
        sa.Column('target_audience', sa.Text(), nullable=True),
        sa.Column('differentiation', sa.Text(), nullable=True),
        sa.Column('risk', sa.Text(), nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=True),
        sa.Column('hypothesis_check', sa.Text(), nullable=True),
        sa.Column('hypothesis_alignment', sa.String(20), nullable=True),
        sa.Column('total_demand', sa.Integer(), nullable=True),
        sa.Column('apps_analyzed', sa.Integer(), nullable=True),
        sa.Column('sources', postgresql.JSONB(), nullable=True),
    )
    op.create_index('ix_innovation_briefs_user_id', 'innovation_briefs', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_innovation_briefs_user_id', 'innovation_briefs')
    op.drop_table('innovation_briefs')
