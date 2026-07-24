"""phase1: started_at on pipeline_jobs, unique constraint + composite index

Revision ID: f1a2b3c4d5e6
Revises: c2d3e4f5a6b7
Create Date: 2026-07-24

"""
from alembic import op
import sqlalchemy as sa

revision = 'f1a2b3c4d5e6'
down_revision = 'c2d3e4f5a6b7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add started_at to pipeline_jobs
    op.add_column('pipeline_jobs',
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True)
    )

    # 2. Unique constraint on reviews (datasource_id, external_id)
    # Only enforce when external_id is NOT NULL (PostgreSQL allows multiple NULLs in unique index)
    op.create_index(
        'ix_reviews_datasource_external_unique',
        'reviews',
        ['datasource_id', 'external_id'],
        unique=True,
        postgresql_where=sa.text('external_id IS NOT NULL'),
    )

    # 3. Composite index on review_signals for feature+signal_type queries
    op.create_index(
        'ix_review_signals_datasource_feature_type',
        'review_signals',
        ['datasource_id', 'feature', 'signal_type'],
    )


def downgrade() -> None:
    op.drop_index('ix_review_signals_datasource_feature_type', table_name='review_signals')
    op.drop_index('ix_reviews_datasource_external_unique', table_name='reviews')
    op.drop_column('pipeline_jobs', 'started_at')
