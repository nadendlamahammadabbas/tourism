"""SQLAlchemy 2.0 database models for Smriti heritage archive."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid


class Base(DeclarativeBase):
    """Base declarative class with common helpers."""
    pass


# Compatible JSON type (JSONB on Postgres, JSON elsewhere)
JsonType = JSON().with_variant(JSONB, "postgresql")


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name_local: Mapped[str | None] = mapped_column(String(255), nullable=True)
    type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="other"
    )  # stepwell|fort|temple|mosque|haveli|palace|craft|manuscript|other
    era_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    era_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    era_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_source: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # user|exif|model|seed
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_asset_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=datetime.utcnow
    )

    # Relationships
    assets: Mapped[list["Asset"]] = relationship("Asset", back_populates="site")
    stories: Mapped[list["Story"]] = relationship("Story", back_populates="site")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("sites.id", ondelete="SET NULL"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(
        String(20), nullable=False, default="photo"
    )  # photo|document|journal
    uri: Mapped[str] = mapped_column(Text, nullable=False)
    thumb_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    depth_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    mime: Mapped[str] = mapped_column(String(100), nullable=False)
    bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    exif: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    stage: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued"
    )  # queued|processing|done|failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    license: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attribution: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=datetime.utcnow
    )
    stage_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=datetime.utcnow
    )

    # Relationships
    site: Mapped[Site | None] = relationship("Site", back_populates="assets")
    extraction: Mapped["Extraction | None"] = relationship(
        "Extraction", back_populates="asset", uselist=False
    )
    chunks: Mapped[list["Chunk"]] = relationship("Chunk", back_populates="asset")


class Extraction(Base):
    __tablename__ = "extractions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("assets.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    monument_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    era_estimate: Mapped[str | None] = mapped_column(String(100), nullable=True)
    features: Mapped[list[str] | None] = mapped_column(JsonType, nullable=True)
    materials: Mapped[list[str] | None] = mapped_column(JsonType, nullable=True)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    script: Mapped[str | None] = mapped_column(String(50), nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    translation_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    entities: Mapped[list[dict[str, Any]] | None] = mapped_column(JsonType, nullable=True)
    location_hint: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    uncertainty_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    edited_by_human: Mapped[bool] = mapped_column(Boolean, default=False)
    raw: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=datetime.utcnow
    )

    # Relationship
    asset: Mapped[Asset] = relationship("Asset", back_populates="extraction")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("sites.id", ondelete="SET NULL"), nullable=True, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(JsonType, nullable=False)
    tsv: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    asset: Mapped[Asset] = relationship("Asset", back_populates="chunks")


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    geom_geojson: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    stop_site_ids: Mapped[list[str] | None] = mapped_column(JsonType, nullable=True)


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(
        String(30), nullable=False, default="folklore"
    )  # folklore|observation|journal
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_asset_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    # Relationship
    site: Mapped[Site] = relationship("Site", back_populates="stories")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued", index=True
    )  # queued|processing|done|failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=4)
    run_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=datetime.utcnow, index=True
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=datetime.utcnow
    )

