"""Add component_versions table and current_version column.

Revision ID: 006
Revises: 005
Create Date: 2026-03-21 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "component_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("component_type", sa.String(100), nullable=False, index=True),
        sa.Column("workspace_id", sa.String(100), nullable=False, index=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("code", sa.Text, nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("changed_by", sa.String(100), nullable=False),
        sa.Column("change_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint(
            "component_type", "workspace_id", "version",
            name="uq_component_version",
        ),
    )

    op.add_column(
        "components",
        sa.Column("current_version", sa.Integer, nullable=False, server_default="1"),
    )

    # Backfill: create version 1 rows for existing custom components
    # that have file_path set (meaning they have code in MinIO)
    conn = op.get_bind()
    custom_components = conn.execute(
        sa.text(
            "SELECT type, workspace_id, file_path FROM components "
            "WHERE source = 'custom' AND file_path IS NOT NULL"
        )
    ).fetchall()
    for comp in custom_components:
        conn.execute(
            sa.text(
                "INSERT INTO component_versions "
                "(id, component_type, workspace_id, version, code, file_hash, changed_by, change_reason, created_at) "
                "VALUES (:id, :type, :ws, 1, :code, :hash, 'migration', 'Backfill from existing component', NOW())"
            ),
            {
                "id": str(__import__("uuid").uuid4()),
                "type": comp[0],
                "ws": comp[1],
                "code": "# Code stored in MinIO — run seed bootstrap to populate",
                "hash": "backfill",
            },
        )


def downgrade() -> None:
    op.drop_column("components", "current_version")
    op.drop_table("component_versions")
