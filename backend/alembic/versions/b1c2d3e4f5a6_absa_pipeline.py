"""ABSA pipeline: add review_aspects, update review_signals

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = 'b1c2d3e4f5a6'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'review_aspects',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('review_id', sa.String(), sa.ForeignKey('reviews.id', ondelete='CASCADE'), nullable=False),
        sa.Column('datasource_id', sa.String(), sa.ForeignKey('datasources.id', ondelete='CASCADE'), nullable=False),
        sa.Column('aspect_term', sa.String(300), nullable=True),
        sa.Column('feature', sa.String(100), nullable=False),
        sa.Column('sentiment', sa.String(20), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('span_text', sa.Text(), nullable=True),
        sa.Column('absa_source', sa.String(30), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_review_aspects_review_id', 'review_aspects', ['review_id'])
    op.create_index('ix_review_aspects_datasource_id', 'review_aspects', ['datasource_id'])
    op.create_index('ix_review_aspects_feature', 'review_aspects', ['feature'])

    # Make sentence_id nullable and update FK to SET NULL on delete
    op.drop_constraint('review_signals_sentence_id_fkey', 'review_signals', type_='foreignkey')
    op.alter_column('review_signals', 'sentence_id', nullable=True)
    op.create_foreign_key(
        'review_signals_sentence_id_fkey',
        'review_signals', 'review_sentences',
        ['sentence_id'], ['id'],
        ondelete='SET NULL',
    )

    # Add aspect_id FK
    op.add_column('review_signals', sa.Column('aspect_id', sa.String(), nullable=True))
    op.create_foreign_key(
        'review_signals_aspect_id_fkey',
        'review_signals', 'review_aspects',
        ['aspect_id'], ['id'],
        ondelete='SET NULL',
    )
    op.create_index('ix_review_signals_aspect_id', 'review_signals', ['aspect_id'])


def downgrade() -> None:
    op.drop_index('ix_review_signals_aspect_id', 'review_signals')
    op.drop_constraint('review_signals_aspect_id_fkey', 'review_signals', type_='foreignkey')
    op.drop_column('review_signals', 'aspect_id')
    op.drop_constraint('review_signals_sentence_id_fkey', 'review_signals', type_='foreignkey')
    op.alter_column('review_signals', 'sentence_id', nullable=False)
    op.create_foreign_key(
        'review_signals_sentence_id_fkey',
        'review_signals', 'review_sentences',
        ['sentence_id'], ['id'],
        ondelete='CASCADE',
    )
    op.drop_table('review_aspects')
