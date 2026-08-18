"""Add composite component fields to components table.

Revision ID: 005
Revises: 004
Create Date: 2026-03-16 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns for composite component support
    op.add_column(
        "components",
        sa.Column("source", sa.String(20), nullable=False, server_default="seed"),
    )
    op.add_column(
        "components",
        sa.Column("is_composite", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "components",
        sa.Column("steps", sa.JSON, nullable=True),
    )
    op.add_column(
        "components",
        sa.Column("workspace_id", sa.String(100), nullable=False, server_default="_global"),
    )
    op.add_column(
        "components",
        sa.Column("file_path", sa.String(500), nullable=True),
    )
    op.add_column(
        "components",
        sa.Column("file_hash", sa.String(64), nullable=True),
    )

    # Drop old unique index on type alone and add composite unique constraint
    # The original model used unique=True which created a unique index, not a named constraint
    op.drop_index("ix_components_type", table_name="components")
    op.create_unique_constraint(
        "uq_component_type_workspace", "components", ["type", "workspace_id"]
    )
    # Re-create a non-unique index on type for query performance
    op.create_index("ix_components_type", "components", ["type"])


def downgrade() -> None:
    op.drop_index("ix_components_type", table_name="components")
    op.drop_constraint("uq_component_type_workspace", "components", type_="unique")
    op.create_index("ix_components_type", "components", ["type"], unique=True)

    op.drop_column("components", "file_hash")
    op.drop_column("components", "file_path")
    op.drop_column("components", "workspace_id")
    op.drop_column("components", "steps")
    op.drop_column("components", "is_composite")
    op.drop_column("components", "source")
