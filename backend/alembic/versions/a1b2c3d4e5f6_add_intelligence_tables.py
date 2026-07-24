"""add intelligence tables: review_sentences, review_signals, feature_narratives

Revision ID: a1b2c3d4e5f6
Revises: eae072bfdc11
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'eae072bfdc11'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'review_sentences',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('review_id', sa.String(), sa.ForeignKey('reviews.id', ondelete='CASCADE'), nullable=False),
        sa.Column('datasource_id', sa.String(), sa.ForeignKey('datasources.id', ondelete='CASCADE'), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_review_sentences_review_id', 'review_sentences', ['review_id'])
    op.create_index('ix_review_sentences_datasource_id', 'review_sentences', ['datasource_id'])

    op.create_table(
        'review_signals',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('sentence_id', sa.String(), sa.ForeignKey('review_sentences.id', ondelete='CASCADE'), nullable=False),
        sa.Column('review_id', sa.String(), sa.ForeignKey('reviews.id', ondelete='CASCADE'), nullable=False),
        sa.Column('datasource_id', sa.String(), sa.ForeignKey('datasources.id', ondelete='CASCADE'), nullable=False),
        sa.Column('feature', sa.String(100), nullable=False),
        sa.Column('signal_type', sa.String(50), nullable=False),
        sa.Column('severity', sa.Integer(), nullable=True),
        sa.Column('is_resolved', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('version_hint', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_review_signals_datasource_id', 'review_signals', ['datasource_id'])
    op.create_index('ix_review_signals_feature', 'review_signals', ['feature'])
    op.create_index('ix_review_signals_sentence_id', 'review_signals', ['sentence_id'])

    op.create_table(
        'feature_narratives',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('datasource_id', sa.String(), sa.ForeignKey('datasources.id', ondelete='CASCADE'), nullable=False),
        sa.Column('feature', sa.String(100), nullable=False),
        sa.Column('narrative', sa.Text(), nullable=False),
        sa.Column('mention_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('avg_severity', sa.Float(), nullable=True),
        sa.Column('signal_counts', sa.JSON(), nullable=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_feature_narratives_datasource_feature', 'feature_narratives', ['datasource_id', 'feature'], unique=True)


def downgrade() -> None:
    op.drop_table('feature_narratives')
    op.drop_table('review_signals')
    op.drop_table('review_sentences')
