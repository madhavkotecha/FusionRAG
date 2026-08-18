from __future__ import annotations

import enum
import uuid

from sqlalchemy import JSON, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class PipelineStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class PipelineType(str, enum.Enum):
    ingestion = "ingestion"
    query = "query"


class Pipeline(TimestampMixin, Base):
    __tablename__ = "pipelines"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    definition: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[PipelineStatus] = mapped_column(
        SAEnum(PipelineStatus), default=PipelineStatus.draft
    )
    pipeline_type: Mapped[PipelineType] = mapped_column(
        SAEnum(PipelineType), default=PipelineType.ingestion, index=True
    )
    datastore_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    created_by: Mapped[str] = mapped_column(String(36))

    versions: Mapped[list[PipelineVersion]] = relationship(
        back_populates="pipeline", cascade="all, delete-orphan"
    )
    runs: Mapped[list["PipelineRun"]] = relationship(
        back_populates="pipeline", cascade="all, delete-orphan"
    )


class PipelineVersion(TimestampMixin, Base):
    __tablename__ = "pipeline_versions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    pipeline_id: Mapped[str] = mapped_column(
        ForeignKey("pipelines.id", ondelete="CASCADE")
    )
    version: Mapped[int] = mapped_column(Integer)
    definition: Mapped[dict] = mapped_column(JSON)
    change_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36))

    pipeline: Mapped[Pipeline] = relationship(back_populates="versions")
