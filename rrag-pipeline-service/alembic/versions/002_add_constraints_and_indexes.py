"""Add database constraints and indexes.

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Unique constraint: pipeline names must be unique within a workspace
    op.create_unique_constraint(
        "uq_pipelines_workspace_name",
        "pipelines",
        ["workspace_id", "name"],
    )

    # Unique constraint: version numbers must be unique per pipeline
    op.create_unique_constraint(
        "uq_pipeline_versions_pipeline_version",
        "pipeline_versions",
        ["pipeline_id", "version"],
    )

    # Index on pipeline_runs for common queries
    op.create_index(
        "ix_pipeline_runs_pipeline_id_created_at",
        "pipeline_runs",
        ["pipeline_id", "created_at"],
    )

    # Index on pipeline_runs status for filtering
    op.create_index(
        "ix_pipeline_runs_status",
        "pipeline_runs",
        ["status"],
    )

    # Index on pipelines created_by for user-specific queries
    op.create_index(
        "ix_pipelines_created_by",
        "pipelines",
        ["created_by"],
    )


def downgrade() -> None:
    op.drop_index("ix_pipelines_created_by", table_name="pipelines")
    op.drop_index("ix_pipeline_runs_status", table_name="pipeline_runs")
    op.drop_index(
        "ix_pipeline_runs_pipeline_id_created_at", table_name="pipeline_runs"
    )
    op.drop_constraint(
        "uq_pipeline_versions_pipeline_version", "pipeline_versions"
    )
    op.drop_constraint("uq_pipelines_workspace_name", "pipelines")
