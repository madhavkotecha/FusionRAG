from __future__ import annotations

import uuid

from sqlalchemy import JSON, Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Component(TimestampMixin, Base):
    __tablename__ = "components"
    __table_args__ = (
        UniqueConstraint("type", "workspace_id", name="uq_component_type_workspace"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    type: Mapped[str] = mapped_column(String(100), index=True)
    category: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    config_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    input_ports: Mapped[list] = mapped_column(JSON, default=list)
    output_ports: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(20), default="seed")
    is_composite: Mapped[bool] = mapped_column(Boolean, default=False)
    steps: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    workspace_id: Mapped[str] = mapped_column(
        String(100), default="_global", server_default="_global"
    )
    file_path: Mapped[str | None] = mapped_column(
        String(500), nullable=True, default=None
    )
    file_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, default=None
    )
    current_version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1"
    )
