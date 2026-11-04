"""001 initial schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-11-04 16:45:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # On PostgreSQL, enable extensions
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Table: sites
    op.create_table(
        "sites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("name_local", sa.String(length=255), nullable=True),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("era_label", sa.String(length=100), nullable=True),
        sa.Column("era_start", sa.Integer(), nullable=True),
        sa.Column("era_end", sa.Integer(), nullable=True),
        sa.Column("region", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("location_source", sa.String(length=20), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cover_asset_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_sites_slug", "sites", ["slug"])
    op.create_index("ix_sites_name", "sites", ["name"])

    # Table: assets
    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("uri", sa.Text(), nullable=False),
        sa.Column("thumb_uri", sa.Text(), nullable=True),
        sa.Column("depth_uri", sa.Text(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("mime", sa.String(length=100), nullable=False),
        sa.Column("bytes", sa.Integer(), nullable=False),
        sa.Column("exif", sa.JSON(), nullable=True),
        sa.Column("stage", sa.String(length=30), nullable=False, server_default="queued"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("license", sa.String(length=100), nullable=True),
        sa.Column("attribution", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("stage_updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sha256"),
    )
    op.create_index("ix_assets_sha256", "assets", ["sha256"])
    op.create_index("ix_assets_site_id", "assets", ["site_id"])

    # Table: extractions
    op.create_table(
        "extractions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("monument_type", sa.String(length=50), nullable=True),
        sa.Column("era_estimate", sa.String(length=100), nullable=True),
        sa.Column("features", sa.JSON(), nullable=True),
        sa.Column("materials", sa.JSON(), nullable=True),
        sa.Column("language", sa.String(length=50), nullable=True),
        sa.Column("script", sa.String(length=50), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("translation_en", sa.Text(), nullable=True),
        sa.Column("entities", sa.JSON(), nullable=True),
        sa.Column("location_hint", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("uncertainty_notes", sa.Text(), nullable=True),
        sa.Column("edited_by_human", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("raw", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id"),
    )

    # Table: chunks
    op.create_table(
        "chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("tsv", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chunks_asset_id", "chunks", ["asset_id"])
    op.create_index("ix_chunks_site_id", "chunks", ["site_id"])

    # Table: routes
    op.create_table(
        "routes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("geom_geojson", sa.JSON(), nullable=True),
        sa.Column("stop_site_ids", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Table: stories
    op.create_table(
        "stories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("source_asset_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stories_site_id", "stories", ["site_id"])

    # Table: jobs
    op.create_table(
        "jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="queued", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="4", nullable=False),
        sa.Column("run_after", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_poll", "jobs", ["status", "run_after"])


def downgrade() -> None:
    op.drop_table("jobs")
    op.drop_table("stories")
    op.drop_table("routes")
    op.drop_table("chunks")
    op.drop_table("extractions")
    op.drop_table("assets")
    op.drop_table("sites")

