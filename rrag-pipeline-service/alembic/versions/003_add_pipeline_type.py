"""Add pipeline_type and datastore_id columns.

Revision ID: 003
Revises: 002
Create Date: 2025-01-03 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


pipelinetype_enum = sa.Enum("ingestion", "query", name="pipelinetype")


def upgrade() -> None:
    # Create the enum type in PostgreSQL first
    pipelinetype_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "pipelines",
        sa.Column(
            "pipeline_type",
            pipelinetype_enum,
            nullable=False,
            server_default="ingestion",
        ),
    )
    op.add_column(
        "pipelines",
        sa.Column("datastore_id", sa.String(36), nullable=True),
    )
    op.create_index("ix_pipelines_pipeline_type", "pipelines", ["pipeline_type"])
    op.create_index("ix_pipelines_datastore_id", "pipelines", ["datastore_id"])


def downgrade() -> None:
    op.drop_index("ix_pipelines_datastore_id", table_name="pipelines")
    op.drop_index("ix_pipelines_pipeline_type", table_name="pipelines")
    op.drop_column("pipelines", "datastore_id")
    op.drop_column("pipelines", "pipeline_type")
    pipelinetype_enum.drop(op.get_bind(), checkfirst=True)
