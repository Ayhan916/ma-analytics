"""hybrid search: add tsvector column + GIN index + auto-update trigger

Revision ID: a3f1c8d9e201
Revises: df8eba836231
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa

revision = "a3f1c8d9e201"
down_revision = "df8eba836231"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add tsvector column
    op.add_column("reviews", sa.Column("search_vector", sa.Text(), nullable=True))
    op.execute("ALTER TABLE reviews ALTER COLUMN search_vector TYPE tsvector USING NULL::tsvector")

    # 2. GIN index for fast full-text lookups
    op.execute(
        "CREATE INDEX ix_reviews_search_vector ON reviews USING GIN (search_vector)"
    )

    # 3. Trigger function: auto-update search_vector on INSERT/UPDATE of content
    op.execute("""
        CREATE OR REPLACE FUNCTION reviews_search_vector_update()
        RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('simple', coalesce(NEW.content, ''));
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_reviews_search_vector
        BEFORE INSERT OR UPDATE OF content
        ON reviews
        FOR EACH ROW
        EXECUTE FUNCTION reviews_search_vector_update();
    """)

    # 4. Backfill existing rows
    op.execute(
        "UPDATE reviews SET search_vector = to_tsvector('simple', coalesce(content, ''))"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_reviews_search_vector ON reviews")
    op.execute("DROP FUNCTION IF EXISTS reviews_search_vector_update()")
    op.execute("DROP INDEX IF EXISTS ix_reviews_search_vector")
    op.drop_column("reviews", "search_vector")
